import httpx
import yaml
import logging

logger = logging.getLogger("agent_service")
logging.basicConfig(level=logging.INFO)

class AgentConfigLoader:
    def __init__(self, config_path="config.yaml"):
        with open(config_path) as f:
            self.config = yaml.safe_load(f)
        self.profile = self.config.get("active_profile", "local")
        self.defaults = self.config.get("defaults", {})
        self.profile_cfg = self.config.get("profiles", {}).get(self.profile, {})
        self.agent_instructions = self.config.get("agent_instructions", {})

    def get_llamastack_base_url(self):
        return (
            self.profile_cfg.get("llama_stack", {}).get("base_url")
            or self.defaults.get("llama_stack", {}).get("base_url")
        )

    def get_llamastack_model(self):
        return (
            self.profile_cfg.get("llama_stack", {}).get("model")
            or self.defaults.get("llama_stack", {}).get("model")
        )

    def get_agent_timeout(self, agent_name):
        return (
            self.profile_cfg.get("agents", {}).get(agent_name, {}).get("timeout")
            or self.defaults.get("agents", {}).get(agent_name, {}).get("timeout")
        )

    def get_agent_max_tokens(self, agent_name):
        return (
            self.profile_cfg.get("agents", {}).get(agent_name, {}).get("max_tokens")
            or self.defaults.get("agents", {}).get(agent_name, {}).get("max_tokens")
        )

    def get_agent_instructions(self, agent_name):
        return self.agent_instructions.get(agent_name, "")

def get_or_create_agent(cfg: AgentConfigLoader, agent_name: str) -> str:
    """Get or create agent by name. Returns agent_id."""
    base_url = cfg.get_llamastack_base_url()
    model = cfg.get_llamastack_model()
    instructions = cfg.get_agent_instructions(agent_name)
    max_tokens = cfg.get_agent_max_tokens(agent_name) or 2048

    # 1. Check if agent exists
    url = f"{base_url.rstrip('/')}/v1/agents"
    resp = httpx.get(url, timeout=30)
    resp.raise_for_status()
    for agent in resp.json().get("agents", []):
        if agent.get("name") == agent_name:
            logger.info(f"Reusing existing agent: {agent_name} (agent_id={agent['agent_id']})")
            return agent["agent_id"]

    # 2. Create agent if not exists
    payload = {
        "agent_config": {
            "model": model,
            "instructions": instructions,
            "name": agent_name,
            "sampling_params": {
                "strategy": {
                    "type": "top_p",
                    "temperature": 0.7,
                    "top_p": 0.9
                },
                "max_tokens": max_tokens,
                "repetition_penalty": 1.0
            },
            "max_infer_iters": 3
        }
    }
    resp = httpx.post(url, json=payload, timeout=30)
    resp.raise_for_status()
    agent_id = resp.json()["agent_id"]
    logger.info(f"Created new agent: {agent_name} (agent_id={agent_id})")
    return agent_id
