import logging
import uuid
import json
import time
import re
from typing import Optional, Dict, Any, List, AsyncGenerator

from llama_stack_client import LlamaStackClient
from llama_stack_client.types import UserMessage

logger = logging.getLogger("ValidationAgent")


def extract_mcp_tool_result(turn):
    """
    Returns the first MCP tool_execution step output, parsed as JSON.
    Ignores post-tool inference steps.
    """
    steps = getattr(turn, "steps", [])
    logger.debug(f"🔍 Total steps in turn: {len(steps)}")

    for idx, step in enumerate(steps):
        step_type = getattr(step, "step_type", type(step).__name__).lower()
        logger.debug(f"Step {idx}: {step_type}")
        if "tool" in step_type:
            logger.info(f"🔧 Found tool_execution step at idx={idx}")
            # Extract tool_responses (list)
            for tr_idx, tool_response in enumerate(getattr(step, "tool_responses", [])):
                content = getattr(tool_response, "content", "")
                # Typical MCP wrapper: {"type":"text","text":"{...json...}"}
                try:
                    parsed = json.loads(content)
                    if isinstance(parsed, dict) and "text" in parsed:
                        inner = json.loads(parsed["text"])
                        logger.info(f" Parsed MCP tool response at step {idx}, tool_response {tr_idx}")
                        return inner  # Found the canonical result!
                    elif isinstance(parsed, dict) and ("output" in parsed or "tool" in parsed):
                        logger.info(f" Parsed MCP tool response at step {idx}, tool_response {tr_idx}")
                        return parsed
                except Exception as e:
                    logger.warning(f"Failed to parse tool response content as JSON: {e}")
            # If we got here, but couldn't parse, continue searching
        # Ignore "inference" steps after tool_execution!
    logger.warning("⚠️ No MCP tool_execution result found in turn steps.")
    return None


class ValidationAgent:
    """
    ValidationAgent: Ansible playbook validator using MCP ansible-lint tool.
    Always returns the tool output, never post-tool hallucinations.
    """

    def __init__(
        self, 
        client: LlamaStackClient, 
        agent_id: str, 
        session_id: str, 
        prompt_template: str,    # From config
        instruction: str,        # From config
        timeout: int = 60, 
        verbose_logging: bool = False
    ):
        logger.info(f"🚀 Initializing ValidationAgent")
        self.client = client
        self.agent_id = agent_id
        self.session_id = session_id
        self.prompt_template = prompt_template
        self.instruction = instruction
        self.timeout = timeout
        self.verbose_logging = verbose_logging
        self.logger = logger
        if verbose_logging:
            self.logger.setLevel(logging.DEBUG)
        self.supported_profiles = ["basic", "moderate", "safety", "shared", "production"]
        self.logger.info(f"ValidationAgent initialized with agent_id: {agent_id}")

    def create_new_session(self, correlation_id: str) -> str:
        try:
            session_name = f"validation-{correlation_id}-{uuid.uuid4()}"
            response = self.client.agents.session.create(
                agent_id=self.agent_id,
                session_name=session_name,
            )
            session_id = response.session_id
            self.logger.info(f"📱 Created new session: {session_id} for correlation: {correlation_id}")
            return session_id
        except Exception as e:
            self.logger.error(f"Failed to create session: {e}")
            self.logger.info(f"↩️ Falling back to default session: {self.session_id}")
            return self.session_id

    def _build_validation_prompt(self, playbook_content: str, profile: str) -> str:
        """Build validation prompt using config-driven template and instruction."""
        try:
            return self.prompt_template.format(
                instruction=self.instruction,
                playbook_content=playbook_content.strip(),
                profile=profile
            )
        except KeyError as e:
            logger.warning(f"Template parameter {e} not found, trying alternative format...")
            try:
                return self.prompt_template.format(
                    instruction=self.instruction,
                    playbook=playbook_content.strip(),
                    profile=profile
                )
            except Exception as e2:
                logger.error(f"Error formatting validation prompt from config: {e2}. Falling back to safe template.")
                return self._build_fallback_prompt(playbook_content, profile)
        except Exception as e:
            logger.error(f"Error formatting validation prompt from config: {e}. Falling back to safe template.")
            return self._build_fallback_prompt(playbook_content, profile)

    def _build_fallback_prompt(self, playbook_content: str, profile: str) -> str:
        return f"""{self.instruction}

Use the lint_ansible_playbook tool with {profile} profile to check this playbook:

{playbook_content.strip()}
"""

    async def validate_playbook(
        self, 
        playbook_content: str, 
        profile: str = "basic", 
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        correlation_id = correlation_id or str(uuid.uuid4())
        start_time = time.time()
        if profile not in self.supported_profiles:
            raise ValueError(f"Unsupported profile: {profile}. Supported: {self.supported_profiles}")
        self.logger.info(f"🔍 Validating playbook with {profile} profile (correlation: {correlation_id})")
        try:
            query_session_id = self.create_new_session(correlation_id)
            user_prompt = self._build_validation_prompt(playbook_content, profile)
            
            if self.verbose_logging:
                self.logger.debug(f"Built validation prompt: {user_prompt[:500]}...")
            
            messages = [UserMessage(role="user", content=user_prompt)]

            generator = self.client.agents.turn.create(
                agent_id=self.agent_id,
                session_id=query_session_id,
                messages=messages,
                stream=True,
            )

            turn = None
            timeout_seconds = self.timeout
            timeout_start = time.time()
            chunk_count = 0
            last_event_time = timeout_start
            
            for chunk in generator:
                chunk_count += 1
                current_time = time.time()
                if current_time - last_event_time > 20 or current_time - timeout_start > timeout_seconds:
                    self.logger.error("⏰ Validation timeout or event delay.")
                    break
                last_event_time = current_time

                if hasattr(chunk, 'event') and hasattr(chunk.event, 'payload'):
                    event = chunk.event
                    event_type = getattr(event.payload, 'event_type', 'unknown')
                    if event_type == "turn_complete":
                        turn = event.payload.turn
                        self.logger.info(f" Turn completed after {current_time - timeout_start:.1f}s with {chunk_count} chunks")
                        break

            if not turn:
                self.logger.error(f" No turn completed in response after {chunk_count} chunks")
                return {
                    "success": False,
                    "correlation_id": correlation_id,
                    "profile": profile,
                    "error": f"Turn never completed after {chunk_count} chunks.",
                    "summary": {"passed": False, "exit_code": -1},
                    "issues_count": 0,
                    "issues": [],
                    "formatted_issues": "Agent turn never completed. This suggests the MCP tool is not responding or the agent is stuck.",
                    "elapsed_time": time.time() - start_time,
                    "timeout": True,
                    "debug_info": {
                        "chunk_count": chunk_count,
                        "agent_stuck": True
                    }
                }
            
            # --- Main Fix: Return only the MCP tool result ---
            result = await self._process_validation_response(turn, correlation_id, profile, time.time() - start_time)
            return result
        except TimeoutError as e:
            return {
                "success": False,
                "correlation_id": correlation_id,
                "profile": profile,
                "error": f"Validation timeout: {str(e)}",
                "summary": {"passed": False},
                "issues_count": 0,
                "issues": [],
                "formatted_issues": "Validation timed out",
                "elapsed_time": time.time() - start_time,
                "timeout": True
            }
        except Exception as e:
            return {
                "success": False,
                "correlation_id": correlation_id,
                "profile": profile,
                "error": str(e),
                "summary": {"passed": False},
                "issues_count": 0,
                "issues": [],
                "formatted_issues": f"Validation failed: {str(e)}",
                "elapsed_time": time.time() - start_time
            }

    async def _process_validation_response(self, turn, correlation_id: str, profile: str, elapsed_time: float) -> Dict[str, Any]:
        tool_result = extract_mcp_tool_result(turn)
        if tool_result:
            output = tool_result.get("output", {})
            summary = output.get("summary", {})
            issues = output.get("issues", [])
            raw_output = output.get("raw_output", {})

            return {
                "success": tool_result.get("success", True),
                "correlation_id": correlation_id,
                "profile": profile,
                "summary": summary,
                "issues_count": summary.get("issue_count", len(issues)),
                "issues": issues,
                "formatted_issues": "\n".join(
                    f"[{i.get('severity','').upper()}] {i.get('rule','')}: {i.get('message','')}" for i in issues
                ) if issues else (raw_output.get("stdout", "") or "No issues found."),
                "passed": summary.get("passed", False),
                "raw_stdout": raw_output.get("stdout", ""),
                "raw_stderr": raw_output.get("stderr", ""),
                "tool_response": tool_result,
                "tool": tool_result.get("tool", "mcp::ansible_lint"),
                "elapsed_time": elapsed_time,
                "session_info": {
                    "agent_id": self.agent_id,
                    "pattern": "Registry-based"
                }
            }
        else:
            return {
                "success": False,
                "correlation_id": correlation_id,
                "profile": profile,
                "error": "No MCP tool_execution result found in agent response.",
                "summary": {"passed": False},
                "issues_count": 0,
                "issues": [],
                "formatted_issues": "No MCP tool_execution result found.",
                "elapsed_time": elapsed_time,
                "session_info": {
                    "agent_id": self.agent_id,
                    "pattern": "Registry-based"
                },
                "debug_info": {}
            }

    # --- Utility Methods (Unchanged) ---
    async def validate_playbook_stream(
        self, 
        playbook_content: str, 
        profile: str = "basic", 
        correlation_id: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        correlation_id = correlation_id or str(uuid.uuid4())
        try:
            yield {
                "type": "progress",
                "status": "processing", 
                "message": f"🔍 Validation started with {profile} profile",
                "agent_info": {
                    "agent_id": self.agent_id,
                    "correlation_id": correlation_id,
                    "pattern": "Registry-based"
                }
            }
            result = await self.validate_playbook(playbook_content, profile, correlation_id)
            yield {
                "type": "final_result",
                "data": result,
                "correlation_id": correlation_id
            }
        except Exception as e:
            yield {
                "type": "error",
                "error": str(e),
                "correlation_id": correlation_id
            }

    async def validate_syntax(
        self, 
        playbook_content: str, 
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        return await self.validate_playbook(
            playbook_content=playbook_content,
            profile="basic",
            correlation_id=correlation_id
        )

    async def production_validate(
        self, 
        playbook_content: str, 
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        return await self.validate_playbook(
            playbook_content=playbook_content,
            profile="production", 
            correlation_id=correlation_id
        )

    async def validate_multiple_files(
        self, 
        files: Dict[str, str], 
        profile: str = "basic",
        correlation_id: Optional[str] = None
    ) -> Dict[str, Dict[str, Any]]:
        correlation_id = correlation_id or str(uuid.uuid4())
        results = {}
        for filename, content in files.items():
            self.logger.info(f"🔍 Validating file: {filename}")
            file_correlation = f"{correlation_id}-{filename}"
            try:
                result = await self.validate_playbook(content, profile, file_correlation)
                result["filename"] = filename
                results[filename] = result
            except Exception as e:
                self.logger.error(f"Failed to validate {filename}: {e}")
                results[filename] = {
                    "success": False,
                    "filename": filename,
                    "correlation_id": file_correlation,
                    "error": str(e),
                    "summary": {"passed": False},
                    "issues_count": 0,
                    "issues": [],
                    "formatted_issues": f"Failed to validate {filename}: {str(e)}"
                }
        return results

    async def debug_tools(self) -> Dict[str, Any]:
        try:
            simple_prompt = "What tools do you have available? List all your tools."
            messages = [UserMessage(role="user", content=simple_prompt)]
            generator = self.client.agents.turn.create(
                agent_id=self.agent_id,
                session_id=self.session_id,
                messages=messages,
                stream=True,
            )
            turn = None
            events_seen = []
            for chunk in generator:
                event = chunk.event
                event_type = event.payload.event_type
                events_seen.append(event_type)
                if event_type == "turn_complete":
                    turn = event.payload.turn
                    break
            tool_info = {
                "turn_completed": turn is not None,
                "events_seen": events_seen,
                "steps_count": len(turn.steps) if turn and hasattr(turn, 'steps') else 0,
                "output_message": turn.output_message.content if turn and hasattr(turn, 'output_message') and turn.output_message else None
            }
            return tool_info
        except Exception as e:
            return {"error": str(e), "available": False}

    async def test_tool_availability(self) -> Dict[str, Any]:
        try:
            test_playbook = """---
- name: Simple test
  hosts: localhost
  tasks:
    - name: Debug task
      debug:
        msg: "test"
"""
            tool_prompt = f"""Use the lint_ansible_playbook tool to check this playbook:

{test_playbook}

Call the ansible-lint tool now."""
            messages = [UserMessage(role="user", content=tool_prompt)]
            generator = self.client.agents.turn.create(
                agent_id=self.agent_id,
                session_id=self.session_id,
                messages=messages,
                stream=True,
            )
            turn = None
            events_seen = []
            tool_events = []
            timeout_start = time.time()
            for chunk in generator:
                if (time.time() - timeout_start) > 30:
                    return {
                        "success": False,
                        "error": "Tool test timed out after 30 seconds",
                        "events_seen": events_seen,
                        "tool_events": tool_events
                    }
                event = chunk.event
                event_type = event.payload.event_type
                events_seen.append(event_type)
                if "tool" in event_type.lower():
                    tool_events.append(event_type)
                if event_type == "turn_complete":
                    turn = event.payload.turn
                    break
            has_tool_steps = False
            if turn and hasattr(turn, 'steps'):
                for step in turn.steps:
                    step_type = getattr(step, "step_type", type(step).__name__)
                    if "tool" in step_type.lower():
                        has_tool_steps = True
                        break
            return {
                "success": turn is not None,
                "turn_completed": turn is not None,
                "events_seen": events_seen,
                "tool_events": tool_events,
                "has_tool_steps": has_tool_steps,
                "steps_count": len(turn.steps) if turn and hasattr(turn, 'steps') else 0,
                "elapsed_time": time.time() - timeout_start
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def health_check(self) -> bool:
        try:
            test_playbook = """---
- name: Health check playbook
  hosts: localhost
  tasks:
    - name: Test task
      debug:
        msg: "Health check"
"""
            result = await self.validate_playbook(test_playbook, "basic", "health-check")
            return result.get("success") is not None
        except Exception as e:
            self.logger.error(f"Validation health check failed: {e}")
            return False

    def get_status(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "client_base_url": getattr(self.client, 'base_url', 'unknown'),
            "timeout": self.timeout,
            "status": "ready",
            "pattern": "Registry-based",
            "tool": "mcp::ansible_lint",
            "supported_profiles": self.supported_profiles
        }

    def get_supported_profiles(self) -> List[str]:
        return self.supported_profiles.copy()

    def get_profile_descriptions(self) -> Dict[str, str]:
        return {
            "basic": "Basic syntax and structure validation",
            "moderate": "Standard best practices checking", 
            "safety": "Security-focused validation rules",
            "shared": "Rules for shared/reusable playbooks",
            "production": "Strict production-ready validation"
        }
