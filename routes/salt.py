"""
Salt Analysis Routes
Clean routes for Salt infrastructure analysis
"""

import uuid
import logging
from typing import Dict, Any
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()

class SaltAnalysisRequest(BaseModel):
    name: str = Field(..., description="Salt object name")
    files: Dict[str, str] = Field(..., description="Salt files content")

class SaltAnalysisResponse(BaseModel):
    success: bool
    correlation_id: str
    data: Dict[str, Any]
    message: str

@router.post("/salt/analyze", response_model=SaltAnalysisResponse)
async def analyze_salt(request: SaltAnalysisRequest, app_request: Request):
    """Analyze Salt infrastructure automation"""
    correlation_id = str(uuid.uuid4())[:8]
    logger.info(f"[{correlation_id}] 🧂 Salt analysis request: {request.name}")
    
    try:
        if not hasattr(app_request.app.state, 'salt_analysis_agent'):
            raise HTTPException(status_code=500, detail="Salt analysis agent not available")
        
        salt_agent = app_request.app.state.salt_analysis_agent
        
        salt_data = {
            "name": request.name,
            "files": request.files
        }
        
        result = await salt_agent.analyze_salt(salt_data, correlation_id)
        
        if not result.get("success"):
            raise HTTPException(status_code=400, detail="Salt analysis failed")
        
        logger.info(f"[{correlation_id}]  Salt analysis completed successfully")
        
        return SaltAnalysisResponse(
            success=True,
            correlation_id=correlation_id,
            data=result,
            message="Salt analysis completed successfully"
        )
        
    except Exception as e:
        logger.error(f"[{correlation_id}]  Salt analysis failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Salt analysis failed: {str(e)}")

@router.post("/salt/analyze/stream")
async def analyze_salt_stream(request: SaltAnalysisRequest, app_request: Request):
    """Stream Salt analysis with progress updates"""
    correlation_id = str(uuid.uuid4())[:8]
    logger.info(f"[{correlation_id}] 🧂 Salt streaming analysis request: {request.name}")
    
    try:
        if not hasattr(app_request.app.state, 'salt_analysis_agent'):
            raise HTTPException(status_code=500, detail="Salt analysis agent not available")
        
        salt_agent = app_request.app.state.salt_analysis_agent
        
        salt_data = {
            "name": request.name,
            "files": request.files
        }
        
        async def generate():
            async for chunk in salt_agent.analyze_salt_stream(salt_data, correlation_id):
                import json
                yield f"data: {json.dumps(chunk)}\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Correlation-ID": correlation_id
            }
        )
        
    except Exception as e:
        logger.error(f"[{correlation_id}]  Salt streaming analysis failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Salt streaming analysis failed: {str(e)}")

@router.get("/salt/status")
async def get_salt_status(app_request: Request):
    """Get Salt agent status"""
    try:
        if not hasattr(app_request.app.state, 'salt_analysis_agent'):
            return {"status": "not_available", "message": "Salt analysis agent not configured"}
        
        salt_agent = app_request.app.state.salt_analysis_agent
        status = salt_agent.get_status()
        
        return {
            "status": "available",
            "agent_status": status
        }
        
    except Exception as e:
        logger.error(f" Failed to get Salt agent status: {str(e)}")
        return {"status": "error", "message": str(e)}

@router.get("/salt/health")
async def salt_health_check(app_request: Request):
    """Health check for Salt agent"""
    try:
        if not hasattr(app_request.app.state, 'salt_analysis_agent'):
            return {"healthy": False, "message": "Salt analysis agent not configured"}
        
        salt_agent = app_request.app.state.salt_analysis_agent
        is_healthy = await salt_agent.health_check()
        
        return {
            "healthy": is_healthy,
            "message": "Salt agent healthy" if is_healthy else "Salt agent unhealthy"
        }
        
    except Exception as e:
        logger.error(f" Salt health check failed: {str(e)}")
        return {"healthy": False, "message": str(e)}