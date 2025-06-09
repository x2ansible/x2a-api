import logging
import uuid
import json
from typing import Optional, Dict, Any, List
from json import JSONDecodeError

from llama_stack_client import LlamaStackClient, Agent
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
        top = json.loads(content)
        if isinstance(top, dict) and "text" in top:
            return json.loads(top["text"])
        return top
    except Exception as e:
        logger.warning(f"Failed to parse tool_response content as JSON: {e}")
        return None

def _step_printer(steps, logger_instance=None):
    """Print the steps of an agent's response in a formatted way"""
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
    ValidationAgent - Hybrid approach: Uses working direct Agent creation pattern
    """
    
    def __init__(self, client: LlamaStackClient, agent_id: str = None, session_id: str = None, 
                 timeout: int = 60, verbose_logging: bool = False):
        self.client = client
        self.agent_id = agent_id  # For compatibility, but we'll create our own agents
        self.session_id = session_id
        self.timeout = timeout
        self.verbose_logging = verbose_logging
        self.logger = logger
        self.logger.info(f"🔍 ValidationAgent initialized (hybrid pattern)")

    async def validate_playbook(
        self, 
        playbook_content: str, 
        profile: str = "basic", 
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Validate using direct Agent creation - SAME AS WORKING TEST SCRIPT"""
        correlation_id = correlation_id or str(uuid.uuid4())
        
        self.logger.info(f"🔍 Validating playbook with {profile} profile (correlation: {correlation_id})")
        
        try:
            # Create agent using EXACT same pattern as working test script
            self.logger.info("🆕 Creating direct agent (like working test script)")
            
            agent = Agent(
                self.client,
                model="meta-llama/Llama-3.1-8B-Instruct",
                instructions="You are an Ansible expert. Use Ansible Lint tools when asked about linting.",
                tools=["mcp::ansible_lint"],
                tool_config={"tool_choice": "auto"},
                sampling_params={"strategy": {"type": "greedy"}, "max_tokens": 512}
            )
            
            # Create session
            session_id = agent.create_session(f"validation_{correlation_id}")
            self.logger.info(f"📱 Created session: {session_id}")

            # Prepare query - same format as working test script
            query = f"Use the lint_ansible_playbook tool with {profile} profile to check this playbook:\n\n{playbook_content}"
            self.logger.info(f"🚀 Calling direct agent with query")
            
            # Create turn - EXACT same as working test script
            response = agent.create_turn(
                messages=[{
                    "role": "user",
                    "content": query
                }],
                session_id=session_id,
                stream=False  # EXACTLY like working script
            )
            
            self.logger.info(f"📊 Turn completed with {len(response.steps)} steps")

            # Process response using SAME logic as working test script
            return await self._process_validation_response(response, correlation_id, profile)
            
        except Exception as e:
            self.logger.error(f" Validation failed: {str(e)}")
            return {
                "success": False,
                "correlation_id": correlation_id,
                "profile": profile,
                "error": str(e),
                "summary": {"passed": False},
                "issues_count": 0,
                "issues": [],
                "formatted_issues": f"Validation failed: {str(e)}"
            }

    async def _process_validation_response(self, response, correlation_id: str, profile: str) -> Dict[str, Any]:
        """Process validation response - SAME LOGIC AS WORKING TEST SCRIPT"""
        
        found_lint = False
        tool_results = []
        
        # Add step printing for debugging (optional)
        if self.verbose_logging:
            _step_printer(response.steps, self.logger)
        
        if hasattr(response, "steps"):
            for idx, step in enumerate(response.steps):
                step_type = getattr(step, "step_type", "unknown")
                self.logger.info(f"📋 Step {idx+1}: {step_type}")
                
                # Only interested in tool_execution step with tool_responses - SAME AS TEST SCRIPT
                if step_type == "tool_execution":
                    self.logger.info("🔧 Found tool_execution step!")
                    if hasattr(step, "tool_responses"):
                        self.logger.info(f"📥 Found {len(step.tool_responses)} tool responses")
                        for tool_response in step.tool_responses:
                            content = getattr(tool_response, "content", "")
                            lint_json = _get_lint_result_from_tool_response_content(content)
                            if lint_json:
                                found_lint = True
                                tool_results.append(lint_json)
                                self.logger.info(" Successfully parsed lint result!")
                    else:
                        self.logger.warning("⚠️ tool_execution step has no tool_responses")
        
        if found_lint and tool_results:
            # Process results - SAME AS WORKING TEST SCRIPT
            lint_json = tool_results[0]
            
            summary = lint_json.get("output", {}).get("summary", {})
            issues = lint_json.get("output", {}).get("issues", [])
            raw_output = lint_json.get("output", {}).get("raw_output", {})
            
            result = {
                "success": lint_json.get("success", False),
                "correlation_id": correlation_id,
                "profile": profile,
                "summary": summary,
                "issues_count": len(issues),
                "issues": issues,
                "formatted_issues": _format_lint_issues(issues),
                "passed": summary.get("passed", False),
                "raw_stdout": raw_output.get("stdout", ""),
                "raw_stderr": raw_output.get("stderr", ""),
                "tool_response": lint_json,
                "tool": lint_json.get("tool", "mcp::ansible_lint")
            }
            
            self.logger.info(f" Validation completed: {len(issues)} issues found")
            return result
        else:
            self.logger.warning("⚠️ No tool execution found")
            
            return {
                "success": False,
                "correlation_id": correlation_id,
                "profile": profile,
                "error": "No tool execution results found",
                "summary": {"passed": False},
                "issues_count": 0,
                "issues": [],
                "formatted_issues": "No tool execution occurred"
            }

    async def validate_playbook_stream(
        self, 
        playbook_content: str, 
        profile: str = "basic", 
        correlation_id: Optional[str] = None
    ):
        """Validate playbook with streaming updates"""
        correlation_id = correlation_id or str(uuid.uuid4())
        
        try:
            yield {
                "type": "progress",
                "status": "processing", 
                "message": f"🔍 Validation started with {profile} profile",
                "correlation_id": correlation_id
            }

            result = await self.validate_playbook(playbook_content, profile, correlation_id)
            
            yield {
                "type": "final_result",
                "data": result
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

    def get_status(self) -> Dict[str, Any]:
        """Get current status of the validation agent"""
        return {
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "client_base_url": self.client.base_url,
            "timeout": self.timeout,
            "status": "ready",
            "pattern": "Hybrid (Direct Agent Creation like working test script)",
            "tool": "mcp::ansible_lint",
            "supported_profiles": ["basic", "moderate", "safety", "shared", "production"]
        }

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

    def get_supported_profiles(self) -> List[str]:
        """Get list of supported validation profiles"""
        return ["basic", "moderate", "safety", "shared", "production"]

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