import logging
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Dict, Any, List, Optional

logger = logging.getLogger("admin")
router = APIRouter(prefix="/admin", tags=["admin"])

# ---- Pydantic Models ----
class CreateAgentRequest(BaseModel):
    name: str
    model: str
    instructions: str
    tools: Optional[List[Dict[str, Any]]] = []

class AgentResponse(BaseModel):
    agent_id: str
    name: str
    status: str

class AgentListResponse(BaseModel):
    agents: Dict[str, str]
    count: int

class AgentInstructionsResponse(BaseModel):
    agent_name: str
    instructions: str
    model: str
    tools: List[Any]
    sampling_params: Dict[str, Any] = {}

# ---- New Pydantic Models for Enhanced Operations ----
class UpdateAgentRequest(BaseModel):
    model: str
    instructions: str
    tools: Optional[List[Dict[str, Any]]] = []

class AgentDetailsResponse(BaseModel):
    agent_id: str
    name: str
    agent_config: Dict[str, Any]
    status: str

class SessionResponse(BaseModel):
    session_id: str
    agent_id: str
    status: str

class SessionListResponse(BaseModel):
    sessions: List[Dict[str, Any]]
    count: int

# ---- Agent Management Endpoints ----
@router.post("/agents", response_model=AgentResponse)
async def create_agent(request: CreateAgentRequest, app_request: Request):
    """
    Create a new agent and register it with LlamaStack.
    """
    try:
        agent_manager = app_request.app.state.agent_manager
        agent_config = {
            "name": request.name,
            "model": request.model,
            "instructions": request.instructions,
            "tools": request.tools
        }
        logger.info(f"Creating new agent: {request.name}")
        agent_id = await agent_manager.create_agent(agent_config)
        logger.info(f"Agent created: {request.name} -> {agent_id}")
        return AgentResponse(agent_id=agent_id, name=request.name, status="created")
    except Exception as e:
        logger.error(f"Agent creation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Agent creation failed: {str(e)}")

@router.get("/agents", response_model=AgentListResponse)
async def list_agents(app_request: Request):
    """
    List all registered agents.
    """
    try:
        agent_manager = app_request.app.state.agent_manager
        agents = agent_manager.registered_agents
        return AgentListResponse(agents=agents, count=len(agents))
    except Exception as e:
        logger.error(f"Failed to list agents: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list agents: {str(e)}")

@router.get("/agents/{agent_name}")
async def get_agent(agent_name: str, app_request: Request):
    """
    Get specific agent details.
    """
    try:
        agent_manager = app_request.app.state.agent_manager
        agent_id = agent_manager.get_agent_id(agent_name)
        if not agent_id:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
        return {"name": agent_name, "agent_id": agent_id, "status": "active"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agent {agent_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get agent: {str(e)}")

@router.delete("/agents/{agent_name}")
async def delete_agent(agent_name: str, app_request: Request):
    """
    Remove an agent from the registry (does not delete from LlamaStack server).
    """
    try:
        agent_manager = app_request.app.state.agent_manager
        if agent_name not in agent_manager.registered_agents:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
        agent_id = agent_manager.registered_agents.pop(agent_name)
        logger.info(f"Agent removed from registry: {agent_name}")
        return {
            "message": f"Agent '{agent_name}' removed from registry",
            "agent_id": agent_id,
            "note": "Agent may still exist on LlamaStack server"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete agent {agent_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete agent: {str(e)}")

@router.post("/agents/refresh")
async def refresh_agents(app_request: Request):
    """
    Refresh agent list from LlamaStack server.
    """
    try:
        agent_manager = app_request.app.state.agent_manager
        await agent_manager.fetch_existing_agents()
        return {
            "message": "Agent list refreshed",
            "agents": agent_manager.registered_agents,
            "count": len(agent_manager.registered_agents)
        }
    except Exception as e:
        logger.error(f"Failed to refresh agents: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to refresh agents: {str(e)}")

# ---- New Enhanced Agent Management Endpoints ----

@router.delete("/agents/{agent_name}/remote")
async def delete_agent_from_llamastack(agent_name: str, app_request: Request):
    """
    Delete an agent from the LlamaStack server.
    This is different from the regular delete endpoint which only removes from local registry.
    """
    try:
        agent_manager = app_request.app.state.agent_manager
        agent_id = agent_manager.get_agent_id(agent_name)
        if not agent_id:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
        
        success = await agent_manager.delete_agent_from_server(agent_id)
        if success:
            # Remove from local registry as well
            agent_manager.registered_agents.pop(agent_name, None)
            logger.info(f"Agent deleted from LlamaStack server: {agent_name}")
            return {
                "message": f"Agent '{agent_name}' deleted from LlamaStack server",
                "agent_id": agent_id,
                "status": "deleted"
            }
        else:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found on LlamaStack server")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete agent {agent_name} from server: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete agent from server: {str(e)}")

@router.put("/agents/{agent_name}")
async def update_agent(agent_name: str, request: UpdateAgentRequest, app_request: Request):
    """
    Update an existing agent's configuration on the LlamaStack server.
    """
    try:
        agent_manager = app_request.app.state.agent_manager
        agent_id = agent_manager.get_agent_id(agent_name)
        if not agent_id:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
        
        agent_config = {
            "name": agent_name,
            "model": request.model,
            "instructions": request.instructions,
            "tools": request.tools
        }
        
        success = await agent_manager.update_agent(agent_id, agent_config)
        if success:
            logger.info(f"Agent updated on LlamaStack server: {agent_name}")
            return {
                "message": f"Agent '{agent_name}' updated successfully",
                "agent_id": agent_id,
                "status": "updated"
            }
        else:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found on LlamaStack server")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update agent {agent_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update agent: {str(e)}")

@router.get("/agents/{agent_name}/details", response_model=AgentDetailsResponse)
async def get_agent_details(agent_name: str, app_request: Request):
    """
    Get detailed information about an agent from the LlamaStack server.
    """
    try:
        agent_manager = app_request.app.state.agent_manager
        agent_id = agent_manager.get_agent_id(agent_name)
        if not agent_id:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
        
        agent_details = await agent_manager.get_agent_details(agent_id)
        return AgentDetailsResponse(
            agent_id=agent_id,
            name=agent_name,
            agent_config=agent_details.get("agent_config", {}),
            status="active"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agent details for {agent_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get agent details: {str(e)}")

# ---- Session Management Endpoints ----

@router.post("/agents/{agent_name}/sessions", response_model=SessionResponse)
async def create_session(agent_name: str, app_request: Request):
    """
    Create a new session for an agent.
    """
    try:
        agent_manager = app_request.app.state.agent_manager
        agent_id = agent_manager.get_agent_id(agent_name)
        if not agent_id:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
        
        session_data = await agent_manager.create_session(agent_id)
        session_id = session_data.get("session_id")
        
        logger.info(f"Session created for agent {agent_name}: {session_id}")
        return SessionResponse(
            session_id=session_id,
            agent_id=agent_id,
            status="created"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create session for agent {agent_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")

@router.get("/agents/{agent_name}/sessions", response_model=SessionListResponse)
async def list_sessions(agent_name: str, app_request: Request):
    """
    List all sessions for an agent.
    """
    try:
        agent_manager = app_request.app.state.agent_manager
        agent_id = agent_manager.get_agent_id(agent_name)
        if not agent_id:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
        
        sessions = await agent_manager.list_sessions(agent_id)
        return SessionListResponse(sessions=sessions, count=len(sessions))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list sessions for agent {agent_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list sessions: {str(e)}")

@router.delete("/agents/{agent_name}/sessions/{session_id}")
async def delete_session(agent_name: str, session_id: str, app_request: Request):
    """
    Delete a specific session for an agent.
    """
    try:
        agent_manager = app_request.app.state.agent_manager
        agent_id = agent_manager.get_agent_id(agent_name)
        if not agent_id:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
        
        success = await agent_manager.delete_session(agent_id, session_id)
        if success:
            logger.info(f"Session {session_id} deleted for agent {agent_name}")
            return {
                "message": f"Session {session_id} deleted successfully",
                "agent_name": agent_name,
                "session_id": session_id
            }
        else:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete session {session_id} for agent {agent_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete session: {str(e)}")

# ---- System Health & Info ----
@router.get("/health")
async def admin_health():
    """
    Admin health check endpoint.
    """
    return {
        "status": "healthy",
        "service": "X2A Agents API Admin",
        "endpoints": [
            "GET /admin/agents",
            "POST /admin/agents", 
            "GET /admin/agents/{name}",
            "DELETE /admin/agents/{name}",
            "POST /admin/agents/refresh",
            "DELETE /admin/agents/{name}/remote",
            "PUT /admin/agents/{name}",
            "GET /admin/agents/{name}/details",
            "POST /admin/agents/{name}/sessions",
            "GET /admin/agents/{name}/sessions",
            "DELETE /admin/agents/{name}/sessions/{session_id}"
        ]
    }

@router.get("/info")
async def system_info(app_request: Request):
    """
    Get system information.
    """
    try:
        agent_manager = app_request.app.state.agent_manager
        return {
            "title": "X2A Agents API",
            "version": "1.0.0", 
            "description": "Multi-agent IaC API (Chef, Context, Generate, Validate)",
            "llamastack_url": getattr(agent_manager, 'base_url', None),
            "registered_agents": len(agent_manager.registered_agents),
            "available_routes": [
                "/chef - Chef cookbook analysis",
                "/context - Knowledge search", 
                "/generate - Code generation",
                "/validate - Playbook validation",
                "/admin - Agent management"
            ]
        }
    except Exception as e:
        logger.error(f"Failed to get system info: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get system info: {str(e)}")

@router.get("/agents/{agent_name}/instructions", response_model=AgentInstructionsResponse)
async def get_agent_instructions(agent_name: str, app_request: Request):
    """
    Get agent instructions and config from YAML config.
    """
    try:
        # Get config loader from app state or create new one
        if hasattr(app_request.app.state, 'config_loader'):
            config_loader = app_request.app.state.config_loader
        else:
            from config.config import ConfigLoader
            config_loader = ConfigLoader("config.yaml")
        agent_config = config_loader.get_agent_config(agent_name)
        if not agent_config:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
        return AgentInstructionsResponse(
            agent_name=agent_name,
            instructions=agent_config.get("instructions", ""),
            model=agent_config.get("model", ""),
            tools=agent_config.get("tools", []),
            sampling_params=agent_config.get("sampling_params", {}) or {}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get instructions for {agent_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get agent instructions: {str(e)}")
