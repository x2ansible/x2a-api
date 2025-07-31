from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Dict, List
import asyncio
import json
import logging
from datetime import datetime

# Import your ValidationAgent class - adjust path as needed
# from agents.validate.validate_agent import ValidationAgent
# from agents.validate.ansible_lint_validator import AnsibleLintValidator

router = APIRouter(prefix="/validate", tags=["validation"])
logger = logging.getLogger("validation_routes")


def get_validation_agent(request: Request):
    """Get ValidationAgent from app state (supports both ValidationAgent and LangGraphValidationAgent)"""
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


# === MAIN ENDPOINTS WITH TIMEOUT HANDLING ===

@router.post("/playbook")
async def validate_playbook(
    request: ValidateRequest,
    agent = Depends(get_validation_agent),
):
    """Validate an Ansible playbook using custom ansible-lint tool with timeout handling"""
    try:
        max_size = 50000  # 50KB limit
        if len(request.playbook_content) > max_size:
            raise HTTPException(
                status_code=413,
                detail=f"Playbook too large ({len(request.playbook_content)} chars). Maximum size: {max_size} characters"
            )
        
        # Check if agent supports get_supported_profiles method
        supported_profiles = ["basic", "production"]  # default
        if hasattr(agent, 'get_supported_profiles'):
            supported_profiles = agent.get_supported_profiles()
        
        if request.profile not in supported_profiles:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported profile: {request.profile}. Supported: {supported_profiles}"
            )
        
        try:
            result = await asyncio.wait_for(
                agent.validate_playbook(
                    playbook_content=request.playbook_content,
                    profile=request.profile
                ),
                timeout=120  # 2 minute timeout
            )
        except asyncio.TimeoutError:
            logger.error(f"Validation request timed out for profile: {request.profile}")
            raise HTTPException(
                status_code=408,
                detail=f"Validation request timed out after 2 minutes. Try with a smaller playbook or 'basic' profile."
            )

        # Handle timeout flag in result
        if result.get("timeout"):
            raise HTTPException(
                status_code=408,
                detail=result.get("formatted_issues", "Validation timed out")
            )

        return {
            "success": True,
            "validation_result": result,
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "profile": request.profile,
                "playbook_length": len(request.playbook_content),
                "issues_found": result.get("issues_count", 0),
                "passed": result.get("passed", False),
                "pattern": "Registry-based",
                "agent_id": result.get("agent_id", "unknown"),
                "elapsed_time": result.get("elapsed_time", 0),
                "timeout": result.get("timeout", False)
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Playbook validation error: {e}")
        raise HTTPException(status_code=500, detail=f"Playbook validation error: {e}")

@router.post("/playbook/stream")
async def validate_playbook_stream(
    request: ValidateRequest,
    agent = Depends(get_validation_agent),
):
    """Stream playbook validation results with timeout handling (event-stream)"""
    max_size = 50000
    if len(request.playbook_content) > max_size:
        def size_error_generator():
            yield f"data: {json.dumps({'type': 'error', 'error': f'Playbook too large ({len(request.playbook_content)} chars). Maximum: {max_size} characters'})}\n\n"
        return StreamingResponse(
            size_error_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )
    
    # Check supported profiles
    supported_profiles = ["basic", "production"]  # default
    if hasattr(agent, 'get_supported_profiles'):
        supported_profiles = agent.get_supported_profiles()
    
    if request.profile not in supported_profiles:
        def profile_error_generator():
            yield f"data: {json.dumps({'type': 'error', 'error': f'Unsupported profile: {request.profile}'})}\n\n"
        return StreamingResponse(
            profile_error_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    # Check if agent has streaming support
    if not hasattr(agent, 'validate_playbook_stream'):
        def no_stream_error_generator():
            yield f"data: {json.dumps({'type': 'error', 'error': 'Agent does not support streaming'})}\n\n"
        return StreamingResponse(
            no_stream_error_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    # Pass the sync generator directly
    return StreamingResponse(
        agent.validate_playbook_stream(
            playbook_content=request.playbook_content,
            profile=request.profile,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )

@router.post("/multiple")
async def validate_multiple_playbooks(
    request: ValidateMultipleRequest,
    agent = Depends(get_validation_agent),
):
    try:
        if not request.files:
            raise HTTPException(status_code=400, detail="No files provided")
        total_size = sum(len(content) for content in request.files.values())
        max_total_size = 100000
        if total_size > max_total_size:
            raise HTTPException(
                status_code=413,
                detail=f"Total files too large ({total_size} chars). Maximum total size: {max_total_size} characters"
            )
        
        # Check supported profiles
        supported_profiles = ["basic", "production"]  # default
        if hasattr(agent, 'get_supported_profiles'):
            supported_profiles = agent.get_supported_profiles()
        
        if request.profile not in supported_profiles:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported profile: {request.profile}. Supported: {supported_profiles}"
            )
        
        try:
            results = await asyncio.wait_for(
                agent.validate_multiple_files(
                    files=request.files,
                    profile=request.profile
                ),
                timeout=300  # 5 minutes
            )
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=408,
                detail="Multiple file validation timed out after 5 minutes"
            )
        
        total_files = len(results)
        passed_files = sum(1 for r in results.values() if r.get("passed", False))
        total_issues = sum(r.get("issues_count", 0) for r in results.values())
        
        return {
            "success": True,
            "results": results,
            "summary": {
                "total_files": total_files,
                "passed_files": passed_files,
                "failed_files": total_files - passed_files,
                "total_issues": total_issues,
                "profile": request.profile,
                "pattern": "Registry-based"
            },
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "profile": request.profile,
                "agent_pattern": "Registry-based",
                "total_size": total_size
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Multiple file validation error: {e}")
        raise HTTPException(status_code=500, detail=f"Multiple file validation error: {e}")

@router.post("/syntax")
async def validate_syntax(
    request: ValidateSyntaxRequest,
    agent = Depends(get_validation_agent),
):
    try:
        max_size = 25000
        if len(request.playbook_content) > max_size:
            raise HTTPException(
                status_code=413,
                detail=f"Playbook too large for syntax check ({len(request.playbook_content)} chars). Maximum: {max_size} characters"
            )
        try:
            result = await asyncio.wait_for(
                agent.validate_syntax(playbook_content=request.playbook_content),
                timeout=60
            )
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=408,
                detail="Syntax validation timed out after 1 minute"
            )
        return {
            "success": True,
            "syntax_valid": result.get("passed", False),
            "issues": result.get("issues", []),
            "formatted_issues": result.get("formatted_issues", result.get("summary", "")),
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "validation_type": "syntax_check",
                "issues_count": result.get("issues_count", 0),
                "pattern": "Registry-based",
                "agent_id": result.get("agent_id", "unknown"),
                "elapsed_time": result.get("elapsed_time", 0),
                "timeout": result.get("timeout", False)
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Syntax validation error: {e}")
        raise HTTPException(status_code=500, detail=f"Syntax validation error: {e}")

@router.post("/production")
async def production_validate(
    request: ValidateRequest,
    agent = Depends(get_validation_agent),
):
    try:
        max_size = 30000
        if len(request.playbook_content) > max_size:
            raise HTTPException(
                status_code=413,
                detail=f"Playbook too large for production validation ({len(request.playbook_content)} chars). Maximum: {max_size} characters"
            )
        try:
            result = await asyncio.wait_for(
                agent.production_validate(playbook_content=request.playbook_content),
                timeout=180
            )
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=408,
                detail="Production validation timed out after 3 minutes. Try with a smaller playbook."
            )
        return {
            "success": True,
            "production_ready": result.get("passed", False),
            "validation_result": result,
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "profile": "production",
                "playbook_length": len(request.playbook_content),
                "issues_found": result.get("issues_count", 0),
                "pattern": "Registry-based",
                "agent_id": result.get("agent_id", "unknown"),
                "elapsed_time": result.get("elapsed_time", 0),
                "timeout": result.get("timeout", False)
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Production validation error: {e}")
        raise HTTPException(status_code=500, detail=f"Production validation error: {e}")

# === STATUS AND HEALTH ENDPOINTS ===

@router.get("/status")
async def get_validation_status(
    agent = Depends(get_validation_agent),
):
    try:
        # Get supported profiles safely
        supported_profiles = ["basic", "production"]  # default
        if hasattr(agent, 'get_supported_profiles'):
            supported_profiles = agent.get_supported_profiles()
        
        # Get agent status safely
        agent_info = {"status": "ready", "type": "ValidationAgent"}
        if hasattr(agent, 'get_status'):
            agent_info = agent.get_status()
        
        return {
            "status": "ready",
            "agent_info": agent_info,
            "supported_profiles": supported_profiles,
            "limits": {
                "max_playbook_size": 50000,
                "max_syntax_size": 25000,
                "max_production_size": 30000,
                "max_multiple_total_size": 100000,
                "timeout_playbook": 120,
                "timeout_syntax": 60,
                "timeout_production": 180,
                "timeout_multiple": 300,
                "timeout_streaming": 150
            },
            "timestamp": datetime.now().isoformat(),
            "pattern": "Registry-based with timeout handling"
        }
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Status check failed: {e}")

@router.post("/health")
async def validation_health_check(
    agent = Depends(get_validation_agent),
):
    try:
        is_healthy = False
        if hasattr(agent, 'health_check'):
            is_healthy = await asyncio.wait_for(
                agent.health_check(),
                timeout=30
            )
        else:
            # Basic health check - try to get status
            try:
                if hasattr(agent, 'get_status'):
                    agent.get_status()
                    is_healthy = True
            except Exception:
                is_healthy = False
        
        return {
            "healthy": is_healthy,
            "agent_id": getattr(agent, 'agent_id', 'unknown'),
            "pattern": "Registry-based with timeout handling",
            "tool": "ansible_lint_tool",
            "timestamp": datetime.now().isoformat(),
            "session_id": getattr(agent, 'session_id', 'unknown')
        }
    except asyncio.TimeoutError:
        return {
            "healthy": False,
            "error": "Health check timed out after 30 seconds",
            "pattern": "Registry-based",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "healthy": False,
            "error": str(e),
            "pattern": "Registry-based",
            "timestamp": datetime.now().isoformat()
        }

@router.get("/profiles")
async def get_supported_profiles(
    agent = Depends(get_validation_agent),
):
    # Get supported profiles safely
    supported_profiles = ["basic", "production"]  # default
    if hasattr(agent, 'get_supported_profiles'):
        supported_profiles = agent.get_supported_profiles()
    
    return {
        "profiles": supported_profiles,
        "descriptions": {
            "basic": "Basic syntax and structure validation",
            "production": "Strict production-ready validation"
        },
        "default": "basic",
        "recommended_profiles": {
            "development": "basic",
            "production": "production"
        },
        "timeout_info": {
            "basic": "~30-60 seconds",
            "production": "~90-180 seconds"
        },
        "timestamp": datetime.now().isoformat(),
        "pattern": "Registry-based",
        "tool": "ansible_lint_tool"
    }

@router.get("/agent-info")
async def get_agent_info(
    agent = Depends(get_validation_agent),
):
    try:
        # Get agent status safely
        status_info = {"status": "ready", "type": "ValidationAgent"}
        if hasattr(agent, 'get_status'):
            status_info = agent.get_status()
        
        # Get supported profiles safely
        supported_profiles = ["basic", "production"]  # default
        if hasattr(agent, 'get_supported_profiles'):
            supported_profiles = agent.get_supported_profiles()
        
        return {
            "agent_details": status_info,
            "capabilities": {
                "validation_profiles": supported_profiles,
                "streaming_support": hasattr(agent, 'validate_playbook_stream'),
                "multiple_file_support": hasattr(agent, 'validate_multiple_files'),
                "health_check_support": hasattr(agent, 'health_check'),
                "timeout_handling": True,
                "size_limits": True
            },
            "configuration": {
                "tool": "ansible_lint_tool",
                "pattern": "Registry-based",
                "architecture": "Custom tool with agentic pattern"
            },
            "limits": {
                "max_playbook_size": 50000,
                "max_syntax_size": 25000,
                "max_production_size": 30000,
                "max_multiple_total_size": 100000
            },
            "timeouts": {
                "playbook_validation": 120,
                "syntax_check": 60,
                "production_validation": 180,
                "multiple_files": 300,
                "streaming": 150,
                "health_check": 30
            },
            "endpoints": {
                "validate_playbook": "/api/validate/playbook",
                "syntax_check": "/api/validate/syntax",
                "production_validate": "/api/validate/production",
                "multiple_files": "/api/validate/multiple",
                "streaming": "/api/validate/playbook/stream"
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Agent info retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=f"Agent info retrieval failed: {e}")

@router.post("/test")
async def test_validation(
    agent = Depends(get_validation_agent),
):
    test_playbook = """---
- name: Test playbook
  hosts: localhost
  tasks:
    - name: Echo message
      debug:
        msg: "This is a test playbook"
    - name: Create directory
      file:
        path: /tmp/test
        state: directory
        mode: '0755'
"""
    try:
        result = await asyncio.wait_for(
            agent.validate_playbook(
                playbook_content=test_playbook,
                profile="basic"
            ),
            timeout=60
        )
        return {
            "success": True,
            "test_result": result,
            "test_playbook": test_playbook,
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "test_type": "sample_validation",
                "pattern": "Registry-based with timeout handling",
                "elapsed_time": result.get("elapsed_time", 0),
                "timeout": result.get("timeout", False)
            }
        }
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=408,
            detail="Test validation timed out after 1 minute"
        )
    except Exception as e:
        logger.error(f"Test validation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Test validation failed: {e}")

@router.get("/limits")
async def get_validation_limits():
    return {
        "size_limits": {
            "max_playbook_size": 50000,
            "max_syntax_size": 25000,
            "max_production_size": 30000,
            "max_multiple_total_size": 100000,
            "description": "Limits in characters"
        },
        "timeout_limits": {
            "playbook_validation": 120,
            "syntax_check": 60,
            "production_validation": 180,
            "multiple_files": 300,
            "streaming": 150,
            "health_check": 30,
            "description": "Timeouts in seconds"
        },
        "recommendations": {
            "for_large_playbooks": "Use 'basic' profile for faster validation",
            "for_production": "Keep playbooks under 30KB for production validation",
            "for_multiple_files": "Limit total size to 100KB across all files",
            "for_streaming": "Use streaming for real-time feedback on long validations"
        },
        "timestamp": datetime.now().isoformat()
    }