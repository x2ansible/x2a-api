import logging
import uuid
import json
import time
import re
from typing import Optional, Dict, Any, List, AsyncGenerator
from json import JSONDecodeError

from llama_stack_client import LlamaStackClient
from llama_stack_client.types import UserMessage

try:
    from rich.pretty import pprint
    from termcolor import cprint
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

logger = logging.getLogger("ValidationAgent")

def _format_lint_issues(issues: List[Dict[str, Any]]) -> str:
    """Format lint issues into a readable string"""
    if not issues:
        return "No issues found."
    
    formatted = []
    for issue in issues:
        if isinstance(issue, dict):
            rule = issue.get("rule", "unknown")
            message = issue.get("message", str(issue))
            severity = issue.get("severity", "info")
            filename = issue.get("filename", "")
            line = issue.get("line", "")
            
            location = f"{filename}:{line}" if filename and line else filename or "unknown"
            formatted.append(f"[{severity.upper()}] {rule}: {message} ({location})")
        else:
            formatted.append(str(issue))
    
    return "\n".join(formatted)

def _get_lint_result_from_tool_response_content(content: str):
    """Extract lint result from tool response content"""
    logger.debug(f"🔍 _get_lint_result_from_tool_response_content called with content length: {len(content)}")
    
    try:
        # Parse the outer JSON structure
        parsed_content = json.loads(content)
        logger.debug(f"🔍 Successfully parsed JSON content")
        
        # Debug logging
        logger.debug(f"🔍 Parsed content keys: {list(parsed_content.keys()) if isinstance(parsed_content, dict) else 'not a dict'}")
        logger.debug(f"🔍 Parsed content type: {type(parsed_content)}")
        
        # Check if this is the wrapper structure with 'text' field
        if isinstance(parsed_content, dict) and "text" in parsed_content:
            text_content = parsed_content["text"]
            logger.debug(f"🔍 Found text field with length: {len(str(text_content))}")
            logger.debug(f"🔍 Text field type: {type(text_content)}")
            
            # Parse the nested JSON that contains the actual lint result
            if isinstance(text_content, str):
                try:
                    nested_result = json.loads(text_content)
                    logger.debug(f"🔍 Successfully parsed nested JSON")
                    logger.debug(f"🔍 Nested result keys: {list(nested_result.keys()) if isinstance(nested_result, dict) else 'not a dict'}")
                    logger.debug(f"🔍 Nested result type: {type(nested_result)}")
                    
                    # This should be the actual lint result with 'tool', 'output', etc.
                    if isinstance(nested_result, dict) and "tool" in nested_result:
                        logger.debug("🔍 Found valid lint result structure with 'tool' key")
                        logger.debug(f"🔍 Tool name: {nested_result.get('tool')}")
                        return nested_result
                    else:
                        logger.warning("🔍 Nested result doesn't have expected 'tool' key structure")
                        logger.debug(f"🔍 Available keys in nested result: {list(nested_result.keys()) if isinstance(nested_result, dict) else 'not a dict'}")
                        return nested_result
                        
                except json.JSONDecodeError as e:
                    logger.warning(f"🔍 Failed to parse nested JSON: {e}")
                    logger.debug(f"🔍 Raw text content preview: {str(text_content)[:200]}...")
                    return {"raw_text": text_content}
            else:
                logger.warning(f"🔍 Text field is not a string, it's: {type(text_content)}")
                return text_content
        
        # Check if it's already the lint result structure
        elif isinstance(parsed_content, dict) and "tool" in parsed_content and "output" in parsed_content:
            logger.debug("🔍 Direct lint result structure found")
            logger.debug(f"🔍 Direct result tool: {parsed_content.get('tool')}")
            logger.debug(f"🔍 Direct result output keys: {list(parsed_content.get('output', {}).keys())}")
            return parsed_content
        
        # Fallback - return as is
        else:
            logger.debug("🔍 Using parsed content as-is (no recognized structure)")
            logger.debug(f"🔍 Fallback content keys: {list(parsed_content.keys()) if isinstance(parsed_content, dict) else 'not a dict'}")
            return parsed_content
        
    except json.JSONDecodeError as e:
        logger.warning(f" Failed to parse tool_response content as JSON: {e}")
        logger.debug(f"🔍 Raw content preview (first 500 chars): {content[:500]}...")
        logger.debug(f"🔍 Raw content preview (last 100 chars): ...{content[-100:]}")
        return None
    except Exception as e:
        logger.error(f" Unexpected error parsing tool response: {e}")
        logger.debug(f"🔍 Exception type: {type(e)}")
        logger.debug(f"🔍 Content type: {type(content)}")
        return None

