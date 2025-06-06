import logging
import asyncio
import time
import json
import uuid
from typing import Dict, Any, AsyncGenerator

from llama_stack_client import LlamaStackClient
from llama_stack_client.types import UserMessage

logger = logging.getLogger("ValidationAgent")

class ValidationAgent:
    """
    ValidationAgent following Meta's pattern - Direct LlamaStack API calls only
    """
    def __init__(self, client: LlamaStackClient, agent_id: str, session_id: str, timeout: int = 30):
        self.client = client
        self.agent_id = agent_id
        self.session_id = session_id  # Default session
        self.timeout = timeout
        self.logger = logger
        self.logger.info(f"🔍 ValidationAgent initialized with agent_id: {agent_id}")

    def create_new_session(self, correlation_id: str) -> str:
        """Create a new session for this specific validation request"""
        try:
            response = self.client.agents.session.create(
                agent_id=self.agent_id,
                session_name=f"validation-{correlation_id}-{uuid.uuid4()}",
            )
            session_id = response.session_id
            self.logger.info(f" Created new session: {session_id} for correlation: {correlation_id}")
            return session_id
        except Exception as e:
            self.logger.error(f" Failed to create session: {e}")
            # Fallback to default session
            self.logger.info(f"↩️  Falling back to default session: {self.session_id}")
            return self.session_id

    async def validate_playbook(self, playbook: str, lint_profile: str = "basic", correlation_id: str = None) -> Dict[str, Any]:
        """Validate Ansible playbook using the validation agent"""
        correlation_id = correlation_id or str(uuid.uuid4())
        
        prompt = f"""Validate this Ansible playbook using the ansible_lint_tool with the '{lint_profile}' profile:

```yaml
{playbook}
```

Always call the tool first, then provide a comprehensive analysis of the results."""

        self.logger.info(f"🔍 Starting validation with {lint_profile} profile...")
        
        try:
            # Create dedicated session for this validation
            validation_session_id = self.create_new_session(correlation_id)

            # Direct API call following Meta's pattern
            messages = [UserMessage(role="user", content=prompt)]
            
            # Add timeout using asyncio
            generator = await asyncio.wait_for(
                asyncio.to_thread(
                    self.client.agents.turn.create,
                    agent_id=self.agent_id,
                    session_id=validation_session_id,
                    messages=messages,
                    stream=True,
                ),
                timeout=self.timeout
            )
            
            # Process streaming response
            turn = None
            for chunk in generator:
                event = chunk.event
                event_type = event.payload.event_type
                if event_type == "turn_complete":
                    turn = event.payload.turn
                    break
            
            if not turn:
                self.logger.error(" No turn completed in response")
                return self._create_error_response("No turn completed in validation")

            # Log steps for debugging
            self.logger.info(f" Turn completed with {len(turn.steps)} steps")
            for i, step in enumerate(turn.steps):
                self.logger.info(f"📋 Step {i+1}: {step.step_type}")

            # Process the agent response
            return await self._process_agent_response(turn, playbook, lint_profile)
            
        except asyncio.TimeoutError:
            self.logger.error(f" Agent validation timed out after {self.timeout} seconds")
            return self._create_error_response(f"Agent validation timed out after {self.timeout} seconds")
        except Exception as e:
            self.logger.error(f" Validation failed: {str(e)}")
            return self._create_error_response(f"Agent validation failed: {str(e)}")

    async def _process_agent_response(self, turn, playbook: str, lint_profile: str) -> Dict[str, Any]:
        """Process the agent response and extract validation results"""
        try:
            agent_text = ""
            tool_results = []

            self.logger.info("Processing agent response...")
            
            # Get agent output text
            if hasattr(turn, 'output_message') and hasattr(turn.output_message, 'content'):
                agent_text = str(turn.output_message.content)
                self.logger.info(f"Got agent output: {len(agent_text)} chars")
            
            # Process steps to find tool results
            if hasattr(turn, 'steps') and turn.steps:
                self.logger.info(f"Found {len(turn.steps)} steps")
                for i, step in enumerate(turn.steps):
                    self.logger.info(f"Processing step {i}: {step.step_type}")
                    
                    # Check if this is a tool execution step
                    if step.step_type == "tool_execution":
                        self.logger.info("Found tool execution step!")
                        
                        # Check tool_responses
                        if hasattr(step, 'tool_responses') and step.tool_responses:
                            self.logger.info(f"Found {len(step.tool_responses)} tool responses")
                            for j, tool_response in enumerate(step.tool_responses):
                                self.logger.info(f"Tool response {j}: {type(tool_response)}")
                                
                                # Extract tool response content
                                content = self._extract_tool_response_content(tool_response)
                                if content and isinstance(content, dict) and 'validation_passed' in content:
                                    self.logger.info("Successfully found validation result!")
                                    tool_results.append(content)

            self.logger.info(f"Processed response - Agent text: {len(agent_text)} chars, Tool results: {len(tool_results)}")

            # Look for validation results in tool outputs
            validation_result = None
            for tool_result in tool_results:
                if isinstance(tool_result, dict) and 'validation_passed' in tool_result:
                    validation_result = tool_result
                    self.logger.info(f"Found validation result: passed={validation_result.get('validation_passed')}")
                    break

            if validation_result:
                self.logger.info(" Successfully found validation result from tool!")
                return {
                    "success": True,
                    "validation_passed": validation_result.get("validation_passed", False),
                    "exit_code": validation_result.get("exit_code", -1),
                    "message": validation_result.get("message", ""),
                    "summary": validation_result.get("summary", {}),
                    "issues": validation_result.get("issues", []),
                    "recommendations": validation_result.get("recommendations", []),
                    "agent_analysis": agent_text.strip(),
                    "raw_output": validation_result.get("raw_output", {}),
                    "playbook_length": len(playbook),
                    "lint_profile": lint_profile,
                    "debug_info": {
                        "tool_results_found": len(tool_results),
                        "mode": "pure_agentic"
                    }
                }
            else:
                self.logger.error(" Agent did not call the tool or tool response not found!")
                
                # Import and call the tool directly as fallback
                try:
                    from agents.tools.ansible_lint_tool import ansible_lint_tool
                    self.logger.warning("⚠️ Falling back to direct tool call")
                    direct_result = ansible_lint_tool(playbook, lint_profile)
                    return {
                        "success": True,
                        "validation_passed": direct_result.get("validation_passed", False),
                        "exit_code": direct_result.get("exit_code", -1),
                        "message": direct_result.get("message", ""),
                        "summary": direct_result.get("summary", {}),
                        "issues": direct_result.get("issues", []),
                        "recommendations": direct_result.get("recommendations", []),
                        "agent_analysis": agent_text.strip() or "Tool called directly due to tool response parsing issues",
                        "raw_output": direct_result.get("raw_output", {}),
                        "playbook_length": len(playbook),
                        "lint_profile": lint_profile,
                        "debug_info": {
                            "mode": "direct_tool_fallback",
                            "tool_results_found": len(tool_results),
                            "reason": "Agent called tool but tool response not extracted properly"
                        }
                    }
                except ImportError:
                    return self._create_error_response("Tool not found and agent response not extractable")

        except Exception as e:
            self.logger.error(f" Failed to process agent response: {e}")
            return self._create_error_response(f"Failed to process agent response: {str(e)}")

    def _extract_tool_response_content(self, tool_response):
        """Extract content from tool response in various possible formats"""
        # Check if response has content
        if hasattr(tool_response, 'content'):
            content = tool_response.content
            
            # Try to parse as JSON if it's a string
            if isinstance(content, str):
                try:
                    parsed_content = json.loads(content)
                    if isinstance(parsed_content, dict):
                        return parsed_content
                except json.JSONDecodeError:
                    pass
            
            # If it's already a dict
            elif isinstance(content, dict):
                return content
        
        # Check if response itself is the result
        if hasattr(tool_response, 'result'):
            result = tool_response.result
            if isinstance(result, dict):
                return result
        
        # Check other possible attributes
        for attr_name in ['data', 'output', 'value']:
            if hasattr(tool_response, attr_name):
                attr_value = getattr(tool_response, attr_name)
                if isinstance(attr_value, dict):
                    return attr_value
        
        return None

    async def validate_playbook_stream(
        self, playbook: str, lint_profile: str = "basic", correlation_id: str = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream validation progress and result"""
        correlation_id = correlation_id or str(uuid.uuid4())
        start_time = time.time()
        
        try:
            yield {
                "type": "progress",
                "status": "processing",
                "message": "🔍 Validation started",
                "agent_info": {
                    "agent_id": self.agent_id,
                    "correlation_id": correlation_id
                }
            }

            result = await self.validate_playbook(playbook, lint_profile, correlation_id)
            
            yield {
                "type": "final_validation",
                "data": result,
                "correlation_id": correlation_id,
                "processing_time": round(time.time() - start_time, 2)
            }
        except Exception as e:
            yield {
                "type": "error",
                "error": str(e),
                "correlation_id": correlation_id
            }

    def _create_error_response(self, error_message: str) -> Dict[str, Any]:
        """Create standardized error response"""
        return {
            "success": False,
            "validation_passed": False,
            "exit_code": -1,
            "message": f"{error_message}",
            "summary": {
                "passed": False,
                "violations": 0,
                "warnings": 0,
                "total_issues": 0,
                "error": True
            },
            "issues": [],
            "recommendations": [],
            "agent_analysis": f"Validation failed: {error_message}",
            "error": error_message
        }

    def get_status(self) -> Dict[str, Any]:
        """Get current status of the validation agent"""
        return {
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "client_base_url": self.client.base_url,
            "timeout": self.timeout,
            "status": "ready",
            "pattern": "Meta Direct API"
        }

    async def health_check(self) -> bool:
        """Perform a health check on the validation agent"""
        try:
            messages = [UserMessage(role="user", content="Health check")]
            generator = self.client.agents.turn.create(
                agent_id=self.agent_id,
                session_id=self.session_id,
                messages=messages,
                stream=True,
            )
            
            # Just check if we can create a turn without errors
            for chunk in generator:
                break  # Just need first chunk to verify connection works
            
            self.logger.info(" Validation agent health check passed")
            return True
        except Exception as e:
            self.logger.error(f" Validation agent health check failed: {e}")
            return False