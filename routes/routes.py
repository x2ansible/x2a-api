import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Dict, Any

from agents.chef_analysis.agent import create_chef_analysis_agent, ChefAnalysisAgent
from config.config import ConfigLoader

import asyncio
import json
import traceback

# ---- Router Setup ----
router = APIRouter(prefix="/chef", tags=["chef-analysis"])

# ---- Global Config Loader ----
config_loader = ConfigLoader("config.yaml")

def get_chef_agent() -> ChefAnalysisAgent:
    # For production: use a singleton/lru_cache if agent creation is heavy
    return create_chef_analysis_agent(config_loader)

# ---- Pydantic Models ----
class ChefAnalyzeRequest(BaseModel):
    cookbook_name: str
    files: Dict[str, str]

# ---- Sync Endpoint ----
@router.post("/analyze")
async def analyze_cookbook(
    request: ChefAnalyzeRequest,
    agent: ChefAnalysisAgent = Depends(get_chef_agent)
):
    cookbook_data = {
        "name": request.cookbook_name,
        "files": request.files,
    }
    try:
        result = await agent.analyze_cookbook(cookbook_data)
        return result
    except Exception as e:
        logging.error(f"Error in analyze_cookbook: {e}")
        logging.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Analysis error: {str(e)}")

# ---- Streaming Endpoint ----
@router.post("/analyze/stream")
async def analyze_cookbook_stream(
    request: ChefAnalyzeRequest,
    agent: ChefAnalysisAgent = Depends(get_chef_agent)
):
    async def event_generator():
        try:
            async for event in agent.analyze_cookbook_stream(
                {"name": request.cookbook_name, "files": request.files}
            ):
                # Send each event as SSE
                await asyncio.sleep(0.05)  # throttle if needed
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            error_event = {
                "type": "error",
                "error": str(e),
            }
            yield f"data: {json.dumps(error_event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )

# ---- (Optional) Health/Debug Endpoint ----
@router.get("/health")
async def health():
    # Optionally add checks for agent/model availability
    return {"status": "ok"}
