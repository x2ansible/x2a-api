from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import logging
from datetime import datetime

from agents.context_agent.context_agent import ContextAgent

# This line should already exist in your file
router = APIRouter(prefix="/context", tags=["context-agent"])
logger = logging.getLogger("context_routes")

def get_context_agent(request: Request) -> ContextAgent:
    """Get ContextAgent from app state (LSS API)"""
    if not hasattr(request.app.state, 'context_agent'):
        raise HTTPException(status_code=503, detail="ContextAgent not available")
    return request.app.state.context_agent

class ContextSearchRequest(BaseModel):
    code: str
    top_k: Optional[int] = 5

class QuestionRequest(BaseModel):
    question: str

class ContextRequest(BaseModel):
    code: str
    top_k: int = 5
    vector_db_id: Optional[str] = None  # UI might send this

# === NEW CONVERSATIONAL ENDPOINTS (AGENTIC RAG PATTERN) ===

@router.post("/ask")
async def ask_question(
    request: QuestionRequest,
    agent: ContextAgent = Depends(get_context_agent),
):
    """Ask a question to the RAG agent - conversational interface"""
    try:
        result = await agent.ask_question(request.question)
        return result
        
    except Exception as e:
        logger.error(f"Question processing error: {e}")
        raise HTTPException(status_code=500, detail=f"Question processing failed: {e}")

@router.post("/ask/stream")
async def ask_question_stream(
    request: QuestionRequest,
    agent: ContextAgent = Depends(get_context_agent),
):
    """Ask a question to the RAG agent with streaming response"""
    try:
        return StreamingResponse(
            agent.ask_question_stream(request.question),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )
    except Exception as e:
        logger.error(f"Streaming question error: {e}")
        raise HTTPException(status_code=500, detail=f"Streaming failed: {e}")

# === EXISTING ENDPOINTS (keep all your existing code below) ===

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



@router.post("/query/stream")
async def query_context_stream(
    request: ContextRequest,
    agent: ContextAgent = Depends(get_context_agent),
):
    """UI-compatible streaming endpoint using agentic RAG pattern"""
    import asyncio
    import json
    
    async def event_generator():
        try:
            # 1. Emit start event (UI expects this format)
            start_event = {
                'event': 'start', 
                'timestamp': datetime.now().isoformat(), 
                'msg': 'Context search started'
            }
            yield f"data: {json.dumps(start_event)}\n\n"
            await asyncio.sleep(0.1)
            
            # 2. Emit progress event (UI expects this format)
            progress_event = {
                'event': 'progress', 
                'progress': 0.5, 
                'msg': 'Searching knowledge base...', 
                'timestamp': datetime.now().isoformat()
            }
            yield f"data: {json.dumps(progress_event)}\n\n"
            await asyncio.sleep(0.2)
            
            # 3. Use new agentic approach to get results
            result = await agent.query_context(request.code, request.top_k)
            
            # 4. Emit result event (UI expects this format)
            result_event = {
                'event': 'result', 
                'context': result.get('context', []),
                'elapsed_time': result.get('elapsed_time', 0),
                'correlation_id': result.get('correlation_id', ''),
                'timestamp': datetime.now().isoformat()
            }
            yield f"data: {json.dumps(result_event)}\n\n"
            
        except Exception as e:
            # Error event (UI expects this format)
            error_event = {
                'event': 'error', 
                'msg': f'Context search failed: {str(e)}', 
                'timestamp': datetime.now().isoformat()
            }
            yield f"data: {json.dumps(error_event)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )

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