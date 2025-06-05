from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from agents.code_generator.code_generator_agent import create_codegen_agent, CodeGeneratorAgent
from config.config import ConfigLoader

router = APIRouter(prefix="/generate", tags=["code-generator"])
config_loader = ConfigLoader("config.yaml")

def get_codegen_agent() -> CodeGeneratorAgent:
    return create_codegen_agent(config_loader)

class GenerateRequest(BaseModel):
    input_code: str
    context: Optional[str] = None

@router.post("/playbook")
async def generate_playbook(
    request: GenerateRequest,
    agent: CodeGeneratorAgent = Depends(get_codegen_agent),
):
    try:
        result = await agent.generate(request.input_code, request.context or "")
        return {"playbook": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Playbook generation error: {e}")

from fastapi.responses import StreamingResponse
import asyncio
import json

@router.post("/playbook/stream")
async def generate_playbook_stream(
    request: GenerateRequest,
    agent: CodeGeneratorAgent = Depends(get_codegen_agent),
):
    async def event_generator():
        async for event in agent.generate_stream(request.input_code, request.context or ""):
            await asyncio.sleep(0.1)  # adjust or remove in prod
            yield f"data: {json.dumps(event)}\n\n"
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
