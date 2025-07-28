import yaml
import re
import os
from typing import Dict, List, Any, Optional

class ConfigLoader:
    """
    Loads and interpolates config.yaml for LlamaStack-based agentic apps.
    - Expands {agent_instructions.XYZ} references inside agents -> instructions.
    - Provides access to base_url, default_model, agents list, and agent_instructions.
    - Also provides access to prompt templates in the 'prompts' section.
    - Raises clear errors on misconfigurations.
    - Supports environment variable overrides for configuration.
    """

    def __init__(self, config_path: str = None):
        # Support environment variable override for config file path
        if config_path is None:
            config_path = os.getenv("CONFIG_FILE", "config.yaml")
        self.config_path = config_path
        self.config = self._load_config()
        self._agents = self._validate_and_interpolate()

    def _load_config(self) -> Dict[str, Any]:
        """Loads and parses the YAML config file."""
        try:
            with open(self.config_path, "r") as f:
                config = yaml.safe_load(f)
            if not config:
                raise ValueError("Config file is empty or invalid.")
            
            # Apply environment variable overrides
            config = self._apply_env_overrides(config)
            
            return config
        except Exception as e:
            raise RuntimeError(f"Failed to load config file '{self.config_path}': {e}")

    def _apply_env_overrides(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply environment variable overrides to configuration."""
        # Override llamastack base_url if environment variable is set
        if "llamastack" in config and "base_url" in config["llamastack"]:
            env_base_url = os.getenv("LLAMASTACK_BASE_URL")
            if env_base_url:
                config["llamastack"]["base_url"] = env_base_url
        
        # Override llamastack model if environment variable is set
        if "llamastack" in config:
            env_model = os.getenv("LLAMASTACK_MODEL")
            if env_model:
                config["llamastack"]["default_model"] = env_model
        
        # Override file storage upload directory if environment variable is set
        if "file_storage" in config:
            env_upload_dir = os.getenv("UPLOAD_DIR")
            if env_upload_dir:
                config["file_storage"]["upload_dir"] = env_upload_dir
        
        # Override vector DB settings if environment variables are set
        if "vector_db" in config:
            env_db_id = os.getenv("VECTOR_DB_ID")
            if env_db_id:
                config["vector_db"]["default_db_id"] = env_db_id
            
            env_chunk_size = os.getenv("VECTOR_DB_CHUNK_SIZE")
            if env_chunk_size:
                try:
                    config["vector_db"]["default_chunk_size"] = int(env_chunk_size)
                except ValueError:
                    pass  # Keep default if invalid integer
        
        return config

    def _validate_and_interpolate(self) -> List[Dict[str, Any]]:
        """Validates config and interpolates agent_instructions into agents."""
        # Validate llamastack section
        if "llamastack" not in self.config or "base_url" not in self.config["llamastack"]:
            raise ValueError("Config must include 'llamastack.base_url'")
        # Validate agents section
        if "agents" not in self.config or not isinstance(self.config["agents"], list):
            raise ValueError("Config must include 'agents' as a list.")

        instr_map = self.config.get("agent_instructions", {})
        out: List[Dict[str, Any]] = []
        for agent in self.config["agents"]:
            agent = dict(agent)  # Shallow copy
            instr = agent.get("instructions", "")
            # Interpolate instructions if referencing agent_instructions
            m = re.match(r"\{agent_instructions\.([^\}]+)\}", instr)
            if m:
                key = m.group(1)
                resolved = instr_map.get(key)
                if not resolved:
                    raise ValueError(
                        f"Instruction reference '{{agent_instructions.{key}}}' for agent '{agent.get('name')}' "
                        f"not found in 'agent_instructions' section."
                    )
                agent["instructions"] = resolved
            out.append(agent)
        return out

    def get_llamastack_base_url(self) -> str:
        """Returns LlamaStack API base URL from config."""
        return self.config["llamastack"]["base_url"]

    def get_llamastack_model(self) -> str:
        """Returns the default LlamaStack model name from config."""
        return self.config["llamastack"].get("default_model", "llama3-8b-instruct")

    def get_agents_config(self) -> List[Dict[str, Any]]:
        """
        Returns the interpolated agent configurations (instructions expanded!).
        This is what you should use to instantiate all agents.
        """
        return self._agents

    def get_agent_instructions(self, agent_name: str) -> Optional[str]:
        """Returns the instructions string for the named agent, if defined."""
        return self.config.get("agent_instructions", {}).get(agent_name)

    def get_agent_config(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """
        Returns the full config dictionary for a specific agent (by name).
        """
        for agent in self._agents:
            if agent.get("name") == agent_name:
                return agent
        return None

    def get_prompt_template(self, prompt_name: str) -> Optional[str]:
        """
        Returns the string template for a given prompt name (from 'prompts' section).
        """
        return self.config.get("prompts", {}).get(prompt_name)
