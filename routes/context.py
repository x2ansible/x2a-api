from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Dict, Any
import asyncio
import json
import time
import logging

from agents.context_agent.context_agent import create_context_agent, ContextAgent
from config.config import ConfigLoader

router = APIRouter(prefix="/context", tags=["context-agent"])
config_loader = ConfigLoader("config.yaml")
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

def get_context_agent() -> ContextAgent:
    return create_context_agent(config_loader)

class ContextRequest(BaseModel):
    code: str
    top_k: int = 5

@router.post("/query")
async def query_context(
    request: ContextRequest,
    agent: ContextAgent = Depends(get_context_agent),
):
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
    async def event_generator():
        start_time = time.time()
        
        try:
            # 1. Emit start event
            start_event = {'event': 'start', 'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'msg': 'Context search started'}
            yield f"data: {safe_json_serialize(start_event)}\n\n"
            await asyncio.sleep(0.1)
            
            # 2. Emit progress event
            progress_event = {'event': 'progress', 'progress': 0.5, 'msg': 'Searching knowledge base...', 'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
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
            result_event = {'event': 'result', **clean_result, 'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'processing_time': round(time.time() - start_time, 2)}
            yield f"data: {safe_json_serialize(result_event)}\n\n"
            
        except Exception as e:
            logger.error(f"Context streaming error: {e}")
            logger.exception("Full context streaming error:")
            
            # Safely serialize the error message without any complex objects
            error_msg = str(e)
            if len(error_msg) > 500:  # Truncate very long error messages
                error_msg = error_msg[:500] + "..."
            
            # Emit error event with safe string serialization
            error_event = {'event': 'error', 'msg': f'Context search failed: {error_msg}', 'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
            try:
                yield f"data: {safe_json_serialize(error_event)}\n\n"
            except Exception as json_error:
                # Last resort: emit a basic error message
                logger.error(f"Failed to serialize error response: {json_error}")
                basic_error = {'event': 'error', 'msg': 'Context search failed: Internal error', 'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
                yield f"data: {json.dumps(basic_error)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )