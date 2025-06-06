from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional
import asyncio
import json

from agents.validate.validate_agent import create_validation_agent, ValidationAgent
from config.config import ConfigLoader

router = APIRouter(prefix="/validate", tags=["Validation"])
config_loader = ConfigLoader("config.yaml")

def get_validation_agent() -> ValidationAgent:
    return create_validation_agent(config_loader)  # <-- ONLY config_loader here

class ValidationRequest(BaseModel):
    playbook: str = Field(..., description="Ansible playbook YAML")
    profile: str = Field(default="basic", description="Lint profile to use")

@router.post("/playbook/stream")
async def validate_playbook_stream(
    request: ValidationRequest,
    agent: ValidationAgent = Depends(get_validation_agent)
):
    async def event_generator():
        try:
            async for event in agent.validate_playbook_stream(
                playbook=request.playbook,
                lint_profile=request.profile
            ):
                await asyncio.sleep(0.05)
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
