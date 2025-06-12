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
    """Get ValidationAgent from app state (Registry pattern)"""
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

# === DEBUG ENDPOINTS ===

@router.get("/debug/tools")
async def debug_tools_endpoint(
    agent: ValidationAgent = Depends(get_validation_agent),
):
    """Debug endpoint to check MCP tool availability"""
    try:
        debug_info = await agent.debug_tools()
        return {
            "success": True,
            "debug_info": debug_info,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Tool debug failed: {e}")
        raise HTTPException(status_code=500, detail=f"Tool debug failed: {e}")

@router.post("/debug/test-tool")
async def test_tool_availability(
    agent: ValidationAgent = Depends(get_validation_agent),
):
    """Test if the MCP ansible_lint tool is working"""
    try:
        test_result = await agent.test_tool_availability()
        return {
            "success": True,
            "test_result": test_result,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Tool test failed: {e}")
        raise HTTPException(status_code=500, detail=f"Tool test failed: {e}")

# === MAIN ENDPOINTS WITH TIMEOUT HANDLING ===

@router.post("/playbook")
async def validate_playbook(
    request: ValidateRequest,
    agent: ValidationAgent = Depends(get_validation_agent),
):
    """Validate an Ansible playbook using MCP ansible_lint tool with timeout handling"""
    try:
        # Validate playbook size
        max_size = 50000  # 50KB limit
        if len(request.playbook_content) > max_size:
            raise HTTPException(
                status_code=413,
                detail=f"Playbook too large ({len(request.playbook_content)} chars). Maximum size: {max_size} characters"
            )
        
        # Validate profile
        if request.profile not in agent.get_supported_profiles():
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported profile: {request.profile}. Supported: {agent.get_supported_profiles()}"
            )
        
        # Add timeout wrapper to prevent worker timeouts
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
        
        # Handle timeout result from agent
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
                "agent_id": result.get("session_info", {}).get("agent_id", "unknown"),
                "elapsed_time": result.get("elapsed_time", 0)
            }
        }
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(f"Playbook validation error: {e}")
        raise HTTPException(status_code=500, detail=f"Playbook validation error: {e}")

@router.post("/playbook/stream")
async def validate_playbook_stream(
    request: ValidateRequest,
    agent: ValidationAgent = Depends(get_validation_agent),
):
    """Stream playbook validation results with timeout handling"""
    try:
        # Validate playbook size
        max_size = 50000  # 50KB limit
        if len(request.playbook_content) > max_size:
            async def size_error_generator():
                yield f"data: {json.dumps({'type': 'error', 'error': f'Playbook too large ({len(request.playbook_content)} chars). Maximum: {max_size} characters'})}\n\n"
            return StreamingResponse(
                size_error_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                },
            )
        
        # Validate profile
        if request.profile not in agent.get_supported_profiles():
            async def profile_error_generator():
                yield f"data: {json.dumps({'type': 'error', 'error': f'Unsupported profile: {request.profile}'})}\n\n"
            return StreamingResponse(
                profile_error_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                },
            )
    except Exception as e:
        # Return error as stream
        async def error_generator():
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
        return StreamingResponse(
            error_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    async def event_generator():
        try:
            # Use asyncio.wait_for correctly with the async generator
            timeout_seconds = 150  # 2.5 minutes
            start_time = asyncio.get_event_loop().time()
            
            async for event in agent.validate_playbook_stream(
                playbook_content=request.playbook_content,
                profile=request.profile
            ):
                # Check timeout manually since wait_for doesn't work well with async generators
                current_time = asyncio.get_event_loop().time()
                if current_time - start_time > timeout_seconds:
                    yield f"data: {json.dumps({'type': 'error', 'error': 'Streaming validation timed out after 2.5 minutes'})}\n\n"
                    break
                
                await asyncio.sleep(0.1)
                yield f"data: {json.dumps(event)}\n\n"
                
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

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
    """Validate multiple playbook files with timeout handling"""
    try:
        if not request.files:
            raise HTTPException(status_code=400, detail="No files provided")
        
        # Check total size of all files
        total_size = sum(len(content) for content in request.files.values())
        max_total_size = 100000  # 100KB total limit for multiple files
        if total_size > max_total_size:
            raise HTTPException(
                status_code=413,
                detail=f"Total files too large ({total_size} chars). Maximum total size: {max_total_size} characters"
            )
        
        # Validate profile
        if request.profile not in agent.get_supported_profiles():
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported profile: {request.profile}. Supported: {agent.get_supported_profiles()}"
            )
        
        # Add timeout for multiple file validation
        try:
            results = await asyncio.wait_for(
                agent.validate_multiple_files(
                    files=request.files,
                    profile=request.profile
                ),
                timeout=300  # 5 minute timeout for multiple files
            )
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=408,
                detail="Multiple file validation timed out after 5 minutes"
            )
        
        # Calculate summary statistics
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
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(f"Multiple file validation error: {e}")
        raise HTTPException(status_code=500, detail=f"Multiple file validation error: {e}")

@router.post("/syntax")
async def validate_syntax(
    request: ValidateSyntaxRequest,
    agent: ValidationAgent = Depends(get_validation_agent),
):
    """Quick syntax validation using basic profile with timeout handling"""
    try:
        # Validate playbook size
        max_size = 25000  # Smaller limit for syntax check
        if len(request.playbook_content) > max_size:
            raise HTTPException(
                status_code=413,
                detail=f"Playbook too large for syntax check ({len(request.playbook_content)} chars). Maximum: {max_size} characters"
            )
        
        # Add timeout for syntax validation
        try:
            result = await asyncio.wait_for(
                agent.validate_syntax(playbook_content=request.playbook_content),
                timeout=60  # 1 minute timeout for syntax check
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
            "formatted_issues": result.get("formatted_issues", ""),
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "validation_type": "syntax_check",
                "issues_count": result.get("issues_count", 0),
                "pattern": "Registry-based",
                "agent_id": result.get("session_info", {}).get("agent_id", "unknown"),
                "elapsed_time": result.get("elapsed_time", 0)
            }
        }
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(f"Syntax validation error: {e}")
        raise HTTPException(status_code=500, detail=f"Syntax validation error: {e}")

@router.post("/production")
async def production_validate(
    request: ValidateRequest,
    agent: ValidationAgent = Depends(get_validation_agent),
):
    """Production-ready validation with strict rules and timeout handling"""
    try:
        # Validate playbook size (stricter for production)
        max_size = 30000  # Smaller limit for production validation
        if len(request.playbook_content) > max_size:
            raise HTTPException(
                status_code=413,
                detail=f"Playbook too large for production validation ({len(request.playbook_content)} chars). Maximum: {max_size} characters"
            )
        
        # Add timeout for production validation
        try:
            result = await asyncio.wait_for(
                agent.production_validate(playbook_content=request.playbook_content),
                timeout=180  # 3 minute timeout for production validation
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
                "agent_id": result.get("session_info", {}).get("agent_id", "unknown"),
                "elapsed_time": result.get("elapsed_time", 0)
            }
        }
    except HTTPException:
        raise  # Re-raise HTTP exceptions
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
    agent: ValidationAgent = Depends(get_validation_agent),
):
    """Perform health check on validation agent with timeout"""
    try:
        # Add timeout to health check
        is_healthy = await asyncio.wait_for(
            agent.health_check(),
            timeout=30  # 30 second timeout for health check
        )
        return {
            "healthy": is_healthy,
            "agent_id": getattr(agent, 'agent_id', 'unknown'),
            "pattern": "Registry-based with timeout handling",
            "tool": "mcp::ansible_lint",
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
        "recommended_profiles": {
            "development": "basic",
            "testing": "moderate", 
            "staging": "safety",
            "production": "production"
        },
        "timeout_info": {
            "basic": "~30-60 seconds",
            "moderate": "~60-90 seconds",
            "safety": "~60-120 seconds", 
            "shared": "~60-90 seconds",
            "production": "~90-180 seconds"
        },
        "timestamp": datetime.now().isoformat(),
        "pattern": "Registry-based",
        "tool": "mcp::ansible_lint"
    }

# === ENHANCED ENDPOINTS ===

@router.get("/agent-info")
async def get_agent_info(
    agent: ValidationAgent = Depends(get_validation_agent),
):
    """Get detailed agent information"""
    try:
        status_info = agent.get_status()
        return {
            "agent_details": status_info,
            "capabilities": {
                "validation_profiles": agent.get_supported_profiles(),
                "streaming_support": True,
                "multiple_file_support": True,
                "health_check_support": True,
                "debug_tools": True,
                "timeout_handling": True,
                "size_limits": True
            },
            "configuration": {
                "tool": "mcp::ansible_lint",
                "pattern": "Registry-based",
                "architecture": "ContextAgent pattern with timeout handling"
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
                "streaming": "/api/validate/playbook/stream",
                "debug_tools": "/api/validate/debug/tools",
                "test_tool": "/api/validate/debug/test-tool"
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Agent info retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=f"Agent info retrieval failed: {e}")

@router.post("/test")
async def test_validation(
    agent: ValidationAgent = Depends(get_validation_agent),
):
    """Test endpoint with sample playbook and timeout handling"""
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
        # Add timeout to test endpoint
        result = await asyncio.wait_for(
            agent.validate_playbook(
                playbook_content=test_playbook,
                profile="basic"
            ),
            timeout=60  # 1 minute timeout for test
        )
        
        return {
            "success": True,
            "test_result": result,
            "test_playbook": test_playbook,
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "test_type": "sample_validation",
                "pattern": "Registry-based with timeout handling",
                "elapsed_time": result.get("elapsed_time", 0)
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

# === UTILITY ENDPOINTS ===

@router.get("/limits")
async def get_validation_limits():
    """Get current validation limits and timeouts"""
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