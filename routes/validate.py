from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional
import asyncio
import json
import logging
from datetime import datetime

from agents.validate.validate_agent import ValidationAgent

router = APIRouter(prefix="/validate", tags=["validation"])
logger = logging.getLogger("validation_routes")

def get_validation_agent(request: Request) -> ValidationAgent:
    """Get ValidationAgent from app state """
    if not hasattr(request.app.state, 'validation_agent'):
        raise HTTPException(status_code=503, detail="ValidationAgent not available")
    return request.app.state.validation_agent

class ValidationRequest(BaseModel):
    playbook: str = Field(..., description="Ansible playbook YAML")
    profile: str = Field(default="basic", description="Lint profile to use")

class ValidatePlaybookRequest(BaseModel):
    playbook: str = Field(..., description="Ansible playbook YAML content")
    profile: Optional[str] = Field(default="basic", description="Lint profile to use (basic, moderate, safety, shared, production)")

# === MAIN ENDPOINTS ===

@router.post("/playbook")
async def validate_playbook(
    request: ValidatePlaybookRequest,
    agent: ValidationAgent = Depends(get_validation_agent),
):
    """Validate Ansible playbook using the validation agent"""
    try:
        result = await agent.validate_playbook(
            playbook=request.playbook,
            lint_profile=request.profile
        )
        
        return {
            "success": result.get("success", False),
            "validation_passed": result.get("validation_passed", False),
            "summary": result.get("summary", {}),
            "issues": result.get("issues", []),
            "recommendations": result.get("recommendations", []),
            "agent_analysis": result.get("agent_analysis", ""),
            "metadata": {
                "lint_profile": request.profile,
                "playbook_length": len(request.playbook),
                "timestamp": datetime.now().isoformat(),
                "exit_code": result.get("exit_code", -1)
            }
        }
    except Exception as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=500, detail=f"Validation error: {e}")

@router.post("/playbook/stream")
async def validate_playbook_stream(
    request: ValidatePlaybookRequest,
    agent: ValidationAgent = Depends(get_validation_agent),
):
    """Stream validation results"""
    async def event_generator():
        async for event in agent.validate_playbook_stream(
            playbook=request.playbook,
            lint_profile=request.profile
        ):
            await asyncio.sleep(0.05)
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
async def validate_legacy(
    request: ValidationRequest,
    agent: ValidationAgent = Depends(get_validation_agent),
):
    """Legacy endpoint - maintains old interface"""
    try:
        result = await agent.validate_playbook(
            playbook=request.playbook,
            lint_profile=request.profile
        )
        return result
    except Exception as e:
        logger.error(f"Legacy validation error: {e}")
        raise HTTPException(status_code=500, detail=f"Validation error: {e}")

@router.post("/stream")
async def validate_legacy_stream(
    request: ValidationRequest,
    agent: ValidationAgent = Depends(get_validation_agent),
):
    """Legacy streaming endpoint - maintains old interface"""
    async def event_generator():
        try:
            async for event in agent.validate_playbook_stream(
                playbook=request.playbook,
                lint_profile=request.profile
            ):
                # Convert to legacy format
                if event.get("type") == "progress":
                    yield f"data: {json.dumps({'event': 'start', 'timestamp': datetime.now().isoformat(), 'msg': 'Validation started'})}\n\n"
                elif event.get("type") == "final_validation":
                    result_data = event.get("data", {})
                    legacy_event = {
                        'event': 'result',
                        **result_data,
                        'timestamp': datetime.now().isoformat(),
                        'processing_time': event.get('processing_time', 0)
                    }
                    yield f"data: {json.dumps(legacy_event)}\n\n"
                elif event.get("type") == "error":
                    error_msg = event.get("error", "Unknown error")
                    yield f"data: {json.dumps({'event': 'error', 'msg': f'Validation failed: {error_msg}', 'timestamp': datetime.now().isoformat()})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'event': 'error', 'msg': f'Validation failed: {str(e)}', 'timestamp': datetime.now().isoformat()})}\n\n"

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
async def get_validation_status(
    agent: ValidationAgent = Depends(get_validation_agent),
):
    """Get validation agent status"""
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
async def validation_health_check(
    agent: ValidationAgent = Depends(get_validation_agent),
):
    """Perform health check on validation agent"""
    try:
        is_healthy = await agent.health_check()
        return {
            "healthy": is_healthy,
            "agent_id": agent.agent_id,
            "pattern": "LSS API",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "healthy": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }