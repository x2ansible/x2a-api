from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import asyncio
import json
import time

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

@router.post("/playbook/stream")
async def generate_playbook_stream(
    request: GenerateRequest,
    agent: CodeGeneratorAgent = Depends(get_codegen_agent),
):
    async def event_generator():
        start_time = time.time()
        
        # 1. Emit start event
        yield f"data: {json.dumps({'event': 'start', 'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'msg': 'Generation started'})}\n\n"
        await asyncio.sleep(0.1)
        
        # 2. Emit progress event
        yield f"data: {json.dumps({'event': 'progress', 'progress': 0.5, 'msg': 'Generating playbook...', 'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())})}\n\n"
        await asyncio.sleep(0.2)
        
        try:
            # 3. Actually generate the playbook
            result = await agent.generate(request.input_code, request.context or "")
            
            # 4. Emit result event
            yield f"data: {json.dumps({'event': 'result', 'playbook': result, 'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'processing_time': round(time.time() - start_time, 2)})}\n\n"
            
        except Exception as e:
            # Emit error event
            yield f"data: {json.dumps({'event': 'error', 'msg': f'Generation failed: {str(e)}', 'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )