# validate_agent.py

import time
import json
import logging
import uuid
from typing import Optional, Dict, Any, Generator, List
import asyncio

from llama_stack_client import LlamaStackClient
from llama_stack_client.types import UserMessage
from llama_stack_client.types import ToolResponseMessage

import re

from agents.tools.ansible_lint_tool import ansible_lint_tool  # Import our custom tool

logger = logging.getLogger("ValidationAgent")

class ValidationAgent:
    def __init__(
        self,
        client: LlamaStackClient,
        agent_id: str,
        session_id: str,
        instruction: str,
        verbose_logging: bool = False,
        timeout: int = 120,
    ):
        self.client = client
        self.agent_id = agent_id
        self.session_id = session_id
        self.instruction = instruction
        self.verbose_logging = verbose_logging
        self.timeout = timeout
        self.default_profile = "basic"
        self.ansible_lint_tool = ansible_lint_tool  # Make our custom tool available
        logger.info(f"ValidationAgent initialized (id={agent_id}) with session {session_id}")

    def create_new_session(self, correlation_id: str) -> str:
        """Create a new session for validation"""
        try:
            session_name = f"validation-{correlation_id}-{uuid.uuid4()}"
            response = self.client.agents.session.create(
                agent_id=self.agent_id,
                session_name=session_name,
            )
            session_id = response.session_id
            logger.info(f"📱 Created validation session: {session_id} for correlation: {correlation_id}")
            return session_id
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            logger.info(f"↩️ Falling back to default session: {self.session_id}")
            return self.session_id

    async def validate_playbook(
        self, 
        playbook_content: str, 
        profile: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate an Ansible playbook using LLM agent with ansible_lint_tool.
        This is truly agentic - the LLM decides when and how to use the tool.
        """
        correlation_id = correlation_id or f"val-{uuid.uuid4().hex[:8]}"
        start_time = time.monotonic()
        profile = profile or self.default_profile
        
        logger.info(f"[{correlation_id}] Starting agentic playbook validation with profile: {profile}")
        
        try:
            # Use config-driven instruction with playbook content
            prompt = f"""
            {self.instruction}
            
            Playbook to validate:
            {playbook_content}
            
            Profile: {profile}
            
            Please validate this playbook using the ansible_lint_tool and provide your analysis.
            """
            
            # Let the LLM agent decide to call the tool using streaming
            messages = [UserMessage(role="user", content=prompt)]
            
            logger.info(f"[{correlation_id}] Sending validation request to LLM agent (streaming)")
            
            # Use streaming agent turns
            generator = self.client.agents.turn.create(
                agent_id=self.agent_id,
                session_id=self.session_id,
                messages=messages,
                stream=True,
            )
            
            # Process the agent's response and extract tool results
            result = await self._process_agent_response(generator, playbook_content, profile, correlation_id)
            
            return result

        except Exception as e:
            logger.error(f" ValidationAgent error: {e}")
            return self._create_error_response(f"Agent validation failed: {str(e)}")

    def _create_error_response(self, message: str) -> Dict[str, Any]:
        """Helper to create a consistent error response structure."""
        return {
            "validation_passed": False,
            "exit_code": -1,
            "message": message,
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "correlation_id": correlation_id, # Use the current correlation_id
            "elapsed_time": round(time.monotonic() - start_time, 2),
            "profile": profile,
            "playbook_length": len(playbook_content),
            "passed": False,
            "issues_count": 0,
            "issues": [],
            "agentic": True,
            "error": str(e),
        }

    def _parse_agent_response(self, agent_response: str, correlation_id: str) -> Dict[str, Any]:
        """
        Parse the agent's response to extract validation results.
        The agent should have called ansible_lint_tool and provided analysis.
        """
        try:
            # Try to extract JSON from the response
            if "{" in agent_response and "}" in agent_response:
                # Look for JSON-like structures in the response
                start = agent_response.find("{")
                end = agent_response.rfind("}") + 1
                if start != -1 and end > start:
                    json_str = agent_response[start:end]
                    try:
                        parsed = json.loads(json_str)
                        if "validation_passed" in parsed:
                            logger.info(f"[{correlation_id}] Successfully parsed agent response as JSON")
                            return parsed
                    except json.JSONDecodeError:
                        pass
            
            # If no JSON found, try to extract information from text
            logger.info(f"[{correlation_id}] Parsing agent response as text")
            
            # Look for validation indicators in the text
            passed = any(word in agent_response.lower() for word in ["passed", "valid", "success", "no issues"])
            failed = any(word in agent_response.lower() for word in ["failed", "invalid", "error", "issues found"])
            
            # Extract issues count if mentioned
            issues_match = re.search(r'(\d+)\s+issues?', agent_response, re.IGNORECASE)
            issues_count = int(issues_match.group(1)) if issues_match else 0
            
            return {
                "validation_passed": passed and not failed,
                "message": agent_response,
                "issues_count": issues_count,
                "passed": passed and not failed,
                "parsed_from": "text_analysis",
            }
            
        except Exception as e:
            logger.error(f"[{correlation_id}] Failed to parse agent response: {e}")
            return {
                "validation_passed": False,
                "message": f"Failed to parse agent response: {e}",
                "issues_count": 0,
                "passed": False,
                "error": str(e),
            }

    def validate_playbook_stream(
        self, playbook_content: str, profile: Optional[str] = None
    ) -> Generator[str, None, None]:
        """
        Streams playbook validation results as SSE (Server-Sent Events).
        Uses agentic validation with LLM tool calling.
        """
        t0 = time.monotonic()
        profile = profile or self.default_profile
        correlation_id = f"stream-{uuid.uuid4().hex[:8]}"
        
        logger.info(f"[{correlation_id}] Starting agentic streaming validation with profile: {profile}")
        
        try:
            # Run the agentic validation
            result = asyncio.run(self.validate_playbook(playbook_content, profile, correlation_id))
            
            # Stream the result
            yield f"data: {json.dumps({'type': 'result', 'data': result, 'elapsed_time': round(time.monotonic() - t0, 2)})}\n\n"
            
        except Exception as e:
            logger.error(f"[{correlation_id}] Streaming validation error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e), 'elapsed_time': round(time.monotonic() - t0, 2)})}\n\n"
        
        # End event
        yield f"data: {json.dumps({'type': 'end', 'elapsed_time': round(time.monotonic() - t0, 2)})}\n\n"

    async def validate_multiple_files(
        self, 
        files: Dict[str, str], 
        profile: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate multiple Ansible playbook files using agentic approach.
        """
        correlation_id = correlation_id or f"multi-{uuid.uuid4().hex[:8]}"
        start_time = time.monotonic()
        profile = profile or self.default_profile
        
        logger.info(f"[{correlation_id}] Starting agentic multiple file validation with profile: {profile}")
        
        results = {}
        total_issues = 0
        total_passed = 0
        
        for filename, content in files.items():
            try:
                result = await self.validate_playbook(content, profile, f"{correlation_id}-{filename}")
                results[filename] = result
                if result.get("passed", False):
                    total_passed += 1
                total_issues += result.get("issues_count", 0)
            except Exception as e:
                logger.error(f"[{correlation_id}] Failed to validate {filename}: {e}")
                results[filename] = {
                    "validation_passed": False,
                    "message": f"Validation failed: {e}",
                    "issues_count": 0,
                    "passed": False,
                }
        
        overall_result = {
            "validation_passed": total_passed == len(files),
            "total_files": len(files),
            "passed_files": total_passed,
            "failed_files": len(files) - total_passed,
            "total_issues": total_issues,
            "file_results": results,
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "correlation_id": correlation_id,
            "elapsed_time": round(time.monotonic() - start_time, 2),
            "profile": profile,
            "agentic": True,
        }
        
        logger.info(f"[{correlation_id}] Agentic multiple file validation completed: {total_passed}/{len(files)} files passed")
        return overall_result

    async def validate_syntax(
        self, 
        playbook_content: str,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Quick syntax validation of an Ansible playbook using agentic approach.
        """
        correlation_id = correlation_id or f"syntax-{uuid.uuid4().hex[:8]}"
        start_time = time.monotonic()
        
        logger.info(f"[{correlation_id}] Starting agentic syntax validation")
        
        try:
            # Use config-driven instruction for syntax validation
            prompt = f"""
            {self.instruction}
            
            Playbook for syntax validation:
            {playbook_content}
            
            Focus on basic syntax validation using the ansible_lint_tool with basic profile.
            """
            
            messages = [UserMessage(role="user", content=prompt)]
            
            # Use streaming agent turns
            generator = self.client.agents.turn.create(
                agent_id=self.agent_id,
                session_id=self.session_id,
                messages=messages,
                stream=True,
            )
            
            # Collect the streaming response
            agent_response = ""
            turn = None
            
            for chunk in generator:
                event = getattr(chunk, "event", None)
                if event and hasattr(event, "payload"):
                    payload = event.payload
                    if hasattr(payload, "turn_complete") and payload.turn_complete:
                        turn = payload.turn_complete
                        break
                    elif hasattr(payload, "message") and payload.message:
                        agent_response += payload.message.content if hasattr(payload.message, "content") else str(payload.message)
                    elif hasattr(payload, "tool_response") and payload.tool_response:
                        # Tool was called - this is what we want!
                        tool_content = payload.tool_response.content
                        try:
                            # Parse the tool response
                            tool_result = json.loads(tool_content) if isinstance(tool_content, str) else tool_content
                            logger.info(f"[{correlation_id}] Tool was called successfully for syntax validation")
                            
                            # Simplify the result for syntax validation
                            syntax_result = {
                                "syntax_valid": tool_result.get("validation_passed", False),
                                "issues": tool_result.get("issues", []),
                                "issues_count": tool_result.get("issues_count", 0),
                                "message": tool_result.get("message", ""),
                                "agent_id": self.agent_id,
                                "session_id": self.session_id,
                                "correlation_id": correlation_id,
                                "elapsed_time": round(time.monotonic() - start_time, 2),
                                "agentic": True,
                                "tool_called": True,
                            }
                            
                            logger.info(f"[{correlation_id}] Agentic syntax validation completed: {'valid' if syntax_result['syntax_valid'] else 'invalid'}")
                            return syntax_result
                            
                        except Exception as e:
                            logger.error(f"[{correlation_id}] Failed to parse tool response: {e}")
                            return {
                                "syntax_valid": False,
                                "issues": [],
                                "issues_count": 0,
                                "message": f"Tool called but failed to parse response: {e}",
                                "agent_id": self.agent_id,
                                "session_id": self.session_id,
                                "correlation_id": correlation_id,
                                "elapsed_time": round(time.monotonic() - start_time, 2),
                                "agentic": True,
                                "tool_called": True,
                                "error": str(e),
                            }
            
            # If we get here, no tool was called or no turn completed
            if turn:
                agent_response = turn.output_message.content if hasattr(turn, 'output_message') else str(turn)
            
            result = self._parse_agent_response(agent_response, correlation_id)
            
            # Simplify the result for syntax validation
            syntax_result = {
                "syntax_valid": result.get("validation_passed", False),
                "issues": result.get("issues", []),
                "issues_count": result.get("issues_count", 0),
                "message": result.get("message", ""),
                "agent_id": self.agent_id,
                "session_id": self.session_id,
                "correlation_id": correlation_id,
                "elapsed_time": round(time.monotonic() - start_time, 2),
                "agentic": True,
                "tool_called": False,
            }
            
            logger.info(f"[{correlation_id}] Agentic syntax validation completed: {'valid' if syntax_result['syntax_valid'] else 'invalid'}")
            return syntax_result
            
        except Exception as e:
            logger.error(f"[{correlation_id}] Agentic syntax validation failed: {e}")
            return {
                "syntax_valid": False,
                "issues": [],
                "issues_count": 0,
                "message": f"Syntax validation error: {e}",
                "agent_id": self.agent_id,
                "session_id": self.session_id,
                "correlation_id": correlation_id,
                "elapsed_time": round(time.monotonic() - start_time, 2),
                "agentic": True,
                "error": str(e),
            }

    async def production_validate(
        self, 
        playbook_content: str,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Production-ready validation with strict profile using agentic approach.
        """
        correlation_id = correlation_id or f"prod-{uuid.uuid4().hex[:8]}"
        start_time = time.monotonic()
        
        logger.info(f"[{correlation_id}] Starting agentic production validation")
        
        try:
            # Use config-driven instruction for production validation
            prompt = f"""
            {self.instruction}
            
            Playbook for production validation:
            {playbook_content}
            
            Use production profile and provide comprehensive analysis for production deployment readiness.
            """
            
            messages = [UserMessage(role="user", content=prompt)]
            
            # Use streaming agent turns
            generator = self.client.agents.turn.create(
                agent_id=self.agent_id,
                session_id=self.session_id,
                messages=messages,
                stream=True,
            )
            
            # Collect the streaming response
            agent_response = ""
            turn = None
            
            for chunk in generator:
                event = getattr(chunk, "event", None)
                if event and hasattr(event, "payload"):
                    payload = event.payload
                    if hasattr(payload, "turn_complete") and payload.turn_complete:
                        turn = payload.turn_complete
                        break
                    elif hasattr(payload, "message") and payload.message:
                        agent_response += payload.message.content if hasattr(payload.message, "content") else str(payload.message)
                    elif hasattr(payload, "tool_response") and payload.tool_response:
                        # Tool was called - this is what we want!
                        tool_content = payload.tool_response.content
                        try:
                            # Parse the tool response
                            tool_result = json.loads(tool_content) if isinstance(tool_content, str) else tool_content
                            logger.info(f"[{correlation_id}] Tool was called successfully for production validation")
                            
                            # Add production-specific metadata
                            result = tool_result.copy()
                            result.update({
                                "production_ready": result.get("validation_passed", False),
                                "validation_level": "production",
                                "agentic": True,
                                "tool_called": True,
                            })
                            
                            # Add metadata
                            result.update({
                                "agent_id": self.agent_id,
                                "session_id": self.session_id,
                                "correlation_id": correlation_id,
                                "elapsed_time": round(time.monotonic() - start_time, 2),
                                "profile": "production",
                                "playbook_length": len(playbook_content),
                                "passed": result.get("validation_passed", False),
                                "issues_count": len(result.get("issues", [])),
                            })
                            
                            logger.info(f"[{correlation_id}] Agentic production validation completed: {'ready' if result['production_ready'] else 'not ready'}")
                            return result
                            
                        except Exception as e:
                            logger.error(f"[{correlation_id}] Failed to parse tool response: {e}")
                            return {
                                "production_ready": False,
                                "validation_level": "production",
                                "message": f"Tool called but failed to parse response: {e}",
                                "agent_id": self.agent_id,
                                "session_id": self.session_id,
                                "correlation_id": correlation_id,
                                "elapsed_time": round(time.monotonic() - start_time, 2),
                                "validation_passed": False,
                                "issues": [],
                                "issues_count": 0,
                                "agentic": True,
                                "tool_called": True,
                                "error": str(e),
                            }
            
            # If we get here, no tool was called or no turn completed
            if turn:
                agent_response = turn.output_message.content if hasattr(turn, 'output_message') else str(turn)
            
            result = self._parse_agent_response(agent_response, correlation_id)
            
            # Add production-specific metadata
            result.update({
                "production_ready": result.get("validation_passed", False),
                "validation_level": "production",
                "agentic": True,
                "tool_called": False,
            })
            
            logger.info(f"[{correlation_id}] Agentic production validation completed: {'ready' if result['production_ready'] else 'not ready'}")
            return result
            
        except Exception as e:
            logger.error(f"[{correlation_id}] Agentic production validation failed: {e}")
            return {
                "production_ready": False,
                "validation_level": "production",
                "message": f"Production validation error: {e}",
                "agent_id": self.agent_id,
                "session_id": self.session_id,
                "correlation_id": correlation_id,
                "elapsed_time": round(time.monotonic() - start_time, 2),
                "validation_passed": False,
                "issues": [],
                "issues_count": 0,
                "agentic": True,
                "error": str(e),
            }

    def get_supported_profiles(self) -> List[str]:
        """Get list of supported validation profiles."""
        return ["basic", "production"]

    async def health_check(self) -> bool:
        """
        Perform a basic health check using agentic validation.
        """
        try:
            # Use config-driven instruction for health check
            test_playbook = """---
- hosts: localhost
  tasks:
    - name: Health check task
      debug:
        msg: "Health check successful"
"""
            
            prompt = f"""
            {self.instruction}
            
            Test playbook for health check:
            {test_playbook}
            
            Please perform a basic validation to verify the system is working.
            """
            
            messages = [UserMessage(role="user", content=prompt)]
            
            # Use streaming agent turns
            generator = self.client.agents.turn.create(
                agent_id=self.agent_id,
                session_id=self.session_id,
                messages=messages,
                stream=True,
            )
            
            # Just check if we can get a response
            for chunk in generator:
                event = getattr(chunk, "event", None)
                if event and hasattr(event, "payload"):
                    payload = event.payload
                    if hasattr(payload, "turn_complete") and payload.turn_complete:
                        logger.info(" Health check completed successfully")
                        return True
                    elif hasattr(payload, "tool_response") and payload.tool_response:
                        logger.info(" Health check completed with tool response")
                        return True
            
            logger.warning("⚠️ Health check completed but no turn_complete or tool_response found")
            return True
            
        except Exception as e:
            logger.error(f" Health check failed: {e}")
            return False

    def get_status(self) -> Dict[str, Any]:
        """Get agent status information."""
        return {
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "status": "active",
            "supported_profiles": self.get_supported_profiles(),
            "default_profile": self.default_profile,
            "timeout": self.timeout,
            "verbose_logging": self.verbose_logging,
            "agentic": True,
        }

    def _parse_agent_chunk(self, chunk, t0):
        # Handles all possible LlamaStack chunk types
        try:
            event = getattr(chunk, "event", None)
            if event and hasattr(event, "payload"):
                payload = event.payload
                if hasattr(payload, "tool_response") and payload.tool_response:
                    # Tool output
                    content = payload.tool_response.content
                    try:
                        res = json.loads(content) if isinstance(content, str) else content
                        return {
                            "type": "result",
                            "passed": res.get("passed", None),
                            "issues": res.get("issues", []),
                            "issues_count": res.get("issues_count", len(res.get("issues", []))),
                            "formatted_issues": res.get("formatted_issues", ""),
                            "elapsed_time": round(time.monotonic() - t0, 2),
                        }
                    except Exception as ex:
                        return {
                            "type": "error",
                            "error": f"Could not parse tool result: {ex}",
                            "elapsed_time": round(time.monotonic() - t0, 2),
                        }
                elif hasattr(payload, "error") and payload.error:
                    return {
                        "type": "error",
                        "error": str(payload.error),
                        "elapsed_time": round(time.monotonic() - t0, 2),
                    }
            if hasattr(chunk, "message") and chunk.message:
                return {
                    "type": "message",
                    "content": chunk.message,
                    "elapsed_time": round(time.monotonic() - t0, 2),
                }
        except Exception as e:
            return {
                "type": "error",
                "error": f"Unexpected chunk parse error: {e}",
                "elapsed_time": round(time.monotonic() - t0, 2),
            }
        return {
            "type": "unknown",
            "error": "Unrecognized agent chunk.",
            "elapsed_time": round(time.monotonic() - t0, 2),
        }
