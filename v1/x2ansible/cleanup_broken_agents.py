# cleanup_broken_agents.py
import httpx

LLAMASTACK_URL = "http://lss-chai.apps.cluster-7nc6z.7nc6z.sandbox2170.opentlc.com"

def delete_broken_agents():
    try:
        # Get all agents
        response = httpx.get(f"{LLAMASTACK_URL}/v1/agents", timeout=30)
        response.raise_for_status()
        agents = response.json().get("data", [])
        
        # Find agents with None names
        broken_agents = []
        for agent in agents:
            agent_config = agent.get("agent_config", {})
            name = agent_config.get("name")
            if name is None or name == "None" or name == "":
                broken_agents.append(agent.get("agent_id"))
        
        print(f"Found {len(broken_agents)} broken agents to delete")
        
        # Delete them
        for agent_id in broken_agents:
            try:
                del_response = httpx.delete(f"{LLAMASTACK_URL}/v1/agents/{agent_id}", timeout=30)
                del_response.raise_for_status()
                print(f" Deleted broken agent: {agent_id}")
            except Exception as e:
                print(f" Failed to delete {agent_id}: {e}")
        
        print("Cleanup complete!")
        
    except Exception as e:
        print(f"Error during cleanup: {e}")

if __name__ == "__main__":
    delete_broken_agents()