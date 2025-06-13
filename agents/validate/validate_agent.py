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
    try:
        # Parse the outer JSON structure
        parsed_content = json.loads(content)
        
        # Debug logging
        logger.debug(f"🔍 Parsed content keys: {list(parsed_content.keys()) if isinstance(parsed_content, dict) else 'not a dict'}")
        
        # Check if this is the wrapper structure with 'text' field
        if isinstance(parsed_content, dict) and "text" in parsed_content:
            text_content = parsed_content["text"]
            logger.debug(f"🔍 Found text field, parsing nested JSON...")
            
            # Parse the nested JSON that contains the actual lint result
            if isinstance(text_content, str):
                try:
                    nested_result = json.loads(text_content)
                    logger.debug(f"🔍 Nested result keys: {list(nested_result.keys()) if isinstance(nested_result, dict) else 'not a dict'}")
                    
                    # This should be the actual lint result with 'tool', 'output', etc.
                    if isinstance(nested_result, dict) and "tool" in nested_result:
                        logger.debug("🔍 Found valid lint result structure")
                        return nested_result
                    else:
                        logger.warning("🔍 Nested result doesn't have expected structure")
                        return nested_result
                        
                except json.JSONDecodeError as e:
                    logger.warning(f"🔍 Failed to parse nested JSON: {e}")
                    return {"raw_text": text_content}
            else:
                logger.warning("🔍 Text field is not a string")
                return text_content
        
        # Check if it's already the lint result structure
        elif isinstance(parsed_content, dict) and "tool" in parsed_content and "output" in parsed_content:
            logger.debug("🔍 Direct lint result structure found")
            return parsed_content
        
        # Fallback - return as is
        else:
            logger.debug("🔍 Using parsed content as-is")
            return parsed_content
        
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse tool_response content as JSON: {e}")
        logger.debug(f"Raw content: {content[:500]}...")
        return None
    except Exception as e:
        logger.error(f"Unexpected error parsing tool response: {e}")
        return None

def _step_printer(steps, logger_instance=None):
    """Print the steps of an agent's response in a formatted way (optional debugging)"""
    if not RICH_AVAILABLE:
        if logger_instance:
            logger_instance.info("Rich/termcolor not available - skipping step printing")
        return
    
    for i, step in enumerate(steps):
        step_type = type(step).__name__
        print("\n"+"-" * 10, f"📍 Step {i+1}: {step_type}","-" * 10)
        
        if step_type == "ToolExecutionStep":
            print("🔧 Executing tool...")
            try:
                if hasattr(step, 'tool_responses') and step.tool_responses:
                    response_content = step.tool_responses[0].content
                    try:
                        pprint(json.loads(response_content))
                    except (TypeError, JSONDecodeError):
                        pprint(response_content)
                else:
                    print("No tool responses found")
            except Exception as e:
                print(f"Error displaying tool response: {e}")
        else:
            # Handle inference steps
            if hasattr(step, 'api_model_response') and step.api_model_response:
                if hasattr(step.api_model_response, 'content') and step.api_model_response.content:
                    print("🤖 Model Response:")
                    cprint(f"{step.api_model_response.content}\n", "magenta")
                elif hasattr(step.api_model_response, 'tool_calls') and step.api_model_response.tool_calls:
                    tool_call = step.api_model_response.tool_calls[0]
                    print("🛠️ Tool call Generated:")
                    try:
                        args = json.loads(tool_call.arguments_json)
                        cprint(f"Tool call: {tool_call.tool_name}, Arguments: {args}", "magenta")
                    except:
                        cprint(f"Tool call: {tool_call.tool_name}, Arguments: {tool_call.arguments_json}", "magenta")
    
    print("="*10, "Query processing completed","="*10,"\n")

