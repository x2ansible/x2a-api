from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel, Field
from typing import Dict, Optional
from datetime import datetime
from fastapi.responses import StreamingResponse
import asyncio
import json

from agents.chef_analysis.agent import ChefAnalysisAgent

router = APIRouter(prefix="/chef", tags=["chef-analysis"])

class ChefAnalyzeRequest(BaseModel):
    files: Dict[str, str] = Field(..., description="Dictionary of filename to file content")

class ChefAnalysisResponse(BaseModel):
    success: bool
    cookbook_name: str
    analysis_method: str
    version_requirements: Dict
    dependencies: Dict
    functionality: Dict
    recommendations: Dict
    session_info: Dict
    metadata: Optional[Dict] = None

# Dependency injection for ChefAnalysisAgent
def get_chef_agent(request: Request) -> ChefAnalysisAgent:
    if not hasattr(request.app.state, 'chef_analysis_agent'):
        raise HTTPException(status_code=503, detail="Chef analysis agent not available")
    return request.app.state.chef_analysis_agent

@router.post("/analyze", response_model=ChefAnalysisResponse)
async def analyze_cookbook(
    request: ChefAnalyzeRequest,
    agent: ChefAnalysisAgent = Depends(get_chef_agent),
):
    """
    Analyze Chef cookbook using standard single-prompt analysis
    """
    cookbook_name = f"uploaded_cookbook_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    cookbook_data = {
        "name": cookbook_name,
        "files": request.files,
    }
    
    try:
        result = await agent.analyze_cookbook(cookbook_data=cookbook_data)
        
        result["session_info"] = {
            **result.get("session_info", {}),
            "cookbook_name": cookbook_name
        }
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis error: {e}")

@router.post("/analyze/stream")
async def analyze_cookbook_stream(
    request: ChefAnalyzeRequest,
    agent: ChefAnalysisAgent = Depends(get_chef_agent),
):
    """
    Stream Chef cookbook analysis with real-time progress updates
    
    **Event Types:**
    - `progress`: Analysis progress updates
    - `final_analysis`: Complete analysis result
    - `error`: Error information
    """
    cookbook_name = f"stream_cookbook_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    cookbook_data = {
        "name": cookbook_name,
        "files": request.files,
    }
    
    async def event_generator():
        try:
            async for event in agent.analyze_cookbook_stream(cookbook_data=cookbook_data):
                if event.get("type") == "final_analysis" and "data" in event:
                    event["data"]["session_info"] = {
                        **event["data"].get("session_info", {}),
                        "cookbook_name": cookbook_name
                    }
                await asyncio.sleep(0.1)
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            error_event = {
                "type": "error",
                "error": str(e),
                "cookbook_name": cookbook_name
            }
            yield f"data: {json.dumps(error_event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )

@router.get("/status")
async def get_analysis_status(request: Request):
    """Get status of the Chef analysis agent"""
    status = {
        "timestamp": datetime.now().isoformat(),
        "agent_available": False,
        "agent_status": {}
    }
    
    # Check agent availability and status
    if hasattr(request.app.state, 'chef_analysis_agent'):
        try:
            agent = request.app.state.chef_analysis_agent
            status["agent_available"] = True
            status["agent_status"] = agent.get_status()
            status["agent_status"]["health"] = await agent.health_check()
        except Exception as e:
            status["agent_status"] = {"error": str(e), "health": False}
    
    return status

@router.get("/capabilities")
async def get_chef_capabilities():
    """Get detailed information about Chef analysis capabilities"""
    return {
        "analysis_capabilities": {
            "version_requirements": {
                "description": "Determines minimum Chef and Ruby version requirements",
                "outputs": ["min_chef_version", "min_ruby_version", "migration_effort", "estimated_hours", "deprecated_features"]
            },
            "dependency_analysis": {
                "description": "Maps cookbook dependencies and wrapper patterns",
                "outputs": ["is_wrapper", "wrapped_cookbooks", "direct_deps", "runtime_deps", "circular_risk"]
            },
            "functionality_assessment": {
                "description": "Analyzes what the cookbook does and how it can be used",
                "outputs": ["primary_purpose", "services", "packages", "files_managed", "reusability", "customization_points"]
            },
            "strategic_recommendations": {
                "description": "Provides migration and consolidation guidance",
                "outputs": ["consolidation_action", "rationale", "migration_priority", "risk_factors"]
            }
        },
        "supported_cookbook_types": [
            "wrapper cookbooks",
            "library cookbooks", 
            "application cookbooks",
            "custom cookbooks"
        ],
        "supported_file_types": [
            "metadata.rb",
            "recipes/*.rb",
            "attributes/*.rb", 
            "templates/*",
            "files/*",
            "libraries/*.rb"
        ],
        "analysis_method": {
            "type": "standard",
            "description": "Single comprehensive prompt analysis",
            "benefits": ["Fast execution", "Simple architecture", "Reliable results"]
        },
        "output_formats": ["JSON", "Streaming JSON"],
        "session_management": "Dedicated sessions per analysis for context isolation"
    }

# Health check endpoint
@router.get("/health")
async def health_check(request: Request):
    """Health check for Chef analysis service"""
    try:
        if not hasattr(request.app.state, 'chef_analysis_agent'):
            return {"status": "unhealthy", "reason": "Agent not initialized"}
        
        agent = request.app.state.chef_analysis_agent
        health_ok = await agent.health_check()
        
        return {
            "status": "healthy" if health_ok else "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "agent_id": agent.agent_id
        }
    except Exception as e:
        return {
            "status": "unhealthy", 
            "reason": str(e),
            "timestamp": datetime.now().isoformat()
        }