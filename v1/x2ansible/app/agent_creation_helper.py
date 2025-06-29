# app/agent_creation_helper.py - Production-grade agent creation with bulletproof error handling

import logging
from typing import List, Union, Optional, Any, Dict, Tuple
from llama_stack_client import LlamaStackClient
from llama_stack_client.lib.agents.agent import Agent
from llama_stack_client.lib.agents.react.agent import ReActAgent
from llama_stack_client.lib.agents.react.tool_parser import ReActToolParser
from llama_stack_client.types.shared_params.sampling_params import SamplingParams
from llama_stack_client.types.agents.turn_create_params import Toolgroup
from llama_stack_client.lib.agents.client_tool import ClientTool
from llama_stack_client.types.agent_create_params import AgentConfig

# Try to import ReActOutput - handle if not available
try:
    from llama_stack_client.lib.agents.react.tool_parser import ReActOutput
except ImportError:
    try:
        from llama_stack_client.lib.agents.react.agent import ReActOutput
    except ImportError:
        # Create a minimal fallback
        ReActOutput = None

logger = logging.getLogger(__name__)

class AgentCreationError(Exception):
    """Custom exception for agent creation failures"""
    pass

class AgentConfigurationValidator:
    """Validates agent configuration before creation"""
    
    @staticmethod
    def validate_basic_config(agent_name: str, agent_type: str, model: str, instructions: str) -> List[str]:
        """Validate basic required configuration"""
        errors = []
        
        if not agent_name or not isinstance(agent_name, str) or not agent_name.strip():
            errors.append("agent_name must be a non-empty string")
        
        if not agent_type or agent_type.lower() not in ["standard", "react"]:
            errors.append("agent_type must be 'standard' or 'react'")
        
        if not model or not isinstance(model, str) or not model.strip():
            errors.append("model must be a non-empty string")
        
        if not instructions or not isinstance(instructions, str) or not instructions.strip():
            errors.append("instructions must be a non-empty string")
        
        return errors
    
    @staticmethod
    def validate_tools_and_toolgroups(tools: Optional[List], toolgroups: Optional[List]) -> List[str]:
        """Validate tools and toolgroups configuration"""
        errors = []
        
        if tools is not None:
            if not isinstance(tools, list):
                errors.append("tools must be a list")
            else:
                for i, tool in enumerate(tools):
                    if not isinstance(tool, (str, dict, ClientTool)) and not callable(tool):
                        errors.append(f"tools[{i}] must be a string, dict, callable, or ClientTool instance")
        
        if toolgroups is not None:
            if not isinstance(toolgroups, list):
                errors.append("toolgroups must be a list")
            else:
                for i, toolgroup in enumerate(toolgroups):
                    if isinstance(toolgroup, str):
                        if not toolgroup.strip():
                            errors.append(f"toolgroups[{i}] string cannot be empty")
                    elif isinstance(toolgroup, dict):
                        if "name" not in toolgroup:
                            errors.append(f"toolgroups[{i}] dict must have 'name' field")
                        elif not isinstance(toolgroup["name"], str) or not toolgroup["name"].strip():
                            errors.append(f"toolgroups[{i}]['name'] must be a non-empty string")
                    else:
                        errors.append(f"toolgroups[{i}] must be a string or dict")
        
        return errors
    
    @staticmethod
    def validate_sampling_params(sampling_params: Optional[Dict]) -> List[str]:
        """Validate sampling parameters"""
        errors = []
        
        if sampling_params is None:
            return errors
        
        if not isinstance(sampling_params, dict):
            errors.append("sampling_params must be a dictionary")
            return errors
        
        # Validate individual parameters
        temperature = sampling_params.get("temperature")
        if temperature is not None:
            if not isinstance(temperature, (int, float)) or not (0.0 <= temperature <= 2.0):
                errors.append("temperature must be a number between 0.0 and 2.0")
        
        top_p = sampling_params.get("top_p")
        if top_p is not None:
            if not isinstance(top_p, (int, float)) or not (0.0 <= top_p <= 1.0):
                errors.append("top_p must be a number between 0.0 and 1.0")
        
        top_k = sampling_params.get("top_k")
        if top_k is not None:
            if not isinstance(top_k, int) or top_k < 1:
                errors.append("top_k must be a positive integer")
        
        max_tokens = sampling_params.get("max_tokens")
        if max_tokens is not None:
            if not isinstance(max_tokens, int) or max_tokens < 1:
                errors.append("max_tokens must be a positive integer")
        
        repetition_penalty = sampling_params.get("repetition_penalty")
        if repetition_penalty is not None:
            if not isinstance(repetition_penalty, (int, float)) or repetition_penalty <= 0:
                errors.append("repetition_penalty must be a positive number")
        
        return errors
    
    @staticmethod
    def validate_numeric_params(max_infer_iters: Optional[int]) -> List[str]:
        """Validate numeric parameters"""
        errors = []
        
        if max_infer_iters is not None:
            if not isinstance(max_infer_iters, int) or max_infer_iters < 1:
                errors.append("max_infer_iters must be a positive integer")
        
        return errors

class AgentCreationHelper:
    """Production-grade agent creation helper with comprehensive validation and error handling"""
    
    def __init__(self, client: LlamaStackClient):
        self.client = client
        self.validator = AgentConfigurationValidator()
    
    def create_agent_from_config(self, agent_name: str, config: Dict[str, Any]) -> Union[Agent, ReActAgent]:
        """
        Create an agent from configuration with comprehensive validation
        
        Args:
            agent_name: Name for the agent
            config: Configuration dictionary
            
        Returns:
            Agent or ReActAgent instance
            
        Raises:
            AgentCreationError: If agent creation fails
        """
        try:
            # Step 1: Extract and validate basic configuration
            model = config.get("model")
            instructions = config.get("instructions", "")
            agent_pattern = config.get("agent_pattern", "standard").lower()
            
            # Validate basic config
            basic_errors = self.validator.validate_basic_config(agent_name, agent_pattern, model, instructions)
            if basic_errors:
                raise AgentCreationError(f"Basic configuration validation failed: {'; '.join(basic_errors)}")
            
            # Step 2: Extract and validate tools/toolgroups
            tools = config.get("tools", [])
            toolgroups = config.get("toolgroups", [])
            
            tools_errors = self.validator.validate_tools_and_toolgroups(tools, toolgroups)
            if tools_errors:
                raise AgentCreationError(f"Tools/toolgroups validation failed: {'; '.join(tools_errors)}")
            
            # Step 3: Extract and validate sampling parameters
            sampling_params_dict = config.get("sampling_params", {})
            
            # Handle strategy flattening
            if "strategy" in sampling_params_dict:
                strategy = sampling_params_dict.pop("strategy")
                if isinstance(strategy, dict):
                    sampling_params_dict.update(strategy)
            
            sampling_errors = self.validator.validate_sampling_params(sampling_params_dict)
            if sampling_errors:
                raise AgentCreationError(f"Sampling parameters validation failed: {'; '.join(sampling_errors)}")
            
            # Step 4: Extract and validate other parameters
            max_infer_iters = config.get("max_infer_iters", 10)
            tool_config = config.get("tool_config")
            input_shields = config.get("input_shields")
            output_shields = config.get("output_shields")
            response_format = config.get("response_format")
            enable_session_persistence = config.get("enable_session_persistence", True)
            
            numeric_errors = self.validator.validate_numeric_params(max_infer_iters)
            if numeric_errors:
                raise AgentCreationError(f"Numeric parameters validation failed: {'; '.join(numeric_errors)}")
            
            # Step 5: Log creation details
            logger.info(f"🏗️  Creating {agent_pattern} agent '{agent_name}':")
            logger.info(f"    Model: {model}")
            logger.info(f"    Tools: {len(tools)}")
            logger.info(f"    Toolgroups: {len(toolgroups)}")
            logger.info(f"    Max iterations: {max_infer_iters}")
            logger.info(f"    Session persistence: {enable_session_persistence}")
            
            # Step 6: Create the agent
            return self._create_agent_instance(
                agent_name=agent_name,
                agent_type=agent_pattern,
                model=model,
                instructions=instructions,
                tools=tools,
                toolgroups=toolgroups,
                tool_config=tool_config,
                sampling_params_dict=sampling_params_dict,
                max_infer_iters=max_infer_iters,
                input_shields=input_shields,
                output_shields=output_shields,
                response_format=response_format,
                enable_session_persistence=enable_session_persistence
            )
            
        except AgentCreationError:
            # Re-raise our custom errors
            raise
        except Exception as e:
            # Wrap unexpected errors
            error_msg = f"Unexpected error creating agent '{agent_name}': {str(e)}"
            logger.error(f" {error_msg}", exc_info=True)
            raise AgentCreationError(error_msg) from e
    
    def _create_agent_instance(
        self,
        agent_name: str,
        agent_type: str,
        model: str,
        instructions: str,
        tools: List,
        toolgroups: List,
        tool_config: Optional[Dict],
        sampling_params_dict: Dict,
        max_infer_iters: int,
        input_shields: Optional[List[str]],
        output_shields: Optional[List[str]],
        response_format: Optional[Dict],
        enable_session_persistence: bool
    ) -> Union[Agent, ReActAgent]:
        """Create the actual agent instance with proper error handling"""
        
        try:
            # Combine tools and toolgroups - ensure we always have lists, never None
            all_tools = []
            if tools and isinstance(tools, list):
                all_tools.extend(tools)
            if toolgroups and isinstance(toolgroups, list):
                all_tools.extend(toolgroups)
            
            # Convert sampling_params dict to SamplingParams object
            sampling_params_obj = None
            if sampling_params_dict:
                try:
                    sampling_params_obj = SamplingParams(**sampling_params_dict)
                except Exception as e:
                    raise AgentCreationError(f"Invalid sampling parameters: {str(e)}")
            
            # Create agent based on type
            if agent_type == "react":
                return self._create_react_agent(
                    agent_name=agent_name,
                    model=model,
                    instructions=instructions,
                    all_tools=all_tools,
                    tool_config=tool_config,
                    sampling_params_obj=sampling_params_obj,
                    max_infer_iters=max_infer_iters,
                    input_shields=input_shields,
                    output_shields=output_shields,
                    response_format=response_format,
                    enable_session_persistence=enable_session_persistence
                )
            else:
                return self._create_standard_agent(
                    agent_name=agent_name,
                    model=model,
                    instructions=instructions,
                    all_tools=all_tools,
                    tool_config=tool_config,
                    sampling_params_obj=sampling_params_obj,
                    max_infer_iters=max_infer_iters,
                    input_shields=input_shields,
                    output_shields=output_shields,
                    response_format=response_format,
                    enable_session_persistence=enable_session_persistence
                )
                
        except Exception as e:
            if isinstance(e, AgentCreationError):
                raise
            error_msg = f"Failed to create {agent_type} agent instance: {str(e)}"
            logger.error(f" {error_msg}", exc_info=True)
            raise AgentCreationError(error_msg) from e
    
    def _create_react_agent(
        self,
        agent_name: str,
        model: str,
        instructions: str,
        all_tools: List,
        tool_config: Optional[Dict],
        sampling_params_obj: Optional[SamplingParams],
        max_infer_iters: int,
        input_shields: Optional[List[str]],
        output_shields: Optional[List[str]],
        response_format: Optional[Dict],
        enable_session_persistence: bool
    ) -> ReActAgent:
        """Create ReAct agent with proper configuration"""
        
        try:
            # Set up response format for ReAct if not provided
            if not response_format and ReActOutput:
                response_format = {
                    "type": "json_schema",
                    "json_schema": ReActOutput.model_json_schema(),
                }
                logger.debug(f"Auto-configured JSON response format for ReAct agent '{agent_name}'")
            elif not response_format:
                logger.warning(f"ReActOutput schema not available, using basic JSON format for '{agent_name}'")
                response_format = {"type": "json"}
            
            # Create ReAct agent (revert to working version)
            agent = ReActAgent(
                client=self.client,
                model=model,
                instructions=instructions,
                tools=all_tools or [],  # Always pass empty list, never None
                tool_config=tool_config,
                sampling_params=sampling_params_obj,
                max_infer_iters=max_infer_iters,
                input_shields=input_shields,
                output_shields=output_shields,
                response_format=response_format,
                enable_session_persistence=enable_session_persistence,
                tool_parser=ReActToolParser(),
            )
            
            logger.info(f" Created ReActAgent '{agent_name}' with ID: {agent.agent_id}")
            return agent
            
        except Exception as e:
            error_msg = f"ReActAgent creation failed: {str(e)}"
            logger.error(f" {error_msg}")
            raise AgentCreationError(error_msg) from e
    
    def _create_standard_agent(
        self,
        agent_name: str,
        model: str,
        instructions: str,
        all_tools: List,
        tool_config: Optional[Dict],
        sampling_params_obj: Optional[SamplingParams],
        max_infer_iters: int,
        input_shields: Optional[List[str]],
        output_shields: Optional[List[str]],
        response_format: Optional[Dict],
        enable_session_persistence: bool
    ) -> Agent:
        """Create standard agent with proper configuration"""
        
        try:
            # Create standard agent (revert to working version)
            agent = Agent(
                client=self.client,
                model=model,
                instructions=instructions,
                tools=all_tools or [],  # Always pass empty list, never None
                tool_config=tool_config,
                sampling_params=sampling_params_obj,
                max_infer_iters=max_infer_iters,
                input_shields=input_shields,
                output_shields=output_shields,
                response_format=response_format,
                enable_session_persistence=enable_session_persistence,
            )
            
            logger.info(f" Created standard Agent '{agent_name}' with ID: {agent.agent_id}")
            return agent
            
        except Exception as e:
            error_msg = f"Standard Agent creation failed: {str(e)}"
            logger.error(f" {error_msg}")
            raise AgentCreationError(error_msg) from e
    
    def get_agent_info(self, agent: Union[Agent, ReActAgent]) -> Dict[str, Any]:
        """Get comprehensive information about an agent"""
        try:
            agent_type = "react" if isinstance(agent, ReActAgent) else "standard"
            
            # Get toolgroups info safely
            toolgroups = agent.agent_config.get("toolgroups", [])
            toolgroup_names = []
            for tg in toolgroups:
                if isinstance(tg, str):
                    toolgroup_names.append(tg)
                elif isinstance(tg, dict) and "name" in tg:
                    toolgroup_names.append(tg["name"])
            
            # Get client tools info safely
            client_tool_names = list(agent.client_tools.keys()) if hasattr(agent, 'client_tools') and agent.client_tools else []
            
            # Get sampling params safely
            sampling_params = agent.agent_config.get("sampling_params", {})
            if hasattr(sampling_params, '__dict__'):
                sampling_params = sampling_params.__dict__
            
            # Get builtin tools safely
            builtin_tools = []
            if hasattr(agent, 'builtin_tools') and agent.builtin_tools:
                builtin_tools = list(agent.builtin_tools.keys())
            
            # Get sessions count safely
            sessions_count = 0
            if hasattr(agent, 'sessions') and agent.sessions:
                sessions_count = len(agent.sessions)
            
            return {
                "agent_id": getattr(agent, 'agent_id', 'unknown'),
                "agent_type": agent_type,
                "model": agent.agent_config.get("model", "unknown"),
                "instructions_length": len(agent.agent_config.get("instructions", "")),
                "toolgroups": toolgroup_names,
                "client_tools": client_tool_names,
                "builtin_tools": builtin_tools,
                "total_tools": len(toolgroup_names) + len(client_tool_names) + len(builtin_tools),
                "sessions_count": sessions_count,
                "max_infer_iters": agent.agent_config.get("max_infer_iters", 10),
                "enable_session_persistence": agent.agent_config.get("enable_session_persistence", False),
                "has_input_shields": bool(agent.agent_config.get("input_shields")),
                "has_output_shields": bool(agent.agent_config.get("output_shields")),
                "has_response_format": bool(agent.agent_config.get("response_format")),
                "has_tool_config": bool(agent.agent_config.get("tool_config")),
                "sampling_params": sampling_params,
            }
            
        except Exception as e:
            logger.error(f"Error getting agent info: {str(e)}")
            return {
                "agent_id": "error",
                "agent_type": "unknown",
                "error": str(e)
            }
    
    def validate_agent_before_creation(self, agent_name: str, config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate agent configuration before attempting creation
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        all_errors = []
        
        try:
            # Basic validation
            model = config.get("model")
            instructions = config.get("instructions", "")
            agent_pattern = config.get("agent_pattern", "standard").lower()
            
            basic_errors = self.validator.validate_basic_config(agent_name, agent_pattern, model, instructions)
            all_errors.extend(basic_errors)
            
            # Tools validation
            tools = config.get("tools", [])
            toolgroups = config.get("toolgroups", [])
            tools_errors = self.validator.validate_tools_and_toolgroups(tools, toolgroups)
            all_errors.extend(tools_errors)
            
            # Sampling params validation
            sampling_params = config.get("sampling_params", {})
            sampling_errors = self.validator.validate_sampling_params(sampling_params)
            all_errors.extend(sampling_errors)
            
            # Numeric params validation
            max_infer_iters = config.get("max_infer_iters")
            numeric_errors = self.validator.validate_numeric_params(max_infer_iters)
            all_errors.extend(numeric_errors)
            
            return len(all_errors) == 0, all_errors
            
        except Exception as e:
            all_errors.append(f"Validation error: {str(e)}")
            return False, all_errors