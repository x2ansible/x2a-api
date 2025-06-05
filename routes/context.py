from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict, Any

from agents.context_agent.context_agent import create_context_agent, ContextAgent
from config.config import ConfigLoader

router = APIRouter(prefix="/context", tags=["context-agent"])
config_loader = ConfigLoader("config.yaml")

def get_context_agent() -> ContextAgent:
    return create_context_agent(config_loader)

class ContextRequest(BaseModel):
    code: str
    top_k: int = 5

@router.post("/query")
async def query_context(
    request: ContextRequest,
    agent: ContextAgent = Depends(get_context_agent),
):
    try:
        result = await agent.query_context(request.code, request.top_k)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Context query error: {e}")

from fastapi.responses import StreamingResponse
import asyncio
import json

@router.post("/query/stream")
async def query_context_stream(
    request: ContextRequest,
    agent: ContextAgent = Depends(get_context_agent),
):
    async def event_generator():
        async for event in agent.query_context_stream(request.code, request.top_k):
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
