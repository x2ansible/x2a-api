from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Dict, List
import asyncio
import json
import logging
from datetime import datetime

from agents.validate.validate_agent import ValidationAgent

router = APIRouter(prefix="/validate", tags=["validation"])
logger = logging.getLogger("validation_routes")

def get_validation_agent(request: Request) -> ValidationAgent:
    """Get ValidationAgent from app state (LSS API)"""
    if not hasattr(request.app.state, 'validation_agent'):
        raise HTTPException(status_code=503, detail="ValidationAgent not available")
    return request.app.state.validation_agent

class ValidateRequest(BaseModel):
    playbook_content: str
    profile: Optional[str] = "basic"

class ValidateMultipleRequest(BaseModel):
    files: Dict[str, str]  # filename -> content
    profile: Optional[str] = "basic"

class ValidateSyntaxRequest(BaseModel):
    playbook_content: str

# === MAIN ENDPOINTS ===

@router.post("/playbook")
async def validate_playbook(
    request: ValidateRequest,
    agent: ValidationAgent = Depends(get_validation_agent),
):
    """Validate an Ansible playbook using MCP ansible_lint tool"""
    try:
        # Validate profile
        if request.profile not in agent.get_supported_profiles():
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported profile: {request.profile}. Supported: {agent.get_supported_profiles()}"
            )
        
        result = await agent.validate_playbook(
            playbook_content=request.playbook_content,
            profile=request.profile
        )
        
        return {
            "success": True,
            "validation_result": result,
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "profile": request.profile,
                "playbook_length": len(request.playbook_content),
                "issues_found": result.get("issues_count", 0),
                "passed": result.get("summary", {}).get("passed", False)
            }
        }
    except Exception as e:
        logger.error(f"Playbook validation error: {e}")
        raise HTTPException(status_code=500, detail=f"Playbook validation error: {e}")

@router.post("/playbook/stream")
async def validate_playbook_stream(
    request: ValidateRequest,
    agent: ValidationAgent = Depends(get_validation_agent),
):
    """Stream playbook validation results"""
    async def event_generator():
        async for event in agent.validate_playbook_stream(
            playbook_content=request.playbook_content,  # Fixed: use playbook_content
            profile=request.profile
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

@router.post("/multiple")
async def validate_multiple_playbooks(
    request: ValidateMultipleRequest,
    agent: ValidationAgent = Depends(get_validation_agent),
):
    """Validate multiple playbook files"""
    try:
        if not request.files:
            raise HTTPException(status_code=400, detail="No files provided")
        
        # Validate profile
        if request.profile not in agent.get_supported_profiles():
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported profile: {request.profile}. Supported: {agent.get_supported_profiles()}"
            )
        
        results = await agent.validate_multiple_files(
            files=request.files,
            profile=request.profile
        )
        
        # Calculate summary statistics
        total_files = len(results)
        passed_files = sum(1 for r in results.values() if r.get("summary", {}).get("passed", False))
        total_issues = sum(r.get("issues_count", 0) for r in results.values())
        
        return {
            "success": True,
            "results": results,
            "summary": {
                "total_files": total_files,
                "passed_files": passed_files,
                "failed_files": total_files - passed_files,
                "total_issues": total_issues,
                "profile": request.profile
            },
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "profile": request.profile
            }
        }
    except Exception as e:
        logger.error(f"Multiple file validation error: {e}")
        raise HTTPException(status_code=500, detail=f"Multiple file validation error: {e}")

@router.post("/syntax")
async def validate_syntax(
    request: ValidateSyntaxRequest,
    agent: ValidationAgent = Depends(get_validation_agent),
):
    """Quick syntax validation using basic profile"""
    try:
        result = await agent.validate_syntax(
            playbook_content=request.playbook_content
        )
        
        return {
            "success": True,
            "syntax_valid": result.get("summary", {}).get("passed", False),
            "issues": result.get("issues", []),
            "formatted_issues": result.get("formatted_issues", ""),
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "validation_type": "syntax_check",
                "issues_count": result.get("issues_count", 0)
            }
        }
    except Exception as e:
        logger.error(f"Syntax validation error: {e}")
        raise HTTPException(status_code=500, detail=f"Syntax validation error: {e}")

@router.post("/production")
async def production_validate(
    request: ValidateRequest,
    agent: ValidationAgent = Depends(get_validation_agent),
):
    """Production-ready validation with strict rules"""
    try:
        result = await agent.production_validate(
            playbook_content=request.playbook_content
        )
        
        return {
            "success": True,
            "production_ready": result.get("summary", {}).get("passed", False),
            "validation_result": result,
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "profile": "production",
                "playbook_length": len(request.playbook_content),
                "issues_found": result.get("issues_count", 0)
            }
        }
    except Exception as e:
        logger.error(f"Production validation error: {e}")
        raise HTTPException(status_code=500, detail=f"Production validation error: {e}")

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
            "supported_profiles": agent.get_supported_profiles(),
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
            "agent_id": getattr(agent, 'agent_id', 'unknown'),
            "pattern": "Registry-based",
            "tool": "mcp::ansible_lint",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "healthy": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@router.get("/profiles")
async def get_supported_profiles(
    agent: ValidationAgent = Depends(get_validation_agent),
):
    """Get list of supported validation profiles"""
    return {
        "profiles": agent.get_supported_profiles(),
        "descriptions": {
            "basic": "Basic syntax and structure validation",
            "moderate": "Standard best practices checking", 
            "safety": "Security-focused validation rules",
            "shared": "Rules for shared/reusable playbooks",
            "production": "Strict production-ready validation"
        },
        "default": "basic",
        "timestamp": datetime.now().isoformat()
    }