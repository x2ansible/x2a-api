from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Dict
from datetime import datetime
from fastapi.responses import StreamingResponse
import asyncio
import json

from agents.chef_analysis.agent import ChefAnalysisAgent

router = APIRouter(prefix="/chef", tags=["chef-analysis"])

class ChefAnalyzeRequest(BaseModel):
    files: Dict[str, str]

# === Singleton dependency: this is all you need! ===
def get_chef_agent(request: Request) -> ChefAnalysisAgent:
    return request.app.state.chef_analysis_agent

@router.post("/analyze")
async def analyze_cookbook(
    request: ChefAnalyzeRequest,
    agent: ChefAnalysisAgent = Depends(get_chef_agent),
):
    cookbook_name = f"uploaded_cookbook_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    cookbook_data = {
        "name": cookbook_name,
        "files": request.files,
    }
    try:
        result = await agent.analyze_cookbook(cookbook_data)
        result["session_info"] = {
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
    cookbook_name = f"uploaded_cookbook_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    async def event_generator():
        async for event in agent.analyze_cookbook_stream(
            {"name": cookbook_name, "files": request.files}
        ):
            if event.get("type") == "final_analysis" and "data" in event:
                event["data"]["session_info"] = {
                    "cookbook_name": cookbook_name
                }
            await asyncio.sleep(0.1)
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