class ValidationAgent:
    """
    ValidationAgent
    Uses pre-registered agent with mcp::ansible_lint tool configured
    """
    
    def __init__(self, client: LlamaStackClient, agent_id: str, session_id: str, 
                 timeout: int = 60, verbose_logging: bool = False):
        """Initialize ValidationAgent with required parameters"""
        self.client = client
        self.agent_id = agent_id
        self.session_id = session_id
        self.timeout = timeout
        self.verbose_logging = verbose_logging
        self.logger = logger
        
        # Enable debug logging if verbose is requested
        if verbose_logging:
            self.logger.setLevel(logging.DEBUG)
        
        # Configuration
        self.supported_profiles = ["basic", "moderate", "safety", "shared", "production"]
        
        self.logger.info(f"🔍 ValidationAgent initialized with agent_id: {agent_id} (registry pattern)")
        if verbose_logging:
            self.logger.debug("🔍 Debug logging enabled")

    def create_new_session(self, correlation_id: str) -> str:
        """Create a new session for this specific validation query"""
        try:
            response = self.client.agents.session.create(
                agent_id=self.agent_id,
                session_name=f"validation-{correlation_id}-{uuid.uuid4()}",
            )
            session_id = response.session_id
            self.logger.info(f"📱 Created new session: {session_id} for correlation: {correlation_id}")
            return session_id
        except Exception as e:
            self.logger.error(f" Failed to create session: {e}")
            # Fallback to default session
            self.logger.info(f"↩️ Falling back to default session: {self.session_id}")
            return self.session_id

    async def debug_tools(self) -> Dict[str, Any]:
        """Debug function to check tool availability and MCP registration"""
        try:
            import httpx
            
            # Direct HTTP calls to check MCP tool availability
            base_url = self.client.base_url
            
            # Get toolgroups
            toolgroups_response = httpx.get(f"{base_url}/v1/toolgroups", timeout=30)
            toolgroups_data = toolgroups_response.json() if toolgroups_response.status_code == 200 else {"data": []}
            available_toolgroups = [tg.get("identifier", tg.get("toolgroup_id", "unknown")) for tg in toolgroups_data.get("data", [])]
            
            # Get tools
            tools_response = httpx.get(f"{base_url}/v1/tools", timeout=30)
            tools_data = tools_response.json() if tools_response.status_code == 200 else {"data": []}
            available_tools = []
            
            for tool in tools_data.get("data", []):
                tool_name = tool.get("tool_name") or tool.get("name") or tool.get("identifier") or "unknown"
                available_tools.append(tool_name)
            
            # Filter for relevant tools
            ansible_tools = [t for t in available_tools if 'ansible' in t.lower()]
            mcp_tools = [t for t in available_tools if 'mcp::' in t.lower()]
            
            self.logger.info(f"🔧 Available toolgroups: {available_toolgroups}")
            self.logger.info(f"🔧 Available tools: {available_tools}")
            self.logger.info(f"🔧 Ansible tools: {ansible_tools}")
            self.logger.info(f"🔧 MCP tools: {mcp_tools}")
            
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
        
        # Validate profile
        if profile not in self.supported_profiles:
            raise ValueError(f"Unsupported profile: {profile}. Supported: {self.supported_profiles}")
        
        self.logger.info(f"🔍 Validating playbook with {profile} profile (correlation: {correlation_id})")
        
        try:
            # Create dedicated session for this validation query
            query_session_id = self.create_new_session(correlation_id)

            # Construct user prompt that explicitly requests tool usage
            user_prompt = self._build_validation_prompt(playbook_content, profile)
            self.logger.info(f"📬 Sending validation query to registered agent")
            
            # Use registry pattern - same as ContextAgent
            messages = [UserMessage(role="user", content=user_prompt)]
            
            # Create turn with timeout handling
            generator = self.client.agents.turn.create(
                agent_id=self.agent_id,
                session_id=query_session_id,
                messages=messages,
                stream=True,
            )
            
            # Process streaming response with timeout
            turn = None
            timeout_seconds = min(self.timeout, 120)  # Cap at 2 minutes
            timeout_start = time.time()
            
            for chunk in generator:
                # Check for timeout
                if time.time() - timeout_start > timeout_seconds:
                    self.logger.warning(f"⚠️ Turn processing timeout after {timeout_seconds}s")
                    raise TimeoutError(f"Validation timeout after {timeout_seconds} seconds")
                
                event = chunk.event
                event_type = event.payload.event_type
                if event_type == "turn_complete":
                    turn = event.payload.turn
                    break
            
            if not turn:
                self.logger.error(" No turn completed in response")
                raise RuntimeError("No turn completed in validation query")

            # Log steps for debugging
            self.logger.info(f"📊 Turn completed with {len(turn.steps)} steps")
            for i, step in enumerate(turn.steps):
                step_type = getattr(step, 'step_type', type(step).__name__)
                self.logger.info(f"📋 Step {i+1}: {step_type}")

            # Add step printing for debugging (optional)
            if self.verbose_logging:
                _step_printer(turn.steps, self.logger)

            # Process response
            total_time = time.time() - start_time
            return await self._process_validation_response(turn, correlation_id, profile, total_time)
            
        except TimeoutError as e:
            total_time = time.time() - start_time
            self.logger.error(f"⏰ Validation timeout after {total_time:.3f}s: {str(e)}")
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
        # Check playbook size to prevent timeouts
        max_size = 50000  # 50KB limit
        if len(playbook_content) > max_size:
            raise ValueError(f"Playbook too large ({len(playbook_content)} chars). Maximum size: {max_size} characters")
        
        # Add newline to playbook content if missing (fixes common issue)
        if not playbook_content.endswith('\n'):
            playbook_content += '\n'
            self.logger.debug("🔧 Added missing newline to playbook content")
            
        return f"""Please validate this Ansible playbook using ansible-lint with the {profile} profile.

IMPORTANT: You must use the ansible-lint tool to perform the validation. Do not attempt to validate manually.

Playbook to validate:
```yaml
{playbook_content}```

Please:
1. Use the ansible-lint tool to analyze this playbook
2. Report any issues found
3. Provide a summary of the validation results

Profile: {profile}"""

    async def _process_validation_response(self, turn, correlation_id: str, profile: str, elapsed_time: float) -> Dict[str, Any]:
        """Process validation response with proper error handling and issue detection"""
        
        found_lint = False
        tool_results = []
        
        if hasattr(turn, "steps"):
            for idx, step in enumerate(turn.steps):
                step_type = getattr(step, "step_type", type(step).__name__)
                self.logger.info(f"📋 Processing step {idx+1}: {step_type}")
                
                # Look for tool execution steps
                if step_type in ["tool_execution", "ToolExecutionStep"] or "tool" in step_type.lower():
                    self.logger.info("🔧 Found tool execution step!")
                    if hasattr(step, "tool_responses") and step.tool_responses:
                        self.logger.info(f"📥 Found {len(step.tool_responses)} tool responses")
                        for tool_response in step.tool_responses:
                            content = getattr(tool_response, "content", "")
                            self.logger.debug(f"🔍 Raw tool response content: {content}")
                            
                            lint_json = _get_lint_result_from_tool_response_content(content)
                            if lint_json:
                                found_lint = True
                                tool_results.append(lint_json)
                                self.logger.info(" Successfully parsed lint result!")
                                
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
                                tool_results.append({
                                    "raw_output": content,
                                    "success": True,
                                    "output": {"raw_output": {"stdout": content}}
                                })
                                self.logger.info(" Found tool execution with raw output")
                    else:
                        self.logger.warning("⚠️ tool_execution step has no tool_responses")
                
                # Also check for tool calls in inference steps
                elif step_type in ["inference", "InferenceStep"]:
                    if hasattr(step, "api_model_response") and step.api_model_response:
                        if hasattr(step.api_model_response, "tool_calls") and step.api_model_response.tool_calls:
                            self.logger.info(f"🛠️ Found {len(step.api_model_response.tool_calls)} tool calls in inference step")
                            for tool_call in step.api_model_response.tool_calls:
                                self.logger.info(f"Tool call: {tool_call.tool_name}")
        
        if found_lint and tool_results:
            # Process results using the corrected logic
            lint_json = tool_results[0]  # Use first result
            
            self.logger.debug(f"🔍 Processing lint_json: {list(lint_json.keys())}")
            
            # Handle different result structures - CRITICAL: Handle the actual MCP response structure
            if "output" in lint_json:
                output = lint_json["output"]
                summary = output.get("summary", {})
                issues = output.get("issues", [])
                raw_output = output.get("raw_output", {})
                self.logger.debug(f"🔍 Using 'output' structure - summary: {summary}")
            else:
                # Fallback structure
                summary = lint_json.get("summary", {})
                issues = lint_json.get("issues", [])
                raw_output = lint_json.get("raw_output", {})
                self.logger.debug(f"🔍 Using fallback structure - summary: {summary}")
            
            # CRITICAL FIX: Get the ACTUAL exit code and status from the MCP tool response
            actual_exit_code = summary.get("exit_code", 0)
            tool_passed = summary.get("passed", True)  # Default to True only if no exit_code info
            
            self.logger.debug(f"🔍 Extracted values - exit_code: {actual_exit_code}, tool_passed: {tool_passed}")
            
            # Override tool_passed if exit_code indicates failure
            if actual_exit_code > 0:
                tool_passed = False
                self.logger.debug(f"🔍 Overriding tool_passed to False due to exit_code: {actual_exit_code}")
            
            # Calculate actual issues count
            actual_issues_count = len(issues)
            
            # If exit_code > 0 but no issues in array, parse from raw output
            if actual_exit_code > 0 and actual_issues_count == 0:
                stdout = raw_output.get("stdout", "")
                stderr = raw_output.get("stderr", "")
                
                self.logger.debug(f"🔍 Parsing issues from raw output - stdout length: {len(stdout)}, stderr length: {len(stderr)}")
                
                # Count issues from stderr
                if "Failed:" in stderr:
                    failed_match = re.search(r'Failed: (\d+) failure', stderr)
                    if failed_match:
                        actual_issues_count = int(failed_match.group(1))
                        self.logger.debug(f"🔍 Found {actual_issues_count} issues from stderr regex")
                elif stdout.strip():  # At least one issue if stdout has content
                    actual_issues_count = 1
                    self.logger.debug(f"🔍 Found 1 issue from stdout content")
            
            # Determine if validation passed - MUST respect exit_code
            validation_passed = (actual_exit_code == 0) and tool_passed
            
            self.logger.debug(f"🔍 Final validation_passed: {validation_passed} (exit_code: {actual_exit_code}, tool_passed: {tool_passed})")
            
            # Format issues - use stdout if no structured issues
            if issues:
                formatted_issues = _format_lint_issues(issues)
            elif raw_output.get("stdout"):
                formatted_issues = raw_output.get("stdout", "")
            else:
                formatted_issues = "No issues found" if validation_passed else "Validation failed"
            
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
            return result
        else:
            # Enhanced fallback - check if there's useful content in output message
            fallback_content = ""
            if hasattr(turn, 'output_message') and turn.output_message:
                fallback_content = turn.output_message.content.strip()
            
            self.logger.warning("⚠️ No tool execution found - using fallback response")
            
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
                "debug_info": {
                    "steps_found": len(turn.steps) if hasattr(turn, 'steps') else 0,
                    "step_types": [getattr(step, 'step_type', type(step).__name__) for step in turn.steps] if hasattr(turn, 'steps') else []
                }
            }

    async def validate_playbook_stream(
        self, 
        playbook_content: str, 
        profile: str = "basic", 
        correlation_id: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Validate playbook with streaming updates"""
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
        """Quick syntax validation using basic profile"""
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
        results = {}
        
        for filename, content in files.items():
            self.logger.info(f"🔍 Validating file: {filename}")
            file_correlation = f"{correlation_id}-{filename}"
            
            try:
                result = await self.validate_playbook(content, profile, file_correlation)
                result["filename"] = filename
                results[filename] = result
            except Exception as e:
                self.logger.error(f" Failed to validate {filename}: {e}")
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

    async def health_check(self) -> bool:
        """Perform a health check on the validation agent"""
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
            is_healthy = result.get("success") is not None
            
            self.logger.info(f"🏥 Validation health check: {' passed' if is_healthy else ' failed'}")
            return is_healthy
            
        except Exception as e:
            self.logger.error(f" Validation health check failed: {e}")
            return False

    async def test_tool_availability(self) -> Dict[str, Any]:
        """Test if the MCP ansible_lint tool is available and working"""
        try:
            # Try a simple validation to see if tool gets called
            test_playbook = """---
- hosts: localhost
  tasks:
    - debug: 
        msg: "test"
"""
            
            self.logger.info("🧪 Testing tool availability with simple playbook")
            result = await self.validate_playbook(test_playbook, "basic", "tool-test")
            
            tool_called = "tool_execution" in str(result) or result.get("tool_response") is not None
            
            return {
                "tool_available": tool_called,
                "test_result": result,
                "agent_id": self.agent_id,
                "timestamp": time.time()
            }
        except Exception as e:
            self.logger.error(f" Tool availability test failed: {e}")
            return {
                "tool_available": False,
                "error": str(e),
                "agent_id": self.agent_id,
                "timestamp": time.time()
            }

    def get_status(self) -> Dict[str, Any]:
        """Get current status of the validation agent"""
        return {
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "client_base_url": self.client.base_url,
            "timeout": self.timeout,
            "status": "ready",
            "pattern": "Registry-based ",
            "tool": "mcp::ansible_lint",
            "supported_profiles": self.supported_profiles
        }

    def get_supported_profiles(self) -> List[str]:
        """Get list of supported validation profiles"""
        return self.supported_profiles.copy()

    def get_profile_descriptions(self) -> Dict[str, str]:
        """Get descriptions of validation profiles"""
        return {
            "basic": "Basic syntax and structure validation",
            "moderate": "Standard best practices checking", 
            "safety": "Security-focused validation rules",
            "shared": "Rules for shared/reusable playbooks",
            "production": "Strict production-ready validation"
        }