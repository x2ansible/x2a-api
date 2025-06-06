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

# ---- Agent Management Endpoints ----
@router.post("/agents", response_model=AgentResponse)
async def create_agent(request: CreateAgentRequest, app_request: Request):
    """Create a new agent and register it with LlamaStack"""
    try:
        # Get agent manager from app state
        agent_manager = app_request.app.state.agent_manager
        
        agent_config = {
            "name": request.name,
            "model": request.model,
            "instructions": request.instructions,
            "tools": request.tools
        }
        
        logger.info(f"Creating new agent: {request.name}")
        agent_id = await agent_manager.create_agent(agent_config)
        
        logger.info(f"Agent created successfully: {request.name} -> {agent_id}")
        return AgentResponse(
            agent_id=agent_id,
            name=request.name,
            status="created"
        )
    except Exception as e:
        logger.error(f"Agent creation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Agent creation failed: {str(e)}")

@router.get("/agents", response_model=AgentListResponse)
async def list_agents(app_request: Request):
    """List all registered agents"""
    try:
        agent_manager = app_request.app.state.agent_manager
        agents = agent_manager.registered_agents
        
        return AgentListResponse(
            agents=agents,
            count=len(agents)
        )
    except Exception as e:
        logger.error(f"Failed to list agents: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list agents: {str(e)}")

@router.get("/agents/{agent_name}")
async def get_agent(agent_name: str, app_request: Request):
    """Get specific agent details"""
    try:
        agent_manager = app_request.app.state.agent_manager
        agent_id = agent_manager.get_agent_id(agent_name)
        
        if not agent_id:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
        
        return {
            "name": agent_name,
            "agent_id": agent_id,
            "status": "active"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agent {agent_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get agent: {str(e)}")

@router.delete("/agents/{agent_name}")
async def delete_agent(agent_name: str, app_request: Request):
    """Remove an agent from the registry (Note: doesn't delete from LlamaStack server)"""
    try:
        agent_manager = app_request.app.state.agent_manager
        
        if agent_name not in agent_manager.registered_agents:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
        
        # Remove from local registry
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
    """Refresh agent list from LlamaStack server"""
    try:
        agent_manager = app_request.app.state.agent_manager
        
        # Fetch latest agents from server
        await agent_manager.fetch_existing_agents()
        
        return {
            "message": "Agent list refreshed",
            "agents": agent_manager.registered_agents,
            "count": len(agent_manager.registered_agents)
        }
    except Exception as e:
        logger.error(f"Failed to refresh agents: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to refresh agents: {str(e)}")

# ---- System Health Endpoints ----
@router.get("/health")
async def admin_health():
    """Admin health check"""
    return {
        "status": "healthy",
        "service": "X2A Agents API Admin",
        "endpoints": [
            "GET /admin/agents - List agents",
            "POST /admin/agents - Create agent", 
            "GET /admin/agents/{name} - Get agent",
            "DELETE /admin/agents/{name} - Remove agent",
            "POST /admin/agents/refresh - Refresh agent list"
        ]
    }

@router.get("/info")
async def system_info(app_request: Request):
    """Get system information"""
    try:
        agent_manager = app_request.app.state.agent_manager
        
        return {
            "title": "X2A Agents API",
            "version": "1.0.0", 
            "description": "Multi-agent IaC API (Chef, Context, Generate, Validate)",
            "llamastack_url": agent_manager.base_url,
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