def _step_printer(steps, logger_instance=None):
    """Print the steps of an agent's response in a formatted way (optional debugging)"""
    if not RICH_AVAILABLE:
        if logger_instance:
            logger_instance.info("📝 Rich/termcolor not available - skipping step printing")
        return
    
    logger_instance.debug(f"🔍 _step_printer called with {len(steps)} steps")
    
    for i, step in enumerate(steps):
        step_type = type(step).__name__
        logger_instance.debug(f"🔍 Printing step {i+1}/{len(steps)}: {step_type}")
        print("\n"+"-" * 10, f"📍 Step {i+1}: {step_type}","-" * 10)
        
        if step_type == "ToolExecutionStep":
            print("🔧 Executing tool...")
            logger_instance.debug(f"🔍 ToolExecutionStep details - hasattr tool_responses: {hasattr(step, 'tool_responses')}")
            try:
                if hasattr(step, 'tool_responses') and step.tool_responses:
                    logger_instance.debug(f"🔍 Found {len(step.tool_responses)} tool responses")
                    response_content = step.tool_responses[0].content
                    logger_instance.debug(f"🔍 Response content length: {len(response_content)}")
                    try:
                        parsed_content = json.loads(response_content)
                        logger_instance.debug(f"🔍 Successfully parsed response content for display")
                        pprint(parsed_content)
                    except (TypeError, JSONDecodeError) as e:
                        logger_instance.debug(f"🔍 Could not parse response as JSON ({e}), showing raw content")
                        pprint(response_content)
                else:
                    print("No tool responses found")
                    logger_instance.debug("🔍 No tool responses found in ToolExecutionStep")
            except Exception as e:
                print(f"Error displaying tool response: {e}")
                logger_instance.error(f" Error in _step_printer for ToolExecutionStep: {e}")
        else:
            # Handle inference steps
            logger_instance.debug(f"🔍 Processing non-tool step: {step_type}")
            logger_instance.debug(f"🔍 Step attributes: {[attr for attr in dir(step) if not attr.startswith('_')]}")
            
            if hasattr(step, 'api_model_response') and step.api_model_response:
                logger_instance.debug(f"🔍 Found api_model_response")
                if hasattr(step.api_model_response, 'content') and step.api_model_response.content:
                    print("🤖 Model Response:")
                    logger_instance.debug(f"🔍 Model response content length: {len(step.api_model_response.content)}")
                    cprint(f"{step.api_model_response.content}\n", "magenta")
                elif hasattr(step.api_model_response, 'tool_calls') and step.api_model_response.tool_calls:
                    tool_call = step.api_model_response.tool_calls[0]
                    print("🛠️ Tool call Generated:")
                    logger_instance.debug(f"🔍 Tool call name: {tool_call.tool_name}")
                    logger_instance.debug(f"🔍 Tool call arguments length: {len(tool_call.arguments_json)}")
                    try:
                        args = json.loads(tool_call.arguments_json)
                        cprint(f"Tool call: {tool_call.tool_name}, Arguments: {args}", "magenta")
                        logger_instance.debug(f"🔍 Successfully parsed tool call arguments")
                    except Exception as e:
                        cprint(f"Tool call: {tool_call.tool_name}, Arguments: {tool_call.arguments_json}", "magenta")
                        logger_instance.debug(f"🔍 Could not parse tool call arguments as JSON: {e}")
            else:
                logger_instance.debug(f"🔍 No api_model_response found for step {step_type}")
    
    print("="*10, "Query processing completed","="*10,"\n")
    logger_instance.debug("🔍 _step_printer completed")

class ValidationAgent:
    """
    ValidationAgent
    Uses pre-registered agent with mcp::ansible_lint tool configured
    """
    
    def __init__(self, client: LlamaStackClient, agent_id: str, session_id: str, 
                 timeout: int = 60, verbose_logging: bool = False):
        """Initialize ValidationAgent with required parameters"""
        logger.info(f"🚀 Initializing ValidationAgent")
        logger.debug(f"🔍 Init params - agent_id: {agent_id}, session_id: {session_id}, timeout: {timeout}, verbose: {verbose_logging}")
        
        self.client = client
        self.agent_id = agent_id
        self.session_id = session_id
        self.timeout = timeout
        self.verbose_logging = verbose_logging
        self.logger = logger
        
        # Enable debug logging if verbose is requested
        if verbose_logging:
            self.logger.setLevel(logging.DEBUG)
            logger.debug("🔍 Debug logging enabled via verbose_logging flag")
        
        # Configuration
        self.supported_profiles = ["basic", "moderate", "safety", "shared", "production"]
        
        self.logger.info(f"🔍 ValidationAgent initialized with agent_id: {agent_id} (registry pattern)")
        self.logger.debug(f"🔍 Client base URL: {getattr(client, 'base_url', 'unknown')}")
        self.logger.debug(f"🔍 Supported profiles: {self.supported_profiles}")
        
        if verbose_logging:
            self.logger.debug("🔍 Debug logging enabled")

    def create_new_session(self, correlation_id: str) -> str:
        """Create a new session for this specific validation query"""
        logger.debug(f"🔍 create_new_session called with correlation_id: {correlation_id}")
        
        try:
            session_name = f"validation-{correlation_id}-{uuid.uuid4()}"
            logger.debug(f"🔍 Creating session with name: {session_name}")
            
            response = self.client.agents.session.create(
                agent_id=self.agent_id,
                session_name=session_name,
            )
            session_id = response.session_id
            
            self.logger.info(f"📱 Created new session: {session_id} for correlation: {correlation_id}")
            logger.debug(f"🔍 Session creation response type: {type(response)}")
            logger.debug(f"🔍 Session creation response attributes: {[attr for attr in dir(response) if not attr.startswith('_')]}")
            
            return session_id
        except Exception as e:
            self.logger.error(f" Failed to create session: {e}")
            logger.debug(f"🔍 Session creation exception type: {type(e)}")
            logger.debug(f"🔍 Session creation exception details: {str(e)}")
            
            # Fallback to default session
            self.logger.info(f"↩️ Falling back to default session: {self.session_id}")
            logger.debug(f"🔍 Fallback session_id: {self.session_id}")
            return self.session_id

    async def debug_tools(self) -> Dict[str, Any]:
        """Debug function to check tool availability and MCP registration"""
        logger.info("🔧 Starting debug_tools check")
        
        try:
            import httpx
            
            # Direct HTTP calls to check MCP tool availability
            base_url = self.client.base_url
            logger.debug(f"🔍 Using base_url: {base_url}")
            
            # Get toolgroups
            toolgroups_url = f"{base_url}/v1/toolgroups"
            logger.debug(f"🔍 Fetching toolgroups from: {toolgroups_url}")
            
            toolgroups_response = httpx.get(toolgroups_url, timeout=30)
            logger.debug(f"🔍 Toolgroups response status: {toolgroups_response.status_code}")
            
            toolgroups_data = toolgroups_response.json() if toolgroups_response.status_code == 200 else {"data": []}
            available_toolgroups = [tg.get("identifier", tg.get("toolgroup_id", "unknown")) for tg in toolgroups_data.get("data", [])]
            logger.debug(f"🔍 Found {len(available_toolgroups)} toolgroups")
            
            # Get tools
            tools_url = f"{base_url}/v1/tools"
            logger.debug(f"🔍 Fetching tools from: {tools_url}")
            
            tools_response = httpx.get(tools_url, timeout=30)
            logger.debug(f"🔍 Tools response status: {tools_response.status_code}")
            
            tools_data = tools_response.json() if tools_response.status_code == 200 else {"data": []}
            available_tools = []
            
            for tool in tools_data.get("data", []):
                tool_name = tool.get("tool_name") or tool.get("name") or tool.get("identifier") or "unknown"
                available_tools.append(tool_name)
                logger.debug(f"🔍 Found tool: {tool_name}")
            
            # Filter for relevant tools
            ansible_tools = [t for t in available_tools if 'ansible' in t.lower()]
            mcp_tools = [t for t in available_tools if 'mcp::' in t.lower()]
            
            self.logger.info(f"🔧 Available toolgroups: {available_toolgroups}")
            self.logger.info(f"🔧 Available tools: {available_tools}")
            self.logger.info(f"🔧 Ansible tools: {ansible_tools}")
            self.logger.info(f"🔧 MCP tools: {mcp_tools}")
            
            logger.debug(f"🔍 Toolgroups count: {len(available_toolgroups)}")
            logger.debug(f"🔍 Tools count: {len(available_tools)}")
            logger.debug(f"🔍 Ansible tools count: {len(ansible_tools)}")
            logger.debug(f"🔍 MCP tools count: {len(mcp_tools)}")
            
            return {
                "available_tools": available_tools,
                "available_toolgroups": available_toolgroups,
                "ansible_tools": ansible_tools,
                "mcp_tools": mcp_tools,
                "mcp_ansible_lint_toolgroup_available": "mcp::ansible_lint" in available_toolgroups,
                "mcp_ansible_lint_tool_available": "mcp::ansible_lint" in available_tools,
                "agent_id": self.agent_id,
                "debug_info": {
                    "toolgroups_count": len(available_toolgroups),
                    "tools_count": len(available_tools),
                    "toolgroups_response_code": toolgroups_response.status_code,
                    "tools_response_code": tools_response.status_code,
                    "base_url": base_url
                }
            }
        except Exception as e:
            self.logger.error(f" Tool debug failed: {e}")
            logger.debug(f"🔍 Debug tools exception type: {type(e)}")
            logger.debug(f"🔍 Debug tools exception details: {str(e)}")
            return {"error": str(e)}

    async def validate_playbook(
        self, 
        playbook_content: str, 
        profile: str = "basic", 
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Validate playbook using registry pattern - main validation method"""
        correlation_id = correlation_id or str(uuid.uuid4())
        start_time = time.time()
        
        logger.info(f"🔍 validate_playbook started")
        logger.debug(f"🔍 Correlation ID: {correlation_id}")
        logger.debug(f"🔍 Profile: {profile}")
        logger.debug(f"🔍 Playbook content length: {len(playbook_content)}")
        logger.debug(f"🔍 Start time: {start_time}")
        
        # Validate profile
        if profile not in self.supported_profiles:
            error_msg = f"Unsupported profile: {profile}. Supported: {self.supported_profiles}"
            logger.error(f" {error_msg}")
            raise ValueError(error_msg)
        
        logger.debug(f"🔍 Profile validation passed")
        
        self.logger.info(f"🔍 Validating playbook with {profile} profile (correlation: {correlation_id})")
        
        try:
            # Create dedicated session for this validation query
            logger.debug(f"🔍 Creating dedicated session for validation")
            query_session_id = self.create_new_session(correlation_id)
            logger.debug(f"🔍 Using session ID: {query_session_id}")

            # Construct user prompt that explicitly requests tool usage
            logger.debug(f"🔍 Building validation prompt")
            user_prompt = self._build_validation_prompt(playbook_content, profile)
            logger.debug(f"🔍 User prompt length: {len(user_prompt)}")
            logger.debug(f"🔍 User prompt preview: {user_prompt[:200]}...")
            
            self.logger.info(f"📬 Sending validation query to registered agent")
            
            # Use registry pattern - same as ContextAgent
            messages = [UserMessage(role="user", content=user_prompt)]
            logger.debug(f"🔍 Created {len(messages)} messages")
            
            # Create turn with timeout handling
            logger.debug(f"🔍 Creating turn with agent_id: {self.agent_id}, session_id: {query_session_id}")
            
            generator = self.client.agents.turn.create(
                agent_id=self.agent_id,
                session_id=query_session_id,
                messages=messages,
                stream=True,
            )
            
            logger.debug(f"🔍 Turn generator created, starting to process streaming response")
            
            # Process streaming response with timeout
            turn = None
            timeout_seconds = min(self.timeout, 120)  # Cap at 2 minutes
            timeout_start = time.time()
            chunk_count = 0
            
            logger.debug(f"🔍 Processing streaming response with timeout: {timeout_seconds}s")
            
            for chunk in generator:
                chunk_count += 1
                current_time = time.time()
                elapsed = current_time - timeout_start
                
                logger.debug(f"🔍 Processing chunk {chunk_count}, elapsed: {elapsed:.2f}s")
                
                # Check for timeout
                if elapsed > timeout_seconds:
                    logger.warning(f"⚠️ Turn processing timeout after {timeout_seconds}s (chunk {chunk_count})")
                    raise TimeoutError(f"Validation timeout after {timeout_seconds} seconds")
                
                event = chunk.event
                event_type = event.payload.event_type
                logger.debug(f"🔍 Chunk {chunk_count}: event_type = {event_type}")
                
                if event_type == "turn_complete":
                    turn = event.payload.turn
                    logger.debug(f"🔍 Turn completed at chunk {chunk_count}")
                    break
            
            logger.debug(f"🔍 Streaming processing completed. Total chunks: {chunk_count}")
            
            if not turn:
                error_msg = "No turn completed in response"
                self.logger.error(f" {error_msg}")
                logger.debug(f"🔍 Turn object is None after processing {chunk_count} chunks")
                raise RuntimeError(error_msg)

            # Log steps for debugging
            steps_count = len(turn.steps) if hasattr(turn, 'steps') else 0
            self.logger.info(f"📊 Turn completed with {steps_count} steps")
            logger.debug(f"🔍 Turn object type: {type(turn)}")
            logger.debug(f"🔍 Turn attributes: {[attr for attr in dir(turn) if not attr.startswith('_')]}")
            
            for i, step in enumerate(turn.steps if hasattr(turn, 'steps') else []):
                step_type = getattr(step, 'step_type', type(step).__name__)
                self.logger.info(f"📋 Step {i+1}: {step_type}")
                logger.debug(f"🔍 Step {i+1} type: {type(step)}")
                logger.debug(f"🔍 Step {i+1} attributes: {[attr for attr in dir(step) if not attr.startswith('_')]}")

            # Add step printing for debugging (optional)
            if self.verbose_logging:
                logger.debug(f"🔍 Verbose logging enabled, calling _step_printer")
                _step_printer(turn.steps if hasattr(turn, 'steps') else [], self.logger)

            # Process response
            total_time = time.time() - start_time
            logger.debug(f"🔍 Processing validation response, total elapsed: {total_time:.3f}s")
            
            result = await self._process_validation_response(turn, correlation_id, profile, total_time)
            logger.debug(f"🔍 Validation response processed successfully")
            logger.debug(f"🔍 Result keys: {list(result.keys())}")
            
            return result
            
        except TimeoutError as e:
            total_time = time.time() - start_time
            self.logger.error(f"⏰ Validation timeout after {total_time:.3f}s: {str(e)}")
            logger.debug(f"🔍 TimeoutError details: {str(e)}")
            return {
                "success": False,
                "correlation_id": correlation_id,
                "profile": profile,
                "error": f"Validation timeout: {str(e)}",
                "summary": {"passed": False},
                "issues_count": 0,
                "issues": [],
                "formatted_issues": f"Validation timed out after {total_time:.1f} seconds",
                "elapsed_time": total_time,
                "timeout": True
            }
        except Exception as e:
            total_time = time.time() - start_time
            self.logger.error(f" Validation failed after {total_time:.3f}s: {str(e)}")
            logger.debug(f"🔍 Exception type: {type(e)}")
            logger.debug(f"🔍 Exception details: {str(e)}")
            return {
                "success": False,
                "correlation_id": correlation_id,
                "profile": profile,
                "error": str(e),
                "summary": {"passed": False},
                "issues_count": 0,
                "issues": [],
                "formatted_issues": f"Validation failed: {str(e)}",
                "elapsed_time": total_time
            }

    def _build_validation_prompt(self, playbook_content: str, profile: str) -> str:
        """Build effective user prompt that explicitly requests tool usage"""
        logger.debug(f"🔍 _build_validation_prompt called")
        logger.debug(f"🔍 Profile: {profile}")
        logger.debug(f"🔍 Playbook content length: {len(playbook_content)}")
        
        # NEW: Log the full playbook content being validated
        logger.debug(f"🔍 === FULL PLAYBOOK CONTENT START ===")
        logger.debug(f"🔍 Full playbook being validated:")
        logger.debug(f"--------------------------------------------------")
        logger.debug(playbook_content)
        logger.debug(f"--------------------------------------------------")
        logger.debug(f"🔍 === FULL PLAYBOOK CONTENT END ===")
        
        # Check playbook size to prevent timeouts
        max_size = 50000  # 50KB limit
        if len(playbook_content) > max_size:
            error_msg = f"Playbook too large ({len(playbook_content)} chars). Maximum size: {max_size} characters"
            logger.error(f" {error_msg}")
            raise ValueError(error_msg)
        
        logger.debug(f"🔍 Playbook size check passed")
        
        # Add newline to playbook content if missing (fixes common issue)
        original_length = len(playbook_content)
        if not playbook_content.endswith('\n'):
            playbook_content += '\n'
            self.logger.debug("🔧 Added missing newline to playbook content")
            logger.debug(f"🔍 Playbook length changed from {original_length} to {len(playbook_content)}")
        
        prompt = f"""Please validate this Ansible playbook using ansible-lint with the {profile} profile.

IMPORTANT: You must use the ansible-lint tool to perform the validation. Do not attempt to validate manually.

Playbook to validate:
```yaml
{playbook_content}```

Please:
1. Use the ansible-lint tool to analyze this playbook
2. Report any issues found
3. Provide a summary of the validation results

Profile: {profile}"""
        
        logger.debug(f"🔍 Built prompt with length: {len(prompt)}")
        return prompt

    async def _process_validation_response(self, turn, correlation_id: str, profile: str, elapsed_time: float) -> Dict[str, Any]:
        """Process validation response with proper error handling and issue detection"""
        logger.debug(f"🔍 _process_validation_response called")
        logger.debug(f"🔍 Correlation ID: {correlation_id}")
        logger.debug(f"🔍 Profile: {profile}")
        logger.debug(f"🔍 Elapsed time: {elapsed_time:.3f}s")
        
        found_lint = False
        tool_results = []
        
        if hasattr(turn, "steps"):
            steps_count = len(turn.steps)
            logger.debug(f"🔍 Processing {steps_count} steps")
            
            for idx, step in enumerate(turn.steps):
                step_type = getattr(step, "step_type", type(step).__name__)
                self.logger.info(f"📋 Processing step {idx+1}: {step_type}")
                logger.debug(f"🔍 Step {idx+1}/{steps_count}: {step_type}")
                logger.debug(f"🔍 Step {idx+1} object type: {type(step)}")
                
                # Look for tool execution steps
                if step_type in ["tool_execution", "ToolExecutionStep"] or "tool" in step_type.lower():
                    self.logger.info("🔧 Found tool execution step!")
                    logger.debug(f"🔍 Tool execution step found at index {idx}")
                    logger.debug(f"🔍 Step has tool_responses attr: {hasattr(step, 'tool_responses')}")
                    
                    if hasattr(step, "tool_responses") and step.tool_responses:
                        responses_count = len(step.tool_responses)
                        self.logger.info(f"📥 Found {responses_count} tool responses")
                        logger.debug(f"🔍 Processing {responses_count} tool responses")
                        
                        for resp_idx, tool_response in enumerate(step.tool_responses):
                            content = getattr(tool_response, "content", "")
                            content_length = len(content)
                            
                            logger.debug(f"🔍 Tool response {resp_idx+1}/{responses_count} content length: {content_length}")
                            self.logger.debug(f"🔍 Raw tool response content preview: {content[:200]}...")
                            
                            lint_json = _get_lint_result_from_tool_response_content(content)
                            if lint_json:
                                found_lint = True
                                tool_results.append(lint_json)
                                self.logger.info(" Successfully parsed lint result!")
                                logger.debug(f"🔍 Lint JSON keys: {list(lint_json.keys()) if isinstance(lint_json, dict) else 'not a dict'}")
                                
                                # Debug log the parsed result structure
                                self.logger.debug(f"🔍 Parsed lint_json keys: {list(lint_json.keys())}")
                                if "output" in lint_json:
                                    output = lint_json["output"]
                                    self.logger.debug(f"🔍 Output keys: {list(output.keys())}")
                                    if "summary" in output:
                                        summary = output["summary"]
                                        self.logger.debug(f"🔍 Summary content: {summary}")
                                        self.logger.debug(f"🔍 Exit code from summary: {summary.get('exit_code')}")
                                        self.logger.debug(f"🔍 Passed from summary: {summary.get('passed')}")
                            else:
                                # Even if we can't parse JSON, we found tool execution
                                found_lint = True
                                raw_result = {
                                    "raw_output": content,
                                    "success": True,
                                    "output": {"raw_output": {"stdout": content}}
                                }
                                tool_results.append(raw_result)
                                self.logger.info(" Found tool execution with raw output")
                                logger.debug(f"🔍 Using raw output result for response {resp_idx+1}")
                    else:
                        self.logger.warning("⚠️ tool_execution step has no tool_responses")
                        logger.debug(f"🔍 Tool execution step at index {idx} has no tool_responses")
                        logger.debug(f"🔍 Step attributes: {[attr for attr in dir(step) if not attr.startswith('_')]}")
                
                # Also check for tool calls in inference steps
                elif step_type in ["inference", "InferenceStep"]:
                    logger.debug(f"🔍 Processing inference step at index {idx}")
                    logger.debug(f"🔍 Step has api_model_response: {hasattr(step, 'api_model_response')}")
                    
                    if hasattr(step, "api_model_response") and step.api_model_response:
                        logger.debug(f"🔍 Found api_model_response")
                        logger.debug(f"🔍 api_model_response has tool_calls: {hasattr(step.api_model_response, 'tool_calls')}")
                        
                        if hasattr(step.api_model_response, "tool_calls") and step.api_model_response.tool_calls:
                            tool_calls_count = len(step.api_model_response.tool_calls)
                            self.logger.info(f"🛠️ Found {tool_calls_count} tool calls in inference step")
                            logger.debug(f"🔍 Processing {tool_calls_count} tool calls")
                            
                            for tc_idx, tool_call in enumerate(step.api_model_response.tool_calls):
                                tool_name = getattr(tool_call, 'tool_name', 'unknown')
                                self.logger.info(f"Tool call: {tool_name}")
                                logger.debug(f"🔍 Tool call {tc_idx+1}/{tool_calls_count}: {tool_name}")
                                logger.debug(f"🔍 Tool call attributes: {[attr for attr in dir(tool_call) if not attr.startswith('_')]}")
                else:
                    logger.debug(f"🔍 Skipping step {idx+1} with type: {step_type}")
        else:
            logger.warning("⚠️ Turn object has no 'steps' attribute")
            logger.debug(f"🔍 Turn attributes: {[attr for attr in dir(turn) if not attr.startswith('_')]}")
        
        logger.debug(f"🔍 Step processing completed. found_lint: {found_lint}, tool_results count: {len(tool_results)}")
        
        if found_lint and tool_results:
            # Process results using the corrected logic
            lint_json = tool_results[0]  # Use first result
            logger.debug(f"🔍 Using first tool result for processing")
            
            self.logger.debug(f"🔍 Processing lint_json: {list(lint_json.keys())}")
            
            # Handle different result structures - CRITICAL: Handle the actual MCP response structure
            if "output" in lint_json:
                output = lint_json["output"]
                summary = output.get("summary", {})
                issues = output.get("issues", [])
                raw_output = output.get("raw_output", {})
                self.logger.debug(f"🔍 Using 'output' structure - summary: {summary}")
                logger.debug(f"🔍 Output structure - summary keys: {list(summary.keys())}")
                logger.debug(f"🔍 Output structure - issues count: {len(issues)}")
                logger.debug(f"🔍 Output structure - raw_output keys: {list(raw_output.keys())}")
            else:
                # Fallback structure
                summary = lint_json.get("summary", {})
                issues = lint_json.get("issues", [])
                raw_output = lint_json.get("raw_output", {})
                self.logger.debug(f"🔍 Using fallback structure - summary: {summary}")
                logger.debug(f"🔍 Fallback structure - summary keys: {list(summary.keys())}")
                logger.debug(f"🔍 Fallback structure - issues count: {len(issues)}")
                logger.debug(f"🔍 Fallback structure - raw_output keys: {list(raw_output.keys())}")
            
            # CRITICAL FIX: Get the ACTUAL exit code and status from the MCP tool response
            actual_exit_code = summary.get("exit_code", 0)
            tool_passed = summary.get("passed", True)  # Default to True only if no exit_code info
            
            self.logger.debug(f"🔍 Extracted values - exit_code: {actual_exit_code}, tool_passed: {tool_passed}")
            logger.debug(f"🔍 Raw summary data: {summary}")
            
            # Override tool_passed if exit_code indicates failure
            if actual_exit_code > 0:
                tool_passed = False
                self.logger.debug(f"🔍 Overriding tool_passed to False due to exit_code: {actual_exit_code}")
            
            # Calculate actual issues count
            actual_issues_count = len(issues)
            logger.debug(f"🔍 Initial issues count from array: {actual_issues_count}")
            
            # If exit_code > 0 but no issues in array, parse from raw output
            if actual_exit_code > 0 and actual_issues_count == 0:
                stdout = raw_output.get("stdout", "")
                stderr = raw_output.get("stderr", "")
                
                self.logger.debug(f"🔍 Parsing issues from raw output - stdout length: {len(stdout)}, stderr length: {len(stderr)}")
                logger.debug(f"🔍 stdout preview: {stdout[:200]}...")
                logger.debug(f"🔍 stderr preview: {stderr[:200]}...")
                
                # Count issues from stderr
                if "Failed:" in stderr:
                    failed_match = re.search(r'Failed: (\d+) failure', stderr)
                    if failed_match:
                        actual_issues_count = int(failed_match.group(1))
                        self.logger.debug(f"🔍 Found {actual_issues_count} issues from stderr regex")
                elif stdout.strip():  # At least one issue if stdout has content
                    actual_issues_count = 1
                    self.logger.debug(f"🔍 Found 1 issue from stdout content")
                else:
                    logger.debug(f"🔍 No issues found in raw output")
            
            # Determine if validation passed - MUST respect exit_code
            validation_passed = (actual_exit_code == 0) and tool_passed
            
            self.logger.debug(f"🔍 Final validation_passed: {validation_passed} (exit_code: {actual_exit_code}, tool_passed: {tool_passed})")
            logger.debug(f"🔍 Validation logic: exit_code==0: {actual_exit_code == 0}, tool_passed: {tool_passed}")
            
            # Format issues - use stdout if no structured issues
            if issues:
                formatted_issues = _format_lint_issues(issues)
                logger.debug(f"🔍 Using structured issues for formatting")
            elif raw_output.get("stdout"):
                formatted_issues = raw_output.get("stdout", "")
                logger.debug(f"🔍 Using raw stdout for formatted issues")
            else:
                formatted_issues = "No issues found" if validation_passed else "Validation failed"
                logger.debug(f"🔍 Using default message for formatted issues")
            
            logger.debug(f"🔍 Formatted issues length: {len(formatted_issues)}")
            
            result = {
                "success": lint_json.get("success", True),
                "correlation_id": correlation_id,
                "profile": profile,
                "summary": summary,
                "issues_count": actual_issues_count,
                "issues": issues,
                "formatted_issues": formatted_issues,
                "passed": validation_passed,
                "raw_stdout": raw_output.get("stdout", ""),
                "raw_stderr": raw_output.get("stderr", ""),
                "tool_response": lint_json,
                "tool": lint_json.get("tool", "mcp::ansible_lint"),
                "elapsed_time": elapsed_time,
                "session_info": {
                    "agent_id": self.agent_id,
                    "pattern": "Registry-based"
                }
            }
            
            self.logger.info(f" Validation completed: {actual_issues_count} issues found (exit_code: {actual_exit_code}, passed: {validation_passed})")
            logger.debug(f"🔍 Final result keys: {list(result.keys())}")
            logger.debug(f"🔍 Result success: {result['success']}")
            logger.debug(f"🔍 Result passed: {result['passed']}")
            
            return result
        else:
            # Enhanced fallback - check if there's useful content in output message
            fallback_content = ""
            if hasattr(turn, 'output_message') and turn.output_message:
                fallback_content = turn.output_message.content.strip()
                logger.debug(f"🔍 Found output_message content length: {len(fallback_content)}")
            else:
                logger.debug(f"🔍 No output_message found in turn")
            
            self.logger.warning("⚠️ No tool execution found - using fallback response")
            logger.debug(f"🔍 Fallback - found_lint: {found_lint}, tool_results: {len(tool_results)}")
            
            debug_info = {
                "steps_found": len(turn.steps) if hasattr(turn, 'steps') else 0,
                "step_types": [getattr(step, 'step_type', type(step).__name__) for step in turn.steps] if hasattr(turn, 'steps') else [],
                "found_lint": found_lint,
                "tool_results_count": len(tool_results)
            }
            logger.debug(f"🔍 Debug info: {debug_info}")
            
            return {
                "success": False,
                "correlation_id": correlation_id,
                "profile": profile,
                "error": "No tool execution results found",
                "summary": {"passed": False},
                "issues_count": 0,
                "issues": [],
                "formatted_issues": fallback_content if fallback_content else "No tool execution occurred - check agent configuration",
                "elapsed_time": elapsed_time,
                "session_info": {
                    "agent_id": self.agent_id,
                    "pattern": "Registry-based"
                },
                "debug_info": debug_info
            }

    async def validate_playbook_stream(
        self, 
        playbook_content: str, 
        profile: str = "basic", 
        correlation_id: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Validate playbook with streaming updates"""
        correlation_id = correlation_id or str(uuid.uuid4())
        logger.debug(f"🔍 validate_playbook_stream called with correlation_id: {correlation_id}")
        
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
            logger.debug(f"🔍 Sent initial progress message")

            result = await self.validate_playbook(playbook_content, profile, correlation_id)
            logger.debug(f"🔍 Validation completed, sending final result")
            
            yield {
                "type": "final_result",
                "data": result,
                "correlation_id": correlation_id
            }
            logger.debug(f"🔍 Sent final result")
        except Exception as e:
            logger.error(f" Stream validation error: {e}")
            logger.debug(f"🔍 Stream exception type: {type(e)}")
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
        """Quick syntax validation using basic profile"""
        logger.debug(f"🔍 validate_syntax called")
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
        """Production-ready validation with strict rules"""
        logger.debug(f"🔍 production_validate called")
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
        """Validate multiple playbook files"""
        correlation_id = correlation_id or str(uuid.uuid4())
        logger.debug(f"🔍 validate_multiple_files called with {len(files)} files")
        logger.debug(f"🔍 Files: {list(files.keys())}")
        
        results = {}
        
        for filename, content in files.items():
            self.logger.info(f"🔍 Validating file: {filename}")
            file_correlation = f"{correlation_id}-{filename}"
            logger.debug(f"🔍 Processing file {filename} with correlation: {file_correlation}")
            logger.debug(f"🔍 File content length: {len(content)}")
            
            try:
                result = await self.validate_playbook(content, profile, file_correlation)
                result["filename"] = filename
                results[filename] = result
                logger.debug(f"🔍 Successfully validated {filename}")
            except Exception as e:
                self.logger.error(f" Failed to validate {filename}: {e}")
                logger.debug(f"🔍 Validation error for {filename}: {type(e)} - {str(e)}")
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
        
        logger.debug(f"🔍 Multiple files validation completed. Results: {len(results)}")
        return results

    async def health_check(self) -> bool:
        """Perform a health check on the validation agent"""
        logger.debug(f"🔍 health_check called")
        
        try:
            test_playbook = """---
- name: Health check playbook
  hosts: localhost
  tasks:
    - name: Test task
      debug:
        msg: "Health check"
"""
            logger.debug(f"🔍 Running health check with test playbook")
            
            result = await self.validate_playbook(test_playbook, "basic", "health-check")
            is_healthy = result.get("success") is not None
            
            self.logger.info(f"🏥 Validation health check: {' passed' if is_healthy else ' failed'}")
            logger.debug(f"🔍 Health check result success field: {result.get('success')}")
            logger.debug(f"🔍 Health check is_healthy: {is_healthy}")
            
            return is_healthy
            
        except Exception as e:
            self.logger.error(f" Validation health check failed: {e}")
            logger.debug(f"🔍 Health check exception: {type(e)} - {str(e)}")
            return False

    async def test_tool_availability(self) -> Dict[str, Any]:
        """Test if the MCP ansible_lint tool is available and working"""
        logger.debug(f"🔍 test_tool_availability called")
        
        try:
            # Try a simple validation to see if tool gets called
            test_playbook = """---
- hosts: localhost
  tasks:
    - debug: 
        msg: "test"
"""
            
            self.logger.info("🧪 Testing tool availability with simple playbook")
            logger.debug(f"🔍 Test playbook length: {len(test_playbook)}")
            
            result = await self.validate_playbook(test_playbook, "basic", "tool-test")
            
            tool_called = "tool_execution" in str(result) or result.get("tool_response") is not None
            logger.debug(f"🔍 Tool called detection: {tool_called}")
            logger.debug(f"🔍 Result contains tool_execution: {'tool_execution' in str(result)}")
            logger.debug(f"🔍 Result has tool_response: {result.get('tool_response') is not None}")
            
            test_result = {
                "tool_available": tool_called,
                "test_result": result,
                "agent_id": self.agent_id,
                "timestamp": time.time()
            }
            
            logger.debug(f"🔍 Tool availability test completed: {tool_called}")
            return test_result
        except Exception as e:
            self.logger.error(f" Tool availability test failed: {e}")
            logger.debug(f"🔍 Tool test exception: {type(e)} - {str(e)}")
            return {
                "tool_available": False,
                "error": str(e),
                "agent_id": self.agent_id,
                "timestamp": time.time()
            }

    def get_status(self) -> Dict[str, Any]:
        """Get current status of the validation agent"""
        logger.debug(f"🔍 get_status called")
        
        status = {
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "client_base_url": self.client.base_url,
            "timeout": self.timeout,
            "status": "ready",
            "pattern": "Registry-based",
            "tool": "mcp::ansible_lint",
            "supported_profiles": self.supported_profiles
        }
        
        logger.debug(f"🔍 Status: {status}")
        return status

    def get_supported_profiles(self) -> List[str]:
        """Get list of supported validation profiles"""
        logger.debug(f"🔍 get_supported_profiles called")
        return self.supported_profiles.copy()

    def get_profile_descriptions(self) -> Dict[str, str]:
        """Get descriptions of validation profiles"""
        logger.debug(f"🔍 get_profile_descriptions called")
        
        descriptions = {
            "basic": "Basic syntax and structure validation",
            "moderate": "Standard best practices checking", 
            "safety": "Security-focused validation rules",
            "shared": "Rules for shared/reusable playbooks",
            "production": "Strict production-ready validation"
        }
        
        logger.debug(f"🔍 Profile descriptions: {list(descriptions.keys())}")
        return descriptions