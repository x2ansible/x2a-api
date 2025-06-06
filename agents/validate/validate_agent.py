import logging
import asyncio
import time
import json
from typing import Dict, Any, AsyncGenerator

from llama_stack_client import LlamaStackClient
from llama_stack_client.lib.agents.agent import Agent
from llama_stack_client.lib.agents.event_logger import EventLogger
from llama_stack_client.types import UserMessage

from config.config import ConfigLoader
from agents.tools.ansible_lint_tool import ansible_lint_tool

logger = logging.getLogger("ValidationAgent")

class ValidationAgent:
    """
    LlamaStack ValidationAgent using ansible_lint_tool.
    Follows the same pattern as CodeGeneratorAgent.
    """

    def __init__(self, config_loader: ConfigLoader, agent_id: str = "validation", timeout: int = 30):
        self.config_loader = config_loader
        self.agent_id = agent_id
        all_agents = self.config_loader.get_agents_config()
        agent_cfg = next((a for a in all_agents if a.get("name") == self.agent_id), {})
        self.base_url = self.config_loader.get_llamastack_base_url()
        # Use the same model as your working CodeGeneratorAgent
        self.model_id = agent_cfg.get("model") or "meta-llama/Llama-3.1-8B-Instruct"
        self.timeout = timeout
        self.agent = None
        self._last_instructions_hash = None
        self._initialize_agent()
        logger.info(f"ValidationAgent initialized with model: {self.model_id}")

    def _get_current_instructions(self) -> str:
        instructions = self.config_loader.get_agent_instructions(self.agent_id)
        if not instructions:
            logger.warning("No instructions found in config, using fallback.")
            return """You are an expert Ansible playbook validation agent. Your role is to:

1. Always use the ansible_lint_tool when asked to validate a playbook (never answer directly, never guess).
2. Analyze and explain the lint results for users (status, errors, fixes, why it matters).
3. Be thorough, clear, and educational in your response.

CRITICAL: You MUST call ansible_lint_tool(playbook=<content>, profile=<profile>) for every validation request."""
        return instructions

    def _initialize_agent(self):
        try:
            current_instructions = self._get_current_instructions()
            self.client = LlamaStackClient(base_url=self.base_url)
            self.agent = Agent(
                client=self.client,
                model=self.model_id,
                instructions=current_instructions,
                tools=[ansible_lint_tool]  # Register our tool with the agent
            )
            self._last_instructions_hash = hash(current_instructions)
            logger.info(f"ValidationAgent initialized with model: {self.model_id}")
        except Exception as e:
            logger.error(f"Failed to initialize ValidationAgent: {e}")
            raise

    def _check_and_reload_config(self):
        try:
            current_instructions = self._get_current_instructions()
            current_hash = hash(current_instructions)
            if current_hash != self._last_instructions_hash:
                logger.info("ValidationAgent instructions changed, reloading agent.")
                self._initialize_agent()
        except Exception as e:
            logger.error(f"Failed to check/reload config: {e}")

    async def validate_playbook(self, playbook: str, lint_profile: str = "basic") -> Dict[str, Any]:
        try:
            self._check_and_reload_config()
            logger.info(f"Starting agentic validation with {lint_profile} profile")
            
            prompt = f"""Validate this Ansible playbook using the ansible_lint_tool with the '{lint_profile}' profile:

```yaml
{playbook}
```

Always call the tool first, then provide a comprehensive analysis of the results."""

            logger.info("Creating session...")
            session_id = self.agent.create_session("validation-session")
            logger.info(f"Created session: {session_id}")
            
            logger.info("Creating turn...")
            # Add timeout using asyncio
            turn = await asyncio.wait_for(
                asyncio.to_thread(
                    self.agent.create_turn,
                    session_id=session_id,
                    messages=[UserMessage(role="user", content=prompt)],
                    stream=False,
                ),
                timeout=self.timeout
            )
            logger.info(f"Turn completed: {type(turn)}")

            return await self._process_agent_response(turn, playbook, lint_profile)

        except asyncio.TimeoutError:
            logger.error(f"Agent validation timed out after {self.timeout} seconds")
            return self._create_error_response(f"Agent validation timed out after {self.timeout} seconds")
        except Exception as e:
            logger.error(f"ValidationAgent error: {e}")
            logger.exception("Full error details:")
            return self._create_error_response(f"Agent validation failed: {str(e)}")

    async def _process_agent_response(self, turn, playbook: str, lint_profile: str) -> Dict[str, Any]:
        try:
            agent_text = ""
            tool_results = []

            logger.info("Processing agent response...")
            
            # Get agent output text
            if hasattr(turn, 'output_message') and hasattr(turn.output_message, 'content'):
                agent_text = str(turn.output_message.content)
                logger.info(f"Got agent output: {len(agent_text)} chars")
            
            # Process steps to find tool results
            if hasattr(turn, 'steps') and turn.steps:
                logger.info(f"Found {len(turn.steps)} steps")
                for i, step in enumerate(turn.steps):
                    logger.info(f"Processing step {i}: {step.step_type}")
                    
                    # Check if this is a ToolExecutionStep
                    if step.step_type == "tool_execution":
                        logger.info("Found tool execution step!")
                        
                        # Check tool_calls
                        if hasattr(step, 'tool_calls') and step.tool_calls:
                            logger.info(f"Found {len(step.tool_calls)} tool calls")
                            for j, tool_call in enumerate(step.tool_calls):
                                logger.info(f"Tool call {j}: {tool_call.tool_name}")
                                if tool_call.tool_name == 'ansible_lint_tool':
                                    logger.info("Found ansible_lint_tool call!")
                                    logger.info(f"Tool call arguments: {tool_call.arguments}")
                        
                        # Check tool_responses - THIS IS THE KEY!
                        if hasattr(step, 'tool_responses') and step.tool_responses:
                            logger.info(f"Found {len(step.tool_responses)} tool responses")
                            for j, tool_response in enumerate(step.tool_responses):
                                logger.info(f"Tool response {j}: {type(tool_response)}")
                                logger.info(f"Tool response attributes: {dir(tool_response)}")
                                
                                # Check if response has content
                                if hasattr(tool_response, 'content'):
                                    logger.info(f"Tool response content: {tool_response.content}")
                                    
                                    # Try to parse as JSON if it's a string
                                    if isinstance(tool_response.content, str):
                                        try:
                                            parsed_content = json.loads(tool_response.content)
                                            if isinstance(parsed_content, dict) and 'validation_passed' in parsed_content:
                                                logger.info("Successfully parsed tool response content as JSON!")
                                                tool_results.append(parsed_content)
                                        except json.JSONDecodeError:
                                            logger.warning(f"Could not parse tool response content as JSON: {tool_response.content}")
                                    
                                    # If it's already a dict
                                    elif isinstance(tool_response.content, dict):
                                        if 'validation_passed' in tool_response.content:
                                            logger.info("Found validation result in tool response content dict!")
                                            tool_results.append(tool_response.content)
                                
                                # Check if response itself is the result
                                if hasattr(tool_response, 'result'):
                                    logger.info(f"Tool response result: {tool_response.result}")
                                    if isinstance(tool_response.result, dict) and 'validation_passed' in tool_response.result:
                                        logger.info("Found validation result in tool response result!")
                                        tool_results.append(tool_response.result)
                                
                                # Check other possible attributes
                                for attr_name in ['data', 'output', 'value']:
                                    if hasattr(tool_response, attr_name):
                                        attr_value = getattr(tool_response, attr_name)
                                        if isinstance(attr_value, dict) and 'validation_passed' in attr_value:
                                            logger.info(f"Found validation result in tool response {attr_name}!")
                                            tool_results.append(attr_value)

            logger.info(f"Processed response - Agent text: {len(agent_text)} chars, Tool results: {len(tool_results)}")

            # Look for validation results in tool outputs
            validation_result = None
            for i, tool_result in enumerate(tool_results):
                logger.info(f"Checking tool result {i}: {type(tool_result)}")
                if isinstance(tool_result, dict) and 'validation_passed' in tool_result:
                    validation_result = tool_result
                    logger.info(f"Found validation result: passed={validation_result.get('validation_passed')}")
                    break

            if validation_result:
                logger.info("Successfully found validation result from tool!")
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
                logger.error("AGENT DID NOT CALL THE TOOL OR TOOL RESPONSE NOT FOUND!")
                logger.error(f"Available tool results: {tool_results}")
                
                # Call the tool directly as fallback
                logger.warning("Falling back to direct tool call")
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

        except Exception as e:
            logger.error(f"Failed to process agent response: {e}")
            logger.exception("Full error details:")
            return self._create_error_response(f"Failed to process agent response: {str(e)}")

    async def validate_playbook_stream(
        self, playbook: str, lint_profile: str = "basic"
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Streams validation progress and result as SSE-compatible events.
        """
        start_time = time.time()
        
        yield {
            "event": "start",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "msg": "Validation started"
        }
        await asyncio.sleep(0.1)

        yield {
            "event": "progress",
            "progress": 0.5,
            "msg": "Agent analyzing playbook with tool...",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        await asyncio.sleep(0.2)

        try:
            result = await self.validate_playbook(playbook, lint_profile)
        except Exception as e:
            yield {
                "event": "error",
                "msg": f"Validation failed: {str(e)}",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }
            return

        yield {
            "event": "result",
            **result,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "processing_time": round(time.time() - start_time, 2)
        }

    def _create_error_response(self, error_message: str) -> Dict[str, Any]:
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

# Factory for DI
def create_validation_agent(config_loader: ConfigLoader = None, agent_id: str = "validation") -> ValidationAgent:
    if config_loader is None:
        config_loader = ConfigLoader("config.yaml")
    return ValidationAgent(config_loader, agent_id=agent_id)