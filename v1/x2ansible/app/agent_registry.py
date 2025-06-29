# app/agent_registry.py - Production-grade agent registry with bulletproof management

import logging
import threading
import time
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
from llama_stack_client.lib.agents.agent import Agent
from llama_stack_client.lib.agents.react.agent import ReActAgent

from app.client_manager import LlamaStackClientManager, LlamaStackConnectionError
from app.agent_creation_helper import AgentCreationHelper, AgentCreationError
from app.formatters.response_formatters import ResponseFormatterManager
from config.config import ConfigLoader, ConfigValidationError
from utils.logging_utils import get_enhanced_logger

logger = logging.getLogger(__name__)

class AgentRegistryError(Exception):
    """Custom exception for agent registry operations"""
    pass

class SessionManager:
    """Manages agent sessions with proper lifecycle handling"""
    
    def __init__(self):
        self._sessions: Dict[str, str] = {}  # agent_name -> session_id
        self._session_timestamps: Dict[str, float] = {}  # agent_name -> creation_time
        self._lock = threading.Lock()
    
    def get_or_create_session(self, agent_name: str, agent: Union[Agent, ReActAgent]) -> str:
        """Get existing session or create new one for agent"""
        with self._lock:
            if agent_name in self._sessions:
                return self._sessions[agent_name]
            
            try:
                session_id = agent.create_session(f"session_{agent_name}_{int(time.time())}")
                self._sessions[agent_name] = session_id
                self._session_timestamps[agent_name] = time.time()
                
                logger.info(f"📱 Created session '{session_id}' for agent '{agent_name}'")
                return session_id
                
            except Exception as e:
                error_msg = f"Failed to create session for agent '{agent_name}': {str(e)}"
                logger.error(f" {error_msg}")
                raise AgentRegistryError(error_msg) from e
    
    def get_session_info(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """Get session information for agent"""
        with self._lock:
            if agent_name not in self._sessions:
                return None
            
            return {
                "session_id": self._sessions[agent_name],
                "created_at": self._session_timestamps.get(agent_name),
                "age_seconds": time.time() - self._session_timestamps.get(agent_name, 0)
            }
    
    def remove_session(self, agent_name: str) -> bool:
        """Remove session for agent"""
        with self._lock:
            if agent_name in self._sessions:
                del self._sessions[agent_name]
                self._session_timestamps.pop(agent_name, None)
                logger.info(f"🗑️  Removed session for agent '{agent_name}'")
                return True
            return False
    
    def get_all_sessions(self) -> Dict[str, Dict[str, Any]]:
        """Get all session information"""
        with self._lock:
            result = {}
            for agent_name, session_id in self._sessions.items():
                created_at = self._session_timestamps.get(agent_name)
                result[agent_name] = {
                    "session_id": session_id,
                    "created_at": created_at,
                    "age_seconds": time.time() - created_at if created_at else None
                }
            return result

class UnifiedAgentRegistry:
    """
    Production-grade registry for managing both standard and ReAct agents.
    Agents are created once on-demand and reused for all subsequent requests.
    """
    
    def __init__(self, client_manager: LlamaStackClientManager, config_loader: ConfigLoader):
        self.client_manager = client_manager
        self.config_loader = config_loader
        self.creation_helper = AgentCreationHelper(client_manager.get_client())
        self.session_manager = SessionManager()
        self.enhanced_logger = get_enhanced_logger()
        
        # Initialize response formatter manager (reused per registry instance)
        self.response_formatter = ResponseFormatterManager()
        logger.info("🎨 Response formatter manager initialized for this registry")
        
        # Storage for agents and metadata
        self._agents: Dict[str, Union[Agent, ReActAgent]] = {}
        self._agent_configs: Dict[str, Dict[str, Any]] = {}
        self._agent_metadata: Dict[str, Dict[str, Any]] = {}
        self._creation_timestamps: Dict[str, float] = {}
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Load agent configurations
        self._load_agent_configurations()
        
        logger.info("🎯 UnifiedAgentRegistry initialized successfully")

    def _load_agent_configurations(self) -> None:
        """Load and validate all agent configurations from config"""
        try:
            agents_config = self.config_loader.get_agents_config()
            
            if not agents_config:
                raise AgentRegistryError("No agents configured in config file")
            
            # Store configurations by name
            for agent_config in agents_config:
                agent_name = agent_config.get("name")
                if not agent_name:
                    logger.warning("Skipping agent config without name")
                    continue
                
                # Validate configuration before storing
                is_valid, validation_errors = self.creation_helper.validate_agent_before_creation(
                    agent_name, agent_config
                )
                
                if not is_valid:
                    error_msg = f"Invalid configuration for agent '{agent_name}': {'; '.join(validation_errors)}"
                    logger.error(f" {error_msg}")
                    raise AgentRegistryError(error_msg)
                
                self._agent_configs[agent_name] = agent_config
                logger.debug(f" Loaded configuration for agent '{agent_name}'")
            
            logger.info(f"📋 Loaded {len(self._agent_configs)} agent configurations")
            
        except Exception as e:
            if isinstance(e, AgentRegistryError):
                raise
            error_msg = f"Failed to load agent configurations: {str(e)}"
            logger.error(f" {error_msg}")
            raise AgentRegistryError(error_msg) from e

    def _create_agent(self, agent_name: str) -> Union[Agent, ReActAgent]:
        """Create an agent instance with full error handling"""
        with self._lock:
            # Check if already created
            if agent_name in self._agents:
                return self._agents[agent_name]
            
            # Get configuration
            config = self._agent_configs.get(agent_name)
            if not config:
                raise AgentRegistryError(f"No configuration found for agent '{agent_name}'")
            
            try:
                logger.info(f"🚀 Creating agent '{agent_name}'...")
                start_time = time.time()
                
                # Validate model exists on server
                model = config.get("model")
                if not self.client_manager.validate_model(model):
                    logger.warning(f"Model '{model}' may not be available on LlamaStack server")
                
                # Create agent using helper
                agent = self.creation_helper.create_agent_from_config(agent_name, config)
                
                # Store agent and metadata
                self._agents[agent_name] = agent
                self._creation_timestamps[agent_name] = time.time()
                
                # Get detailed agent info
                agent_info = self.creation_helper.get_agent_info(agent)
                self._agent_metadata[agent_name] = agent_info
                
                creation_time = time.time() - start_time
                logger.info(f" Successfully created agent '{agent_name}' in {creation_time:.2f}s")
                logger.info(f"    Type: {agent_info['agent_type']}")
                logger.info(f"    ID: {agent_info['agent_id']}")
                logger.info(f"    Model: {agent_info['model']}")
                logger.info(f"    Total tools: {agent_info['total_tools']}")
                
                return agent
                
            except AgentCreationError as e:
                logger.error(f" Agent creation failed for '{agent_name}': {str(e)}")
                raise AgentRegistryError(f"Failed to create agent '{agent_name}': {str(e)}") from e
            except Exception as e:
                error_msg = f"Unexpected error creating agent '{agent_name}': {str(e)}"
                logger.error(f" {error_msg}", exc_info=True)
                raise AgentRegistryError(error_msg) from e

    def get_agent(self, agent_name: str) -> Union[Agent, ReActAgent]:
        """
        Get agent instance, creating it if necessary
        
        Args:
            agent_name: Name of the agent to get
            
        Returns:
            Agent or ReActAgent instance
            
        Raises:
            AgentRegistryError: If agent cannot be found or created
        """
        if not agent_name:
            raise AgentRegistryError("Agent name cannot be empty")
        
        if agent_name not in self._agent_configs:
            available_agents = list(self._agent_configs.keys())
            raise AgentRegistryError(
                f"Agent '{agent_name}' not found. Available agents: {available_agents}"
            )
        
        # Create agent if not already created
        if agent_name not in self._agents:
            self._create_agent(agent_name)
        
        return self._agents[agent_name]

    def execute_query(self, agent_name: str, query: str, **metadata) -> Dict[str, Any]:
        """
        Execute a query against an agent and return structured response
        
        Args:
            agent_name: Name of the agent to use
            query: Query string to execute
            **metadata: Additional metadata to include in response
            
        Returns:
            Structured response dictionary
        """
        if not query or not query.strip():
            raise AgentRegistryError("Query cannot be empty")
        
        try:
            start_time = time.time()
            
            # Enhanced logging - start
            self.enhanced_logger.log_agent_execution_start(agent_name, query)
            
            # Get agent instance
            agent = self.get_agent(agent_name)
            
            # Get or create session
            session_id = self.session_manager.get_or_create_session(agent_name, agent)
            
            # Prepare messages
            messages = [{"role": "user", "content": query.strip()}]
            
            logger.info(f"🔍 Executing query for agent '{agent_name}' (session: {session_id[:8]}...)")
            logger.debug(f"Query: {query[:100]}...")
            
            # Execute query (non-streaming)
            turn = agent.create_turn(messages=messages, session_id=session_id, stream=False)
            
            execution_time = time.time() - start_time
            
            # Enhanced logging - analyze response
            self.enhanced_logger.log_response_analysis(turn, agent_name)
            self.enhanced_logger.log_agent_execution_complete(agent_name, execution_time, True)
            
            # Get agent type for formatter selection
            agent_type = self._agent_metadata.get(agent_name, {}).get("agent_type", "standard")
            
            # Process response with appropriate formatter
            logger.debug(f"🎨 Processing response with {agent_type} formatter")
            formatted_response = self.response_formatter.process_response(
                raw_response=turn,
                agent_name=agent_name,
                agent_type=agent_type.lower(),
                execution_time=execution_time,
                session_id=session_id,
                **metadata
            )
            
            logger.info(f" Query executed successfully in {execution_time:.2f}s")
            return formatted_response
            
        except AgentRegistryError:
            raise
        except Exception as e:
            execution_time = time.time() - start_time if 'start_time' in locals() else 0
            self.enhanced_logger.log_agent_execution_complete(agent_name, execution_time, False)
            
            error_msg = f"Query execution failed for agent '{agent_name}': {str(e)}"
            logger.error(f" {error_msg}", exc_info=True)
            
            return {
                "success": False,
                "error": error_msg,
                "agent_name": agent_name,
                "metadata": {
                    "timestamp": datetime.utcnow().isoformat(),
                    **metadata
                }
            }

    def _extract_response_content(self, turn: Any) -> str:
        """Extract content from turn response with fallbacks (legacy method)"""
        try:
            # Primary method - get content from output message
            if hasattr(turn, 'output_message') and hasattr(turn.output_message, 'content'):
                content = turn.output_message.content
                if content and isinstance(content, str):
                    return content.strip()
            
            # Fallback - convert entire turn to string
            content = str(turn) if turn else ""
            return content.strip()
            
        except Exception as e:
            logger.warning(f"Error extracting response content: {str(e)}")
            return str(turn) if turn else ""

    def _try_parse_json_response(self, content: str) -> Optional[Dict[str, Any]]:
        """Try to parse response content as JSON (legacy method)"""
        if not content or not isinstance(content, str):
            return None
        
        import json
        
        content = content.strip()
        
        # Direct JSON parsing
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        
        # Extract JSON from code blocks or other formats
        try:
            # Look for JSON between curly braces
            start_idx = content.find('{')
            end_idx = content.rfind('}')
            
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                json_content = content[start_idx:end_idx + 1]
                return json.loads(json_content)
        except json.JSONDecodeError:
            pass
        
        return None

    def get_agent_status(self, agent_name: str) -> Dict[str, Any]:
        """Get detailed status for a specific agent"""
        if agent_name not in self._agent_configs:
            raise AgentRegistryError(f"Agent '{agent_name}' not found")
        
        status = {
            "agent_name": agent_name,
            "config_loaded": True,
            "agent_created": agent_name in self._agents,
            "config": self._agent_configs[agent_name].copy(),
        }
        
        # Add creation info if agent exists
        if agent_name in self._agents:
            status.update({
                "agent_metadata": self._agent_metadata.get(agent_name, {}),
                "created_at": self._creation_timestamps.get(agent_name),
                "session_info": self.session_manager.get_session_info(agent_name),
            })
        
        return status

    def get_registry_status(self) -> Dict[str, Any]:
        """Get comprehensive status of the entire registry"""
        with self._lock:
            # Calculate stats
            total_configured = len(self._agent_configs)
            total_created = len(self._agents)
            
            # Get agent type breakdown
            agent_types = {}
            for name, metadata in self._agent_metadata.items():
                agent_type = metadata.get("agent_type", "unknown")
                agent_types[agent_type] = agent_types.get(agent_type, 0) + 1
            
            # Get session info
            session_info = self.session_manager.get_all_sessions()
            
            return {
                "registry_healthy": True,
                "total_agents_configured": total_configured,
                "total_agents_created": total_created,
                "agents_pending_creation": total_configured - total_created,
                "agent_types": agent_types,
                "configured_agents": list(self._agent_configs.keys()),
                "created_agents": list(self._agents.keys()),
                "sessions": session_info,
                "client_status": self.client_manager.health_check(),
                "timestamp": datetime.utcnow().isoformat()
            }

    def list_available_agents(self) -> List[Dict[str, Any]]:
        """List all available agents with their configuration summary"""
        agents_list = []
        
        for agent_name, config in self._agent_configs.items():
            agent_info = {
                "name": agent_name,
                "type": config.get("agent_pattern", "standard"),
                "model": config.get("model", "unknown"),
                "created": agent_name in self._agents,
                "tools_count": len(config.get("tools", [])),
                "toolgroups_count": len(config.get("toolgroups", [])),
                "has_session": agent_name in self.session_manager._sessions,
            }
            
            # Add runtime info if agent is created
            if agent_name in self._agents:
                metadata = self._agent_metadata.get(agent_name, {})
                agent_info.update({
                    "agent_id": metadata.get("agent_id"),
                    "total_tools": metadata.get("total_tools", 0),
                    "created_at": self._creation_timestamps.get(agent_name),
                })
            
            agents_list.append(agent_info)
        
        return agents_list

    def preload_all_agents(self) -> Dict[str, Any]:
        """
        Preload all configured agents for faster first-time access
        
        Returns:
            Summary of preload operation
        """
        logger.info("🚀 Preloading all configured agents...")
        start_time = time.time()
        
        results = {
            "total_agents": len(self._agent_configs),
            "successful": 0,
            "failed": 0,
            "errors": {},
            "agents_created": []
        }
        
        for agent_name in self._agent_configs.keys():
            try:
                if agent_name not in self._agents:
                    self._create_agent(agent_name)
                    results["agents_created"].append(agent_name)
                results["successful"] += 1
            except Exception as e:
                results["failed"] += 1
                results["errors"][agent_name] = str(e)
                logger.error(f" Failed to preload agent '{agent_name}': {str(e)}")
        
        total_time = time.time() - start_time
        results["total_time"] = total_time
        
        logger.info(f" Preload completed in {total_time:.2f}s: "
                   f"{results['successful']} successful, {results['failed']} failed")
        
        return results

    def reload_configuration(self) -> Dict[str, Any]:
        """
        Reload configuration from file and update registry
        Note: This will not affect already created agents
        """
        try:
            logger.info("🔄 Reloading agent configurations...")
            
            # Reload config from file
            self.config_loader.reload_config()
            
            # Store old configs for comparison
            old_configs = set(self._agent_configs.keys())
            
            # Load new configurations
            self._load_agent_configurations()
            
            new_configs = set(self._agent_configs.keys())
            
            # Calculate changes
            added = new_configs - old_configs
            removed = old_configs - new_configs
            
            logger.info(f" Configuration reloaded: {len(added)} added, {len(removed)} removed")
            
            return {
                "success": True,
                "agents_added": list(added),
                "agents_removed": list(removed),
                "total_agents": len(self._agent_configs),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            error_msg = f"Failed to reload configuration: {str(e)}"
            logger.error(f" {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "timestamp": datetime.utcnow().isoformat()
            }