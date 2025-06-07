from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional
import asyncio
import json
import time
import logging
from datetime import datetime

from agents.context_agent.context_agent import ContextAgent

router = APIRouter(prefix="/context", tags=["context-agent"])
logger = logging.getLogger("context_routes")

def safe_json_serialize(obj):
    """Safely serialize objects to JSON, handling non-serializable types"""
    try:
        return json.dumps(obj)
    except TypeError as e:
        logger.warning(f"JSON serialization failed: {e}")
        # Fallback: convert complex objects to strings
        if isinstance(obj, dict):
            safe_obj = {}
            for key, value in obj.items():
                try:
                    json.dumps(value)  # Test if value is serializable
                    safe_obj[key] = value
                except TypeError:
                    safe_obj[key] = str(value)  # Convert to string if not serializable
            return json.dumps(safe_obj)
        else:
            return json.dumps(str(obj))

def get_context_agent(request: Request) -> ContextAgent:
    """Get ContextAgent from app state (LSS API)"""
    if not hasattr(request.app.state, 'context_agent'):
        raise HTTPException(status_code=503, detail="ContextAgent not available")
    return request.app.state.context_agent

class ContextRequest(BaseModel):
    code: str
    top_k: int = 5

class ContextSearchRequest(BaseModel):
    code: str
    top_k: Optional[int] = 5

# === MAIN ENDPOINTS ===

@router.post("/search")
async def search_context(
    request: ContextSearchRequest,
    agent: ContextAgent = Depends(get_context_agent),
):
    """Search for relevant context using the context agent"""
    try:
        result = await agent.query_context(
            code=request.code,
            top_k=request.top_k
        )
        
        return {
            "success": True,
            "context": result["context"],
            "metadata": {
                "elapsed_time": result["elapsed_time"],
                "correlation_id": result["correlation_id"],
                "chunk_count": len(result["context"]),
                "session_info": result.get("session_info", {}),
                "timestamp": datetime.now().isoformat()
            }
        }
    except Exception as e:
        logger.error(f"Context search error: {e}")
        raise HTTPException(status_code=500, detail=f"Context search error: {e}")

@router.post("/search/stream")
async def search_context_stream(
    request: ContextSearchRequest,
    agent: ContextAgent = Depends(get_context_agent),
):
    """Stream context search results"""
    async def event_generator():
        async for event in agent.query_context_stream(
            code=request.code,
            top_k=request.top_k
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

@router.post("/query")
async def query_context(
    request: ContextRequest,
    agent: ContextAgent = Depends(get_context_agent),
):
    """Legacy endpoint - maintains old interface"""
    try:
        result = await agent.query_context(request.code, request.top_k)
        
        # Clean the result to remove non-serializable objects
        clean_result = {
            'context': result.get('context', []),
            'elapsed_time': result.get('elapsed_time', 0),
            'correlation_id': result.get('correlation_id', '')
        }
        
        return clean_result
    except Exception as e:
        logger.error(f"Context query error: {e}")
        raise HTTPException(status_code=500, detail=f"Context query error: {e}")

@router.post("/query/stream")
async def query_context_stream(
    request: ContextRequest,
    agent: ContextAgent = Depends(get_context_agent),
):
    """Legacy streaming endpoint - maintains old interface"""
    async def event_generator():
        start_time = time.time()
        
        try:
            # 1. Emit start event
            start_event = {
                'event': 'start', 
                'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 
                'msg': 'Context search started'
            }
            yield f"data: {safe_json_serialize(start_event)}\n\n"
            await asyncio.sleep(0.1)
            
            # 2. Emit progress event
            progress_event = {
                'event': 'progress', 
                'progress': 0.5, 
                'msg': 'Searching knowledge base...', 
                'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            }
            yield f"data: {safe_json_serialize(progress_event)}\n\n"
            await asyncio.sleep(0.2)
            
            # 3. Actually query the context
            logger.info(f"Starting context query for: {request.code}")
            result = await agent.query_context(request.code, request.top_k)
            logger.info(f"Context query completed, found {len(result.get('context', []))} chunks")
            
            # Clean the result to remove non-serializable objects
            clean_result = {
                'context': result.get('context', []),
                'elapsed_time': result.get('elapsed_time', 0),
                'correlation_id': result.get('correlation_id', '')
            }
            
            # 4. Emit result event
            result_event = {
                'event': 'result', 
                **clean_result, 
                'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 
                'processing_time': round(time.time() - start_time, 2)
            }
            yield f"data: {safe_json_serialize(result_event)}\n\n"
            
        except Exception as e:
            logger.error(f"Context streaming error: {e}")
            
            # Safely serialize the error message
            error_msg = str(e)
            if len(error_msg) > 500:
                error_msg = error_msg[:500] + "..."
            
            error_event = {
                'event': 'error', 
                'msg': f'Context search failed: {error_msg}', 
                'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            }
            yield f"data: {safe_json_serialize(error_event)}\n\n"
    
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
async def get_context_status(
    agent: ContextAgent = Depends(get_context_agent),
):
    """Get context agent status"""
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
async def context_health_check(
    agent: ContextAgent = Depends(get_context_agent),
):
    """Perform health check on context agent"""
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