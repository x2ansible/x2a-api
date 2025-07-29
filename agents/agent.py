import httpx
from typing import Dict, Any, List

class AgentManager:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.registered_agents = {}  # Maps agent name -> agent_id

    async def fetch_existing_agents(self):
        """
        Fetch existing agents from the LlamaStack server and update self.registered_agents.
        """
        url = f"{self.base_url}/v1/agents"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            # Typical format: {"data": [ ... ]}
            for agent in data.get("data", []):
                name = agent.get("agent_config", {}).get("name")
                agent_id = agent.get("agent_id")
                if name and agent_id:
                    self.registered_agents[name] = agent_id

    async def create_agent(self, agent_config: Dict[str, Any]) -> str:
        url = f"{self.base_url}/v1/agents"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json={"agent_config": agent_config})
            resp.raise_for_status()
            agent_id = resp.json().get("agent_id")
            if agent_id:
                self.registered_agents[agent_config["name"]] = agent_id
            return agent_id

    async def ensure_agents(self, agents_config: List[Dict[str, Any]]) -> Dict[str, str]:
        """
        Ensure all agents from config exist remotely, only create those missing by name.
        """
        await self.fetch_existing_agents()  # Get up-to-date list from server
        for cfg in agents_config:
            if cfg["name"] not in self.registered_agents:
                await self.create_agent(cfg)
        return self.registered_agents

    def get_agent_id(self, name: str) -> str:
        return self.registered_agents.get(name)

    # ---- New methods for enhanced LlamaStack API support ----
    
    async def delete_agent_from_server(self, agent_id: str) -> bool:
        """
        Delete an agent from the LlamaStack server.
        Returns True if successful, False if agent not found.
        """
        url = f"{self.base_url}/v1/agents/{agent_id}"
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.delete(url)
                resp.raise_for_status()
                return True
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    return False  # Agent not found
                raise e

    async def update_agent(self, agent_id: str, agent_config: Dict[str, Any]) -> bool:
        """
        Update an existing agent's configuration on the LlamaStack server.
        Returns True if successful, False if agent not found.
        """
        url = f"{self.base_url}/v1/agents/{agent_id}"
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.put(url, json={"agent_config": agent_config})
                resp.raise_for_status()
                return True
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    return False  # Agent not found
                raise e

    async def get_agent_details(self, agent_id: str) -> Dict[str, Any]:
        """
        Get detailed information about an agent from the LlamaStack server.
        """
        url = f"{self.base_url}/v1/agents/{agent_id}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()

    async def create_session(self, agent_id: str) -> Dict[str, Any]:
        """
        Create a new session for an agent.
        """
        url = f"{self.base_url}/v1/agents/{agent_id}/sessions"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url)
            resp.raise_for_status()
            return resp.json()

    async def list_sessions(self, agent_id: str) -> List[Dict[str, Any]]:
        """
        List all sessions for an agent.
        """
        url = f"{self.base_url}/v1/agents/{agent_id}/sessions"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", [])

    async def delete_session(self, agent_id: str, session_id: str) -> bool:
        """
        Delete a specific session for an agent.
        Returns True if successful, False if session not found.
        """
        url = f"{self.base_url}/v1/agents/{agent_id}/sessions/{session_id}"
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.delete(url)
                resp.raise_for_status()
                return True
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    return False  # Session not found
                raise e
