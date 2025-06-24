import logging
import re
import uuid
import json
import os
from datetime import datetime
from typing import Optional, Dict, Any, AsyncGenerator
from pathlib import Path

from llama_stack_client import LlamaStackClient
from llama_stack_client.types import UserMessage

# Import your step_printer from utils
from utils.utils import step_printer

logger = logging.getLogger("CodeGeneratorAgent")


def _clean_playbook_output(output: str) -> str:
    """Clean playbook output - UNCHANGED from your original."""
    if not output or not output.strip():
        raise ValueError("Empty output received from LLM")
    output = re.sub(r"(?m)^(```+|~~~+)[\w\-]*\n?", '', output)
    output = output.strip()
    if output.startswith("'''") and output.endswith("'''"):
        output = output[3:-3].strip()
    elif output.startswith('"""') and output.endswith('"""'):
        output = output[3:-3].strip()
    elif output.startswith("'") and output.endswith("'") and output.count('\n') > 1:
        output = output[1:-1].strip()
    elif output.startswith('"') and output.endswith('"') and output.count('\n') > 1:
        output = output[1:-1].strip()
    output = output.replace('\\n', '\n').replace('\\t', '\t')
    output = re.sub(r"^('?-{3,}'?\n)+", '', output)
    if not output.startswith('---'):
        output = '---\n' + output.lstrip()
    output = output.rstrip() + '\n'
    lines = output.split('\n')
    yaml_like = False
    for line in lines[1:10]:
        if line.strip() and (':' in line or line.strip().startswith('-')):
            yaml_like = True
            break
    if not yaml_like:
        logger.warning("Generated output doesn't appear to be valid YAML structure")
    return output


class CodeGeneratorAgent:
    """
    CodeGeneratorAgent - AGENTIC approach using enhanced prompts only.
    Let the LLM do the work, don't hard-code transformations.
    """
    def __init__(
        self,
        client: LlamaStackClient,
        agent_id: str,
        session_id: str,
        config_loader,
        timeout: int = 60
    ):
        self.client = client
        self.agent_id = agent_id
        self.session_id = session_id
        self.timeout = timeout
        self.logger = logger
        self.config_loader = config_loader

        # Load instruction/prompt from config.yaml - UNCHANGED
        self.instruction = (
            self.config_loader.get_agent_instructions("generate")
            or self.config_loader.get_agent_config("generate")["instructions"]
        )
        self.prompt_template = (
            self.config_loader.config.get("prompts", {}).get("generate", None)
        )
        if not self.prompt_template:
            # Enhanced fallback with modern examples
            self.prompt_template = (
                "{instruction}\n\n"
                "MODERN ANSIBLE EXAMPLE:\n"
                "---\n"
                "- name: Example playbook\n"
                "  hosts: all\n"
                "  become: true\n"
                "  tasks:\n"
                "    - name: Install package\n"
                "      ansible.builtin.package:\n"
                "        name: httpd\n"
                "        state: present\n"
                "        use: yum\n"
                "      when: ansible_facts['os_family'] == 'RedHat'\n\n"
                "[CONTEXT]\n{context}\n\n"
                "[INPUT CODE]\n{input_code}\n\n"
                "Generate modern Ansible playbook using FQCN syntax like the example above."
            )

        # Configuration flags - UNCHANGED
        self.detailed_logging = os.getenv("DETAILED_CODE_LOGGING", "true").lower() == "true"
        self.save_debug_files = os.getenv("SAVE_GENERATION_INPUTS", "false").lower() == "true"
        self.step_analysis = os.getenv("ENABLE_STEP_ANALYSIS", "false").lower() == "true"
        self.debug_dir = Path("./debug_logs") if self.save_debug_files else None
        self.max_stream_chunks = int(os.getenv("MAX_STREAM_CHUNKS", "5000"))

        if self.save_debug_files and self.debug_dir:
            try:
                self.debug_dir.mkdir(exist_ok=True)
                self.logger.info(f"Debug file logging enabled - saving to: {self.debug_dir}")
            except Exception as e:
                self.logger.warning(f"Could not create debug directory: {e}")
                self.save_debug_files = False

        self.logger.info(f"CodeGeneratorAgent initialized with agent_id: {agent_id}")

    def create_new_session(self, correlation_id: str) -> str:
        """UNCHANGED from your original."""
        try:
            response = self.client.agents.session.create(
                agent_id=self.agent_id,
                session_name=f"code-generation-{correlation_id}-{uuid.uuid4()}",
            )
            session_id = response.session_id
            self.logger.info(f"Created new session: {session_id} for correlation: {correlation_id}")
            return session_id
        except Exception as e:
            self.logger.error(f"Failed to create session: {e}")
            self.logger.info(f"Falling back to default session: {self.session_id}")
            return self.session_id

    def _analyze_output_quality(self, content: str) -> Dict[str, Any]:
        """Simple analysis of what the LLM generated - no modifications."""
        analysis = {
            "has_fqcn": "ansible.builtin." in content or "community." in content,
            "has_modern_facts": "ansible_facts[" in content,
            "has_collections": "collections:" in content,
            "starts_with_yaml": content.strip().startswith("---"),
            "has_become": "become:" in content,
            "has_handlers": "handlers:" in content,
            "line_count": content.count('\n'),
            "estimated_quality": "unknown"
        }
        
        # Simple quality estimation based on modern patterns
        score = 0
        if analysis["has_fqcn"]: score += 40
        if analysis["has_modern_facts"]: score += 20
        if analysis["starts_with_yaml"]: score += 10
        if analysis["has_become"]: score += 10
        if analysis["has_handlers"]: score += 10
        if analysis["line_count"] > 10: score += 10
        
        if score >= 80:
            analysis["estimated_quality"] = "high"
        elif score >= 50:
            analysis["estimated_quality"] = "medium"
        else:
            analysis["estimated_quality"] = "low"
            
        analysis["quality_score"] = score
        
        return analysis

    def _log_generation_inputs(self, input_code: str, context: str, correlation_id: str, prompt: str):
        """Enhanced logging without hard-coded analysis."""
        self.logger.info(f"Starting generation for correlation: {correlation_id}")
        self.logger.info(f"Input code length: {len(input_code)} characters")
        self.logger.info(f"Context length: {len(context)} characters")
        self.logger.info(f"Has context: {'YES' if context.strip() else 'NO'}")
        self.logger.info(f"Input code preview: {repr(input_code[:200])}...")
        
        if context.strip():
            self.logger.info(f"Context preview: {repr(context[:300])}...")
        
        prompt_stats = {
            "correlation_id": correlation_id,
            "timestamp": datetime.utcnow().isoformat(),
            "prompt_length": len(prompt),
            "prompt_lines": prompt.count('\n'),
            "input_section_length": len(input_code),
            "context_section_length": len(context),
            "has_meaningful_context": bool(context.strip()),
            "context_to_code_ratio": len(context) / max(len(input_code), 1)
        }
        self.logger.info(f"Generation statistics: {json.dumps(prompt_stats, indent=2)}")
        
        if self.detailed_logging:
            self.logger.info(f"=== DETAILED GENERATION LOG START (correlation: {correlation_id}) ===")
            self.logger.info(f"Full input code:\n{'-' * 50}\n{input_code}\n{'-' * 50}")
            self.logger.info(f"Full context:\n{'-' * 50}\n{context or 'NO CONTEXT PROVIDED'}\n{'-' * 50}")
            self.logger.info(f"Full prompt being sent to LLM:\n{'-' * 50}\n{prompt}\n{'-' * 50}")
            self.logger.info(f"=== DETAILED GENERATION LOG END ===")

    def _log_generation_output(self, output: str, cleaned_output: str, correlation_id: str):
        """Enhanced logging with quality analysis."""
        self.logger.info(f"Raw output length: {len(output)} characters")
        self.logger.info(f"Cleaned output length: {len(cleaned_output)} characters")
        self.logger.info(f"Output preview: {repr(cleaned_output[:200])}...")
        
        # Analyze what the LLM actually generated
        quality_analysis = self._analyze_output_quality(cleaned_output)
        self.logger.info(f"LLM output quality: {quality_analysis['estimated_quality']} (score: {quality_analysis['quality_score']}/100)")
        self.logger.info(f"Modern features detected: {json.dumps({k: v for k, v in quality_analysis.items() if k.startswith('has_')}, indent=2)}")
        
        if self.detailed_logging:
            self.logger.info(f"=== OUTPUT DETAILS (correlation: {correlation_id}) ===")
            self.logger.info(f"Raw LLM output:\n{'-' * 50}\n{output}\n{'-' * 50}")
            self.logger.info(f"Cleaned playbook:\n{'-' * 50}\n{cleaned_output}\n{'-' * 50}")
            self.logger.info(f"Quality analysis: {json.dumps(quality_analysis, indent=2)}")
            self.logger.info(f"=== OUTPUT DETAILS END ===")

    def _render_prompt(self, input_code: str, context: str) -> str:
        """UNCHANGED from your original."""
        return self.prompt_template.format(
            instruction=self.instruction,
            input_code=input_code,
            context=context or ""
        )

    async def generate(self, input_code: str, context: Optional[str] = "", correlation_id: Optional[str] = None) -> str:
        """UNCHANGED core logic - just pass through what LLM generates."""
        correlation_id = correlation_id or str(uuid.uuid4())
        context = context or ""
        if not input_code or not input_code.strip():
            raise ValueError("Input code cannot be empty")
        prompt = self._render_prompt(input_code, context)
        self._log_generation_inputs(input_code, context, correlation_id, prompt)
        try:
            generation_session_id = self.create_new_session(correlation_id)
            messages = [UserMessage(role="user", content=prompt)]
            self.logger.info(f"Sending request to LLM (agent: {self.agent_id}, session: {generation_session_id})")
            generator = self.client.agents.turn.create(
                agent_id=self.agent_id,
                session_id=generation_session_id,
                messages=messages,
                stream=True,
            )
            turn = None
            chunk_count = 0
            last_event_type = None
            try:
                for chunk in generator:
                    chunk_count += 1
                    if hasattr(chunk, 'event') and chunk.event:
                        event = chunk.event
                        if hasattr(event, 'payload') and event.payload:
                            event_type = getattr(event.payload, 'event_type', None)
                            last_event_type = event_type
                            if event_type == "turn_complete":
                                turn = getattr(event.payload, 'turn', None)
                                break
                            elif event_type == "step_complete":
                                self.logger.debug(f"Step completed: {chunk_count}")
                            elif event_type == "error":
                                error_msg = getattr(event.payload, 'error', 'Unknown error')
                                raise RuntimeError(f"LLM returned error: {error_msg}")
                    if chunk_count > self.max_stream_chunks:
                        self.logger.warning(f"Too many chunks received ({chunk_count}), breaking")
                        break
            except Exception as stream_error:
                self.logger.error(f"Error during streaming: {stream_error}")
                raise RuntimeError(f"Streaming failed: {stream_error}")
            self.logger.info(f"Received {chunk_count} chunks from LLM (last event: {last_event_type})")
            if not turn:
                error_msg = f"No turn completed in response. Last event type: {last_event_type}, Chunk count: {chunk_count}"
                self.logger.error(error_msg)
                raise RuntimeError(error_msg)
            if not hasattr(turn, 'steps') or not turn.steps:
                self.logger.error("Turn has no steps")
                raise RuntimeError("Invalid turn structure - no steps found")
            if not hasattr(turn, 'output_message') or not turn.output_message:
                self.logger.error("Turn has no output message")
                raise RuntimeError("Invalid turn structure - no output message found")
            self.logger.info(f"Turn completed with {len(turn.steps)} steps")
            if self.step_analysis:
                step_printer(turn.steps, correlation_id)
            else:
                for i, step in enumerate(turn.steps):
                    step_type = type(step).__name__
                    self.logger.info(f"Step {i+1}: {step_type}")
                    if hasattr(step, 'step_type'):
                        self.logger.info(f"   Step type: {step.step_type}")
                    if hasattr(step, 'tool_responses') and step.tool_responses:
                        self.logger.info(f"   Tool responses: {len(step.tool_responses)}")
                    if hasattr(step, 'api_model_response') and step.api_model_response:
                        if hasattr(step.api_model_response, 'content') and step.api_model_response.content:
                            content_preview = step.api_model_response.content[:100].replace('\n', ' ')
                            self.logger.info(f"   Model response preview: {content_preview}...")
            if not hasattr(turn.output_message, 'content'):
                self.logger.error("Output message has no content attribute")
                raise RuntimeError("Invalid output message structure")
            output = turn.output_message.content
            if not output:
                self.logger.error("LLM returned empty output")
                for step in turn.steps:
                    if hasattr(step, 'api_model_response') and step.api_model_response:
                        if hasattr(step.api_model_response, 'content') and step.api_model_response.content:
                            output = step.api_model_response.content
                            self.logger.info("Recovered output from step response")
                            break
                if not output:
                    raise RuntimeError("LLM returned empty output and no fallback found")
            try:
                cleaned_output = _clean_playbook_output(output)
            except ValueError as clean_error:
                self.logger.error(f"Failed to clean output: {clean_error}")
                raise RuntimeError(f"Output cleaning failed: {clean_error}")
            if not cleaned_output or len(cleaned_output.strip()) < 10:
                raise RuntimeError("Cleaned output is too short or empty")
            
            # Just log what we got - no transformations
            self._log_generation_output(output, cleaned_output, correlation_id)
            self.logger.info(f"Generation completed successfully for correlation: {correlation_id}")
            
            # Return exactly what the LLM generated (after basic cleaning)
            return cleaned_output
            
        except Exception as e:
            self.logger.error(f"Playbook generation failed for correlation {correlation_id}: {str(e)}")
            error_context = {
                "correlation_id": correlation_id,
                "error_type": type(e).__name__,
                "error_message": str(e),
                "agent_id": self.agent_id,
                "input_code_length": len(input_code),
                "context_length": len(context),
                "timestamp": datetime.utcnow().isoformat()
            }
            self.logger.error(f"Error context: {json.dumps(error_context, indent=2)}")
            raise RuntimeError(f"Playbook generation failed for {correlation_id}: {str(e)}")

    async def generate_stream(self, input_code: str, context: Optional[str] = "", correlation_id: Optional[str] = None) -> AsyncGenerator[Dict[str, Any], None]:
        """UNCHANGED from your original."""
        correlation_id = correlation_id or str(uuid.uuid4())
        try:
            yield {
                "type": "progress",
                "status": "processing",
                "message": "Code generation started",
                "agent_info": {
                    "agent_id": self.agent_id,
                    "correlation_id": correlation_id
                }
            }
            result = await self.generate(input_code, context, correlation_id)
            yield {
                "type": "final_playbook",
                "data": {
                    "playbook": result,
                    "correlation_id": correlation_id,
                    "session_info": {
                        "agent_id": self.agent_id
                    }
                }
            }
        except Exception as e:
            yield {
                "type": "error",
                "error": str(e),
                "correlation_id": correlation_id
            }

    def get_status(self) -> Dict[str, Any]:
        """Status without hard-coded features."""
        return {
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "client_base_url": str(self.client.base_url) if hasattr(self.client, 'base_url') else "unknown",
            "timeout": self.timeout,
            "status": "ready",
            "pattern": "LSS API - Agentic Approach",
            "approach": {
                "type": "prompt_driven",
                "post_processing": "minimal",
                "hard_coded_rules": "none",
                "quality_analysis": "observational_only"
            },
            "logging_config": {
                "detailed_logging": self.detailed_logging,
                "debug_file_saving": self.save_debug_files,
                "step_analysis": self.step_analysis,
                "debug_directory": str(self.debug_dir) if self.debug_dir else None,
                "max_stream_chunks": self.max_stream_chunks
            }
        }

    async def health_check(self) -> bool:
        """UNCHANGED from your original."""
        try:
            test_correlation = f"health-check-{uuid.uuid4()}"
            messages = [UserMessage(role="user", content="Respond with: HEALTH_CHECK_OK")]
            generator = self.client.agents.turn.create(
                agent_id=self.agent_id,
                session_id=self.session_id,
                messages=messages,
                stream=True,
            )
            chunk_received = False
            for chunk in generator:
                chunk_received = True
                break
            if not chunk_received:
                self.logger.error("Health check failed: No chunks received")
                return False
            self.logger.info("Code generator health check passed")
            return True
        except Exception as e:
            self.logger.error(f"Code generator health check failed: {e}")
            return False