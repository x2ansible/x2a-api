import logging
import re
import uuid
import json
import os
from datetime import datetime
from typing import Optional, Dict, Any, AsyncGenerator
from pathlib import Path
from json import JSONDecodeError

from llama_stack_client import LlamaStackClient
from llama_stack_client.types import UserMessage

try:
    from rich.pretty import pprint
    from termcolor import cprint
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("Warning: rich/termcolor not available. Install with: pip install rich termcolor")

logger = logging.getLogger("CodeGeneratorAgent")

def step_printer(steps, correlation_id: str = ""):
    """
    Print the steps of an agent's response in a formatted way.
    Note: stream need to be set to False to use this function.
    Args:
    steps: List of steps from an agent's response.
    correlation_id: Optional correlation ID for tracking
    """
    if not RICH_AVAILABLE:
        # Fallback to basic logging if rich/termcolor not available
        logger.info(f"Processing {len(steps)} steps for correlation: {correlation_id}")
        for i, step in enumerate(steps):
            step_type = type(step).__name__
            logger.info(f"Step {i+1}: {step_type}")
        return
    
    print(f"\n{'=' * 20} STEP ANALYSIS (correlation: {correlation_id}) {'=' * 20}")
    
    for i, step in enumerate(steps):
        step_type = type(step).__name__
        print("\n"+"-" * 10, f"Step {i+1}: {step_type}","-" * 10)
        
        if step_type == "ToolExecutionStep":
            print("Executing tool...")
            try:
                if hasattr(step, 'tool_responses') and step.tool_responses:
                    response_content = step.tool_responses[0].content
                    if isinstance(response_content, str):
                        try:
                            parsed_content = json.loads(response_content)
                            pprint(parsed_content)
                        except JSONDecodeError:
                            pprint(response_content)
                    else:
                        pprint(response_content)
                else:
                    print("No tool responses found")
            except (TypeError, AttributeError, IndexError) as e:
                print(f"Error processing tool response: {e}")
                
        else:
            # Handle other step types
            if hasattr(step, 'api_model_response') and step.api_model_response:
                if hasattr(step.api_model_response, 'content') and step.api_model_response.content:
                    print("Model Response:")
                    cprint(f"{step.api_model_response.content}\n", "magenta")
                elif hasattr(step.api_model_response, 'tool_calls') and step.api_model_response.tool_calls:
                    tool_call = step.api_model_response.tool_calls[0]
                    print("Tool call Generated:")
                    try:
                        args = json.loads(tool_call.arguments_json)
                        cprint(f"Tool call: {tool_call.tool_name}, Arguments: {args}", "magenta")
                    except (JSONDecodeError, AttributeError):
                        cprint(f"Tool call: {tool_call.tool_name}", "magenta")
            
            # Handle other step attributes
            elif hasattr(step, 'step_type'):
                print(f"Step type: {step.step_type}")
                if hasattr(step, 'step_details'):
                    pprint(step.step_details)
    
    print("="*20, "Query processing completed","="*20,"\n")

def _clean_playbook_output(output: str) -> str:
    """Clean and normalize playbook output"""
    if not output or not output.strip():
        raise ValueError("Empty output received from LLM")
    
    # Remove markdown code blocks
    output = re.sub(r"(?m)^(```+|~~~+)[\w\-]*\n?", '', output)
    output = output.strip()
    
    # Remove surrounding quotes if they wrap the entire content
    if output.startswith("'''") and output.endswith("'''"):
        output = output[3:-3].strip()
    elif output.startswith('"""') and output.endswith('"""'):
        output = output[3:-3].strip()
    elif output.startswith("'") and output.endswith("'") and output.count('\n') > 1:
        output = output[1:-1].strip()
    elif output.startswith('"') and output.endswith('"') and output.count('\n') > 1:
        output = output[1:-1].strip()
    
    # Unescape escaped characters
    output = output.replace('\\n', '\n').replace('\\t', '\t')
    
    # Remove multiple YAML document separators at the start
    output = re.sub(r"^('?-{3,}'?\n)+", '', output)
    
    # Ensure it starts with YAML document separator
    if not output.startswith('---'):
        output = '---\n' + output.lstrip()
    
    # Ensure it ends with a newline
    output = output.rstrip() + '\n'
    
    # Basic YAML validation - check if it looks like valid YAML structure
    lines = output.split('\n')
    yaml_like = False
    for line in lines[1:10]:  # Check first few non-separator lines
        if line.strip() and (':' in line or line.strip().startswith('-')):
            yaml_like = True
            break
    
    if not yaml_like:
        logger.warning("Generated output doesn't appear to be valid YAML structure")
    
    return output

class CodeGeneratorAgent:
    """
    CodeGeneratorAgent - Direct LlamaStack API calls with enhanced logging and error handling
    """
    def __init__(self, client: LlamaStackClient, agent_id: str, session_id: str, timeout: int = 60):
        self.client = client
        self.agent_id = agent_id
        self.session_id = session_id
        self.timeout = timeout
        self.logger = logger
        
        # Logging configuration
        self.detailed_logging = os.getenv("DETAILED_CODE_LOGGING", "true").lower() == "true"
        self.save_debug_files = os.getenv("SAVE_GENERATION_INPUTS", "false").lower() == "true"
        self.step_analysis = os.getenv("ENABLE_STEP_ANALYSIS", "false").lower() == "true"
        self.debug_dir = Path("./debug_logs") if self.save_debug_files else None
        
        if self.save_debug_files and self.debug_dir:
            try:
                self.debug_dir.mkdir(exist_ok=True)
                self.logger.info(f"Debug file logging enabled - saving to: {self.debug_dir}")
            except Exception as e:
                self.logger.warning(f"Could not create debug directory: {e}")
                self.save_debug_files = False
        
        self.logger.info(f"CodeGeneratorAgent initialized with agent_id: {agent_id}")
        self.logger.info(f"Detailed logging: {'ENABLED' if self.detailed_logging else 'DISABLED'}")
        self.logger.info(f"Debug file saving: {'ENABLED' if self.save_debug_files else 'DISABLED'}")
        self.logger.info(f"Step analysis: {'ENABLED' if self.step_analysis else 'DISABLED'}")
        self.logger.info(f"Rich formatting: {'AVAILABLE' if RICH_AVAILABLE else 'NOT AVAILABLE'}")

    def create_new_session(self, correlation_id: str) -> str:
        """Create a new session for this specific generation request"""
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

    def _log_generation_inputs(self, input_code: str, context: str, correlation_id: str, prompt: str):
        """Comprehensive logging of generation inputs"""
        
        # Basic stats logging
        self.logger.info(f"Starting generation for correlation: {correlation_id}")
        self.logger.info(f"Input code length: {len(input_code)} characters")
        self.logger.info(f"Context length: {len(context)} characters")
        self.logger.info(f"Has context: {'YES' if context.strip() else 'NO'}")
        
        # Safe preview logging
        self.logger.info(f"Input code preview: {repr(input_code[:200])}...")
        if context.strip():
            self.logger.info(f"Context preview: {repr(context[:300])}...")
        
        # Prompt statistics
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
        
        self.logger.info(f"Prompt statistics: {json.dumps(prompt_stats, indent=2)}")
        
        # Detailed logging
        if self.detailed_logging:
            self.logger.info(f"=== DETAILED GENERATION LOG START (correlation: {correlation_id}) ===")
            self.logger.info(f"Full input code:\n{'-' * 50}\n{input_code}\n{'-' * 50}")
            self.logger.info(f"Full context:\n{'-' * 50}\n{context or 'NO CONTEXT PROVIDED'}\n{'-' * 50}")
            self.logger.info(f"Full prompt being sent to LLM:\n{'-' * 50}\n{prompt}\n{'-' * 50}")
            self.logger.info(f"=== DETAILED GENERATION LOG END ===")

    def _log_generation_output(self, output: str, cleaned_output: str, correlation_id: str):
        """Log generation output details"""
        self.logger.info(f"Raw output length: {len(output)} characters")
        self.logger.info(f"Cleaned output length: {len(cleaned_output)} characters")
        self.logger.info(f"Output preview: {repr(cleaned_output[:200])}...")
        
        if self.detailed_logging:
            self.logger.info(f"=== OUTPUT DETAILS (correlation: {correlation_id}) ===")
            self.logger.info(f"Raw LLM output:\n{'-' * 50}\n{output}\n{'-' * 50}")
            self.logger.info(f"Cleaned playbook:\n{'-' * 50}\n{cleaned_output}\n{'-' * 50}")
            self.logger.info(f"=== OUTPUT DETAILS END ===")

    async def generate(self, input_code: str, context: Optional[str] = "", correlation_id: Optional[str] = None) -> str:
        """Generate Ansible playbook from input code and context"""
        correlation_id = correlation_id or str(uuid.uuid4())
        context = context or ""
        
        # Validate inputs
        if not input_code or not input_code.strip():
            raise ValueError("Input code cannot be empty")
        
        # Build the prompt with better structure
        prompt = (
            f"[CONTEXT]\n{context}\n\n"
            f"[INPUT CODE]\n{input_code}\n\n"
            "Convert the above into a single production-quality Ansible playbook. "
            "Requirements:\n"
            "1. Output ONLY valid YAML content\n"
            "2. Start with '---'\n"
            "3. Include proper Ansible playbook structure with hosts, tasks, etc.\n"
            "4. No markdown formatting, code blocks, or extra text\n"
            "5. Ensure all syntax is valid YAML and Ansible\n\n"
            "Output the Ansible playbook now:"
        )
        
        # Log all input details
        self._log_generation_inputs(input_code, context, correlation_id, prompt)
        
        try:
            # Create dedicated session for this generation
            generation_session_id = self.create_new_session(correlation_id)

            # Direct API call with better error handling
            messages = [UserMessage(role="user", content=prompt)]
            
            self.logger.info(f"Sending request to LLM (agent: {self.agent_id}, session: {generation_session_id})")
            
            # Set up the generator with timeout handling
            generator = self.client.agents.turn.create(
                agent_id=self.agent_id,
                session_id=generation_session_id,
                messages=messages,
                stream=True,
            )
            
            # Process streaming response with better error handling
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
                    
                    # Safety check - prevent infinite loops
                    if chunk_count > 1000:
                        self.logger.warning("Too many chunks received, breaking")
                        break
                        
            except Exception as stream_error:
                self.logger.error(f"Error during streaming: {stream_error}")
                raise RuntimeError(f"Streaming failed: {stream_error}")
            
            self.logger.info(f"Received {chunk_count} chunks from LLM (last event: {last_event_type})")
            
            if not turn:
                error_msg = f"No turn completed in response. Last event type: {last_event_type}, Chunk count: {chunk_count}"
                self.logger.error(error_msg)
                raise RuntimeError(error_msg)

            # Validate turn structure
            if not hasattr(turn, 'steps') or not turn.steps:
                self.logger.error("Turn has no steps")
                raise RuntimeError("Invalid turn structure - no steps found")
                
            if not hasattr(turn, 'output_message') or not turn.output_message:
                self.logger.error("Turn has no output message")
                raise RuntimeError("Invalid turn structure - no output message found")

            self.logger.info(f"Turn completed with {len(turn.steps)} steps")
            
            # Enhanced step analysis
            if self.step_analysis:
                step_printer(turn.steps, correlation_id)
            else:
                # Basic step logging with more details
                for i, step in enumerate(turn.steps):
                    step_type = type(step).__name__
                    self.logger.info(f"Step {i+1}: {step_type}")
                    
                    # Try to extract more information from each step
                    if hasattr(step, 'step_type'):
                        self.logger.info(f"   Step type: {step.step_type}")
                    if hasattr(step, 'tool_responses') and step.tool_responses:
                        self.logger.info(f"   Tool responses: {len(step.tool_responses)}")
                    if hasattr(step, 'api_model_response') and step.api_model_response:
                        if hasattr(step.api_model_response, 'content') and step.api_model_response.content:
                            content_preview = step.api_model_response.content[:100].replace('\n', ' ')
                            self.logger.info(f"   Model response preview: {content_preview}...")

            # Extract output with better validation
            if not hasattr(turn.output_message, 'content'):
                self.logger.error("Output message has no content attribute")
                raise RuntimeError("Invalid output message structure")
                
            output = turn.output_message.content
            
            if not output:
                self.logger.error("LLM returned empty output")
                # Try to extract from steps as fallback
                for step in turn.steps:
                    if hasattr(step, 'api_model_response') and step.api_model_response:
                        if hasattr(step.api_model_response, 'content') and step.api_model_response.content:
                            output = step.api_model_response.content
                            self.logger.info("Recovered output from step response")
                            break
                
                if not output:
                    raise RuntimeError("LLM returned empty output and no fallback found")
            
            # Clean and format the playbook
            try:
                cleaned_output = _clean_playbook_output(output)
            except ValueError as clean_error:
                self.logger.error(f"Failed to clean output: {clean_error}")
                raise RuntimeError(f"Output cleaning failed: {clean_error}")
            
            # Final validation
            if not cleaned_output or len(cleaned_output.strip()) < 10:
                raise RuntimeError("Cleaned output is too short or empty")
            
            # Log output details
            self._log_generation_output(output, cleaned_output, correlation_id)
            
            self.logger.info(f"Generation completed successfully for correlation: {correlation_id}")
            return cleaned_output
            
        except Exception as e:
            self.logger.error(f"Playbook generation failed for correlation {correlation_id}: {str(e)}")
            
            # Enhanced error information
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
            
            # Re-raise with more context
            raise RuntimeError(f"Playbook generation failed for {correlation_id}: {str(e)}")

    async def generate_stream(self, input_code: str, context: Optional[str] = "", correlation_id: Optional[str] = None) -> AsyncGenerator[Dict[str, Any], None]:
        """Generate playbook with streaming updates"""
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
        """Get current status of the code generator agent"""
        return {
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "client_base_url": str(self.client.base_url) if hasattr(self.client, 'base_url') else "unknown",
            "timeout": self.timeout,
            "status": "ready",
            "pattern": "LSS API",
            "logging_config": {
                "detailed_logging": self.detailed_logging,
                "debug_file_saving": self.save_debug_files,
                "step_analysis": self.step_analysis,
                "rich_formatting": RICH_AVAILABLE,
                "debug_directory": str(self.debug_dir) if self.debug_dir else None
            }
        }

    async def health_check(self) -> bool:
        """Perform a health check on the code generator agent"""
        try:
            # Simple test message
            test_correlation = f"health-check-{uuid.uuid4()}"
            messages = [UserMessage(role="user", content="Respond with: HEALTH_CHECK_OK")]
            
            generator = self.client.agents.turn.create(
                agent_id=self.agent_id,
                session_id=self.session_id,
                messages=messages,
                stream=True,
            )
            
            # Check if we can get at least one chunk
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