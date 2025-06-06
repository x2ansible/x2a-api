from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import asyncio
import json
import time
import logging
from datetime import datetime

from agents.code_generator.code_generator_agent import CodeGeneratorAgent

router = APIRouter(prefix="/generate", tags=["code-generator"])
logger = logging.getLogger("codegen_routes")

def get_codegen_agent(request: Request) -> CodeGeneratorAgent:
    """Get CodeGeneratorAgent from app state (Meta pattern)"""
    if not hasattr(request.app.state, 'codegen_agent'):
        raise HTTPException(status_code=503, detail="CodeGeneratorAgent not available")
    return request.app.state.codegen_agent

class GenerateRequest(BaseModel):
    input_code: str
    context: Optional[str] = None

class GeneratePlaybookRequest(BaseModel):
    input_code: str
    context: Optional[str] = None

# === MAIN ENDPOINTS ===

@router.post("/playbook")
async def generate_playbook(
    request: GeneratePlaybookRequest,
    agent: CodeGeneratorAgent = Depends(get_codegen_agent),
):
    """Generate Ansible playbook from input code"""
    try:
        result = await agent.generate(
            input_code=request.input_code,
            context=request.context or ""
        )
        
        return {
            "success": True,
            "playbook": result,
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "input_length": len(request.input_code),
                "context_length": len(request.context or ""),
                "output_length": len(result)
            }
        }
    except Exception as e:
        logger.error(f"Playbook generation error: {e}")
        raise HTTPException(status_code=500, detail=f"Playbook generation error: {e}")

@router.post("/playbook/stream")
async def generate_playbook_stream(
    request: GeneratePlaybookRequest,
    agent: CodeGeneratorAgent = Depends(get_codegen_agent),
):
    """Stream playbook generation results"""
    async def event_generator():
        async for event in agent.generate_stream(
            input_code=request.input_code,
            context=request.context or ""
        ):
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

# === LEGACY ENDPOINTS (for backward compatibility) ===

@router.post("/")
async def generate_legacy(
    request: GenerateRequest,
    agent: CodeGeneratorAgent = Depends(get_codegen_agent),
):
    """Legacy endpoint - maintains old interface"""
    try:
        result = await agent.generate(request.input_code, request.context or "")
        return {"playbook": result}
    except Exception as e:
        logger.error(f"Legacy generation error: {e}")
        raise HTTPException(status_code=500, detail=f"Playbook generation error: {e}")

@router.post("/stream")
async def generate_legacy_stream(
    request: GenerateRequest,
    agent: CodeGeneratorAgent = Depends(get_codegen_agent),
):
    """Legacy streaming endpoint - maintains old interface"""
    async def event_generator():
        start_time = time.time()
        
        try:
            # 1. Emit start event
            yield f"data: {json.dumps({'event': 'start', 'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'msg': 'Generation started'})}\n\n"
            await asyncio.sleep(0.1)
            
            # 2. Emit progress event
            yield f"data: {json.dumps({'event': 'progress', 'progress': 0.5, 'msg': 'Generating playbook...', 'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())})}\n\n"
            await asyncio.sleep(0.2)
            
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

# === STATUS AND HEALTH ENDPOINTS ===

@router.get("/status")
async def get_codegen_status(
    agent: CodeGeneratorAgent = Depends(get_codegen_agent),
):
    """Get code generator agent status"""
    try:
        return {
            "status": "ready",
            "agent_info": agent.get_status(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Status check failed: {e}")

@router.post("/health")
async def codegen_health_check(
    agent: CodeGeneratorAgent = Depends(get_codegen_agent),
):
    """Perform health check on code generator agent"""
    try:
        is_healthy = await agent.health_check()
        return {
            "healthy": is_healthy,
            "agent_id": agent.agent_id,
            "pattern": "Meta Direct API",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "healthy": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }