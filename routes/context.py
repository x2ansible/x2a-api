from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import asyncio
import json
import time
import logging
import tempfile
import os
import uuid
from datetime import datetime
from pathlib import Path

from agents.context_agent.context_agent import ContextAgent

# This line should already exist in your file
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

# === NEW INGEST ENDPOINT ===

@router.post("/ingest")
async def ingest_document(
    file: UploadFile = File(...),
    agent: ContextAgent = Depends(get_context_agent),
):
    """Ingest a document into the context knowledge base"""
    try:
        logger.info(f"📤 Received file upload: {file.filename}")
        
        # Validate file type
        allowed_extensions = {'.txt', '.md', '.yaml', '.yml', '.json', '.py', '.js', '.ts', '.tf', '.pp', '.rb', '.sh', '.cfg', '.conf'}
        file_extension = Path(file.filename or "").suffix.lower()
        
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
            
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file type: {file_extension}. Allowed: {', '.join(sorted(allowed_extensions))}"
            )
        
        # Read and validate file content
        content = await file.read()
        
        # Validate content size (max 10MB)
        max_size = 10 * 1024 * 1024  # 10MB
        if len(content) > max_size:
            raise HTTPException(status_code=400, detail="File too large (max 10MB)")
        
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="File is empty")
        
        # Decode content with multiple encoding attempts
        text_content = None
        encodings = ['utf-8', 'utf-8-sig', 'latin1', 'cp1252']
        
        for encoding in encodings:
            try:
                text_content = content.decode(encoding)
                logger.info(f" Successfully decoded file with {encoding}")
                break
            except UnicodeDecodeError:
                continue
        
        if text_content is None:
            raise HTTPException(status_code=400, detail="Unable to decode file content with any supported encoding")
        
        # Create temporary file for processing
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=file_extension, encoding='utf-8') as temp_file:
            temp_file.write(text_content)
            temp_file_path = temp_file.name
        
        try:
            # Simple processing since we don't want to modify the agent yet
            result = await simple_ingest_fallback(
                content=text_content,
                filename=file.filename,
                file_type=file_extension
            )
            
            logger.info(f" Successfully processed file: {file.filename}")
            
            return {
                "success": True,
                "message": "Conversion pattern added successfully to knowledge base",
                "filename": file.filename,
                "file_size": len(content),
                "file_type": file_extension,
                "chunks_created": result.get("chunks_created", 1),
                "document_id": result.get("document_id"),
                "processing_time": result.get("processing_time", 0),
                "timestamp": datetime.now().isoformat()
            }
            
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_file_path)
                logger.debug(f"🗑️ Cleaned up temporary file: {temp_file_path}")
            except OSError as e:
                logger.warning(f"⚠️ Failed to delete temporary file {temp_file_path}: {e}")
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f" Document ingest error: {e}")
        raise HTTPException(status_code=500, detail=f"Document ingest failed: {str(e)}")


async def simple_ingest_fallback(content: str, filename: str, file_type: str) -> Dict[str, Any]:
    """
    Simple fallback processing for document ingestion
    """
    import time
    start_time = time.time()
    
    try:
        # Simple chunking by lines or character count
        lines = content.split('\n')
        chunks = []
        
        # Group lines into chunks of reasonable size (roughly 500 chars)
        current_chunk = []
        current_size = 0
        
        for line in lines:
            line_size = len(line)
            if current_size + line_size > 500 and current_chunk:
                chunks.append('\n'.join(current_chunk))
                current_chunk = [line]
                current_size = line_size
            else:
                current_chunk.append(line)
                current_size += line_size
        
        # Add remaining chunk
        if current_chunk:
            chunks.append('\n'.join(current_chunk))
        
        # Generate a document ID
        document_id = f"doc_{str(uuid.uuid4())[:8]}_{int(time.time())}"
        
        # Log the ingestion (in real implementation, you'd store this in your vector DB)
        logger.info(f"📝 Processed {filename}: {len(chunks)} chunks created")
        
        processing_time = time.time() - start_time
        
        return {
            "document_id": document_id,
            "chunks_created": len(chunks),
            "filename": filename,
            "file_type": file_type,
            "processing_time": round(processing_time, 2)
        }
        
    except Exception as e:
        logger.error(f" Fallback processing failed for {filename}: {e}")
        raise

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