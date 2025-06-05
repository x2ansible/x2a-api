import yaml
import re
from typing import Dict, List, Any

class ConfigLoader:
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.config = self._load_config()
        self._agents = self._validate_and_interpolate()

    def _load_config(self) -> Dict[str, Any]:
        try:
            with open(self.config_path, "r") as f:
                config = yaml.safe_load(f)
            if not config:
                raise ValueError("Config file is empty or invalid.")
            return config
        except Exception as e:
            raise RuntimeError(f"Failed to load config file '{self.config_path}': {e}")

    def _validate_and_interpolate(self) -> List[Dict[str, Any]]:
        # Validate
        if "llamastack" not in self.config or "base_url" not in self.config["llamastack"]:
            raise ValueError("Config must include 'llamastack.base_url'")
        if "agents" not in self.config or not isinstance(self.config["agents"], list):
            raise ValueError("Config must include 'agents' as a list.")

        instr_map = self.config.get("agent_instructions", {})
        out = []
        for agent in self.config["agents"]:
            agent = dict(agent)  # Shallow copy so we don't mutate the original dict
            # Interpolate instructions if referencing agent_instructions
            instr = agent.get("instructions", "")
            m = re.match(r"\{agent_instructions\.([^\}]+)\}", instr)
            if m:
                key = m.group(1)
                resolved = instr_map.get(key)
                if not resolved:
                    raise ValueError(
                        f"Instruction reference '{{agent_instructions.{key}}}' for agent '{agent['name']}' "
                        f"not found in 'agent_instructions' section."
                    )
                agent["instructions"] = resolved
            out.append(agent)
        return out

    def get_llamastack_base_url(self) -> str:
        return self.config["llamastack"]["base_url"]

    def get_agents_config(self) -> List[Dict[str, Any]]:
        return self._agents

    def get_default_model(self) -> str:
        return self.config["llamastack"].get("default_model", "llama3-8b-instruct")
    
    def __init__(self, config_path="config.yaml"):
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)

    def get_llamastack_base_url(self):
        # For flat config, no profile
        return self.config.get("llamastack", {}).get("base_url")

    def get_llamastack_model(self):
        # For flat config, no profile
        return self.config.get("llamastack", {}).get("default_model")

    def get_agents_config(self):
        return self.config.get("agents", [])

    def get_agent_instructions(self, agent_name):
        return self.config.get("agent_instructions", {}).get(agent_name)