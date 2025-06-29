# config/config.py - Production-grade configuration loader
import os
import yaml
import logging
from typing import Dict, Any, List, Optional, Union
from pathlib import Path

logger = logging.getLogger(__name__)

class ConfigValidationError(Exception):
    """Custom exception for configuration validation errors"""
    pass

class ConfigLoader:
    """
    Production-grade configuration loader with comprehensive validation
    and error handling for unified agent system
    """
    
    def __init__(self, config_file: str = "config.yaml"):
        self.config_file = Path(config_file)
        self.config: Dict[str, Any] = {}
        self._load_and_validate_config()

    def _load_and_validate_config(self) -> None:
        """Load and validate configuration with detailed error reporting"""
        try:
            # Check if config file exists
            if not self.config_file.exists():
                raise ConfigValidationError(
                    f"Configuration file not found: {self.config_file.absolute()}\n"
                    f"Please ensure the config file exists at the specified path."
                )
            
            # Check if file is readable
            if not os.access(self.config_file, os.R_OK):
                raise ConfigValidationError(
                    f"Configuration file is not readable: {self.config_file.absolute()}\n"
                    f"Please check file permissions."
                )
            
            # Load YAML content
            try:
                with open(self.config_file, 'r', encoding='utf-8') as file:
                    self.config = yaml.safe_load(file)
            except yaml.YAMLError as e:
                raise ConfigValidationError(
                    f"Invalid YAML syntax in {self.config_file}:\n{str(e)}\n"
                    f"Please check YAML formatting and fix syntax errors."
                )
            except UnicodeDecodeError as e:
                raise ConfigValidationError(
                    f"Unable to read {self.config_file} - encoding issue:\n{str(e)}\n"
                    f"Please ensure the file is saved with UTF-8 encoding."
                )
            
            # Check if config is not empty
            if not self.config or not isinstance(self.config, dict):
                raise ConfigValidationError(
                    f"Configuration file {self.config_file} is empty or invalid.\n"
                    f"Expected a YAML dictionary with configuration sections."
                )
            
            # Validate required structure
            self._validate_config_structure()
            
            logger.info(f" Configuration loaded successfully from {self.config_file}")
            self._log_config_summary()
            
        except ConfigValidationError:
            # Re-raise validation errors as-is
            raise
        except Exception as e:
            # Wrap unexpected errors
            raise ConfigValidationError(
                f"Unexpected error loading configuration from {self.config_file}:\n{str(e)}"
            ) from e

    def _validate_config_structure(self) -> None:
        """Validate the overall configuration structure"""
        errors = []
        
        # Check required top-level sections
        required_sections = ["llamastack", "agents"]
        for section in required_sections:
            if section not in self.config:
                errors.append(f"Missing required section: '{section}'")
        
        # Validate LlamaStack configuration
        if "llamastack" in self.config:
            llamastack_errors = self._validate_llamastack_config()
            errors.extend(llamastack_errors)
        
        # Validate agents configuration
        if "agents" in self.config:
            agent_errors = self._validate_agents_config()
            errors.extend(agent_errors)
        
        # Raise combined errors if any
        if errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {error}" for error in errors)
            raise ConfigValidationError(error_msg)

    def _validate_llamastack_config(self) -> List[str]:
        """Validate LlamaStack configuration section"""
        errors = []
        llamastack = self.config.get("llamastack", {})
        
        if not isinstance(llamastack, dict):
            return ["llamastack section must be a dictionary"]
        
        # Check required fields
        base_url = llamastack.get("base_url")
        if not base_url:
            errors.append("llamastack.base_url is required")
        elif not isinstance(base_url, str):
            errors.append("llamastack.base_url must be a string")
        elif not base_url.startswith(("http://", "https://")):
            errors.append("llamastack.base_url must be a valid HTTP/HTTPS URL")
        
        # Check optional fields with defaults
        default_model = llamastack.get("default_model")
        if default_model is not None and not isinstance(default_model, str):
            errors.append("llamastack.default_model must be a string")
        
        timeout = llamastack.get("timeout")
        if timeout is not None:
            if not isinstance(timeout, (int, float)) or timeout <= 0:
                errors.append("llamastack.timeout must be a positive number")
        
        return errors

    def _validate_agents_config(self) -> List[str]:
        """Validate agents configuration section"""
        errors = []
        agents = self.config.get("agents", [])
        
        if not isinstance(agents, list):
            return ["agents section must be a list"]
        
        if not agents:
            errors.append("agents section cannot be empty - at least one agent is required")
            return errors
        
        agent_names = set()
        
        for i, agent in enumerate(agents):
            if not isinstance(agent, dict):
                errors.append(f"agents[{i}] must be a dictionary")
                continue
            
            # Validate individual agent
            agent_errors = self._validate_single_agent_config(agent, i)
            errors.extend(agent_errors)
            
            # Check for duplicate names
            agent_name = agent.get("name")
            if agent_name:
                if agent_name in agent_names:
                    errors.append(f"Duplicate agent name: '{agent_name}' (agents[{i}])")
                else:
                    agent_names.add(agent_name)
        
        return errors

    def _validate_single_agent_config(self, agent: Dict[str, Any], index: int) -> List[str]:
        """Validate a single agent configuration"""
        errors = []
        prefix = f"agents[{index}]"
        
        # Required fields
        name = agent.get("name")
        if not name:
            errors.append(f"{prefix}.name is required")
        elif not isinstance(name, str):
            errors.append(f"{prefix}.name must be a string")
        elif not name.strip():
            errors.append(f"{prefix}.name cannot be empty or whitespace")
        
        model = agent.get("model")
        if not model:
            errors.append(f"{prefix}.model is required")
        elif not isinstance(model, str):
            errors.append(f"{prefix}.model must be a string")
        
        instructions = agent.get("instructions")
        if not instructions:
            errors.append(f"{prefix}.instructions is required")
        elif not isinstance(instructions, str):
            errors.append(f"{prefix}.instructions must be a string")
        elif not instructions.strip():
            errors.append(f"{prefix}.instructions cannot be empty or whitespace")
        
        # Validate agent_pattern
        agent_pattern = agent.get("agent_pattern", "standard")
        if agent_pattern not in ["standard", "react"]:
            errors.append(f"{prefix}.agent_pattern must be 'standard' or 'react', got '{agent_pattern}'")
        
        # Validate optional fields
        tools = agent.get("tools")
        if tools is not None and not isinstance(tools, list):
            errors.append(f"{prefix}.tools must be a list")
        
        toolgroups = agent.get("toolgroups")
        if toolgroups is not None and not isinstance(toolgroups, list):
            errors.append(f"{prefix}.toolgroups must be a list")
        
        max_infer_iters = agent.get("max_infer_iters")
        if max_infer_iters is not None:
            if not isinstance(max_infer_iters, int) or max_infer_iters < 1:
                errors.append(f"{prefix}.max_infer_iters must be a positive integer")
        
        # Validate sampling_params
        sampling_params = agent.get("sampling_params")
        if sampling_params is not None:
            if not isinstance(sampling_params, dict):
                errors.append(f"{prefix}.sampling_params must be a dictionary")
            else:
                sampling_errors = self._validate_sampling_params(sampling_params, f"{prefix}.sampling_params")
                errors.extend(sampling_errors)
        
        return errors

    def _validate_sampling_params(self, params: Dict[str, Any], prefix: str) -> List[str]:
        """Validate sampling parameters"""
        errors = []
        valid_params = {
            "temperature", "top_p", "top_k", "max_tokens", 
            "repetition_penalty", "strategy"
        }
        
        # Check for unknown parameters
        unknown_params = set(params.keys()) - valid_params
        if unknown_params:
            errors.append(f"{prefix} contains unknown parameters: {unknown_params}")
        
        # Validate specific parameters
        temperature = params.get("temperature")
        if temperature is not None:
            if not isinstance(temperature, (int, float)) or not (0.0 <= temperature <= 2.0):
                errors.append(f"{prefix}.temperature must be a number between 0.0 and 2.0")
        
        top_p = params.get("top_p")
        if top_p is not None:
            if not isinstance(top_p, (int, float)) or not (0.0 <= top_p <= 1.0):
                errors.append(f"{prefix}.top_p must be a number between 0.0 and 1.0")
        
        top_k = params.get("top_k")
        if top_k is not None:
            if not isinstance(top_k, int) or top_k < 1:
                errors.append(f"{prefix}.top_k must be a positive integer")
        
        max_tokens = params.get("max_tokens")
        if max_tokens is not None:
            if not isinstance(max_tokens, int) or max_tokens < 1:
                errors.append(f"{prefix}.max_tokens must be a positive integer")
        
        repetition_penalty = params.get("repetition_penalty")
        if repetition_penalty is not None:
            if not isinstance(repetition_penalty, (int, float)) or repetition_penalty <= 0:
                errors.append(f"{prefix}.repetition_penalty must be a positive number")
        
        # Validate strategy if present
        strategy = params.get("strategy")
        if strategy is not None:
            if not isinstance(strategy, dict):
                errors.append(f"{prefix}.strategy must be a dictionary")
            else:
                strategy_type = strategy.get("type")
                if strategy_type and strategy_type not in ["greedy", "sampling"]:
                    errors.append(f"{prefix}.strategy.type must be 'greedy' or 'sampling'")
        
        return errors

    def _log_config_summary(self) -> None:
        """Log a summary of the loaded configuration"""
        try:
            llamastack_url = self.get_llamastack_base_url()
            agents = self.get_agents_config()
            
            logger.info(f"📋 Configuration Summary:")
            logger.info(f"   LlamaStack URL: {llamastack_url}")
            logger.info(f"   Default Model: {self.get_llamastack_model()}")
            logger.info(f"   Total Agents: {len(agents)}")
            
            for agent in agents:
                name = agent.get("name", "unnamed")
                pattern = agent.get("agent_pattern", "standard")
                model = agent.get("model", "unknown")
                tools_count = len(agent.get("tools", []))
                toolgroups_count = len(agent.get("toolgroups", []))
                
                logger.info(f"     - {name}: {pattern} agent using {model} "
                          f"({tools_count} tools, {toolgroups_count} toolgroups)")
                          
        except Exception as e:
            logger.warning(f"Could not log config summary: {e}")

    # Getter methods with proper error handling
    def get_llamastack_base_url(self) -> str:
        """Get LlamaStack base URL"""
        url = self.config.get("llamastack", {}).get("base_url", "")
        if not url:
            raise ConfigValidationError("LlamaStack base_url is not configured")
        return url

    def get_llamastack_model(self) -> str:
        """Get default LlamaStack model"""
        return self.config.get("llamastack", {}).get("default_model", "granite32-8b")

    def get_llamastack_timeout(self) -> int:
        """Get LlamaStack timeout"""
        return self.config.get("llamastack", {}).get("timeout", 180)

    def get_agents_config(self) -> List[Dict[str, Any]]:
        """Get all agent configurations"""
        return self.config.get("agents", [])

    def get_agent_config(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """Get specific agent configuration by name"""
        agents = self.get_agents_config()
        for agent in agents:
            if agent.get("name") == agent_name:
                return agent
        return None

    def get_file_storage_config(self) -> Dict[str, Any]:
        """Get file storage configuration with defaults"""
        default_config = {
            "upload_dir": "./uploads",
            "max_file_size": 10485760,  # 10MB
            "allowed_extensions": [".txt", ".md", ".yaml", ".yml", ".json", ".py", ".rb", ".sh"]
        }
        
        user_config = self.config.get("file_storage", {})
        default_config.update(user_config)
        return default_config

    def get_vector_db_config(self) -> Dict[str, Any]:
        """Get vector database configuration with defaults"""
        default_config = {
            "default_db_id": "iac",
            "default_chunk_size": 512
        }
        
        user_config = self.config.get("vector_db", {})
        default_config.update(user_config)
        return default_config

    def get_api_config(self) -> Dict[str, Any]:
        """Get API configuration with defaults"""
        default_config = {
            "title": "Unified Agent API",
            "version": "2.0.0",
            "description": "Unified multi-agent system"
        }
        
        user_config = self.config.get("api", {})
        default_config.update(user_config)
        return default_config

    def get_cors_config(self) -> Dict[str, Any]:
        """Get CORS configuration with defaults"""
        default_config = {
            "allow_origins": ["*"],
            "allow_credentials": True,
            "allow_methods": ["*"],
            "allow_headers": ["*"]
        }
        
        user_config = self.config.get("cors", {})
        default_config.update(user_config)
        return default_config

    def get_logging_config(self) -> Dict[str, Any]:
        """Get logging configuration with defaults"""
        default_config = {
            "level": "INFO",
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        }
        
        user_config = self.config.get("logging", {})
        default_config.update(user_config)
        return default_config

    def reload_config(self) -> None:
        """Reload configuration from file"""
        logger.info("🔄 Reloading configuration...")
        self._load_and_validate_config()
        logger.info(" Configuration reloaded successfully")

    def get_config_summary(self) -> Dict[str, Any]:
        """Get configuration summary for debugging"""
        try:
            agents = self.get_agents_config()
            agent_summary = []
            
            for agent in agents:
                agent_summary.append({
                    "name": agent.get("name"),
                    "pattern": agent.get("agent_pattern", "standard"),
                    "model": agent.get("model"),
                    "tools": len(agent.get("tools", [])),
                    "toolgroups": len(agent.get("toolgroups", [])),
                    "has_instructions": bool(agent.get("instructions", "").strip()),
                    "max_infer_iters": agent.get("max_infer_iters"),
                    "has_sampling_params": bool(agent.get("sampling_params"))
                })

            return {
                "config_file": str(self.config_file.absolute()),
                "config_exists": self.config_file.exists(),
                "config_readable": os.access(self.config_file, os.R_OK) if self.config_file.exists() else False,
                "llamastack_url": self.get_llamastack_base_url(),
                "llamastack_model": self.get_llamastack_model(),
                "llamastack_timeout": self.get_llamastack_timeout(),
                "total_agents": len(agents),
                "agents": agent_summary,
                "validation_status": "valid"
            }
        except Exception as e:
            return {
                "config_file": str(self.config_file.absolute()),
                "validation_status": "invalid",
                "error": str(e)
            }