from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict, Any

from agents.chef_analysis.agent import create_chef_analysis_agent, ChefAnalysisAgent
from config.config import ConfigLoader

router = APIRouter(prefix="/chef", tags=["chef-analysis"])

config_loader = ConfigLoader("config.yaml")

def get_chef_agent() -> ChefAnalysisAgent:
    return create_chef_analysis_agent(config_loader)

class ChefAnalyzeRequest(BaseModel):
    cookbook_name: str
    files: Dict[str, str]

@router.post("/analyze")
async def analyze_cookbook(
    request: ChefAnalyzeRequest,
    agent: ChefAnalysisAgent = Depends(get_chef_agent),
):
    cookbook_data = {
        "name": request.cookbook_name,
        "files": request.files,
    }
    try:
        # Your existing working code - UNCHANGED
        result = await agent.analyze_cookbook(cookbook_data)
        
        # NEW: Just add session info to the response (for context agent workflow)
        result["session_info"] = {
            "agent_id": agent.agent.agent_id,
            "cookbook_name": request.cookbook_name
        }
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis error: {e}")

from fastapi.responses import StreamingResponse
import asyncio
import json

@router.post("/analyze/stream")
async def analyze_cookbook_stream(
    request: ChefAnalyzeRequest,
    agent: ChefAnalysisAgent = Depends(get_chef_agent),
):
    async def event_generator():
        agent_id = agent.agent.agent_id  # Get for session info
        
        async for event in agent.analyze_cookbook_stream(
            {"name": request.cookbook_name, "files": request.files}
        ):
            # NEW: Add session info to final streaming result
            if event.get("type") == "final_analysis" and "data" in event:
                event["data"]["session_info"] = {
                    "agent_id": agent_id,
                    "cookbook_name": request.cookbook_name
                }
            
            await asyncio.sleep(0.1)  # throttle for demo
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )