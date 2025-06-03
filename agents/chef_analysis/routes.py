"""
FastAPI routes for Chef Analysis Agent.
Provides REST API endpoints with streaming support and admin agent info.
"""

import logging
import json
import asyncio
import os
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field, validator

import httpx

from config.config_loader import ConfigLoader
from agents.chef_analysis.agent import create_chef_analysis_agent, ChefAnalysisAgent
from agents.chef_analysis.utils import create_correlation_id
from shared.exceptions import (
    ChefAnalysisBaseException,
    InvalidInputError,
    LLMServiceError,
    TimeoutError
)

logger = logging.getLogger(__name__)

# --- Pydantic Models ---
class CookbookFile(BaseModel):
    filename: str = Field(..., description="Name of the cookbook file")
    content: str = Field(..., description="File content")

class CookbookAnalysisRequest(BaseModel):
    cookbook_name: str = Field(..., description="Name of the cookbook", max_length=100)
    files: Dict[str, str] = Field(
        ..., 
        description="Dictionary of filename to file content",
        min_items=1
    )

    @validator('files')
    def validate_files(cls, v):
        for filename, content in v.items():
            if not content or not content.strip():
                raise ValueError(f"File content cannot be empty for {filename}")
        return v

    @validator('cookbook_name')
    def validate_cookbook_name(cls, v):
        if not v or not v.strip():
            raise ValueError("Cookbook name cannot be empty")
        return v.strip()

# --- Router Setup ---
router = APIRouter(prefix="/chef", tags=["chef-analysis"])

def get_config_loader() -> ConfigLoader:
    return ConfigLoader()

def get_chef_agent(config_loader: ConfigLoader = Depends(get_config_loader)) -> ChefAnalysisAgent:
    return create_chef_analysis_agent(config_loader)

# --- Endpoints ---
@router.post(
    "/analyze",
    summary="Analyze Chef Cookbook",
    description="Analyze a Chef cookbook for version requirements, dependencies, and reuse recommendations"
)
async def analyze_cookbook(
    request: CookbookAnalysisRequest,
    agent: ChefAnalysisAgent = Depends(get_chef_agent)
):
    correlation_id = create_correlation_id()
    logger.info(f"Received cookbook analysis request [{correlation_id}]: {request.cookbook_name}")
    try:
        cookbook_data = {"name": request.cookbook_name, "files": request.files}
        analysis_result = await agent.analyze_cookbook(cookbook_data, correlation_id)
        analysis_result["success"] = True
        analysis_result["cookbook_name"] = request.cookbook_name
        # Optionally add agent version if available
        analysis_result.setdefault("metadata", {})
        analysis_result["metadata"]["agent_version"] = getattr(agent, "agent_version", "1.0.0")
        return analysis_result
    except ChefAnalysisBaseException as e:
        logger.error(f"Chef analysis error [{correlation_id}]: {e.message}")
        error_response = e.to_dict()
        error_response["correlation_id"] = correlation_id
        raise HTTPException(status_code=e.http_status, detail=error_response)
    except Exception as e:
        logger.error(f"Unexpected error [{correlation_id}]: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Internal server error occurred",
                    "correlation_id": correlation_id
                }
            }
        )

@router.post(
    "/analyze/stream",
    summary="Stream Chef Cookbook Analysis",
    description="Analyze a Chef cookbook with real-time progress updates via Server-Sent Events"
)
async def analyze_cookbook_stream(
    request: CookbookAnalysisRequest,
    agent: ChefAnalysisAgent = Depends(get_chef_agent)
) -> StreamingResponse:
    correlation_id = create_correlation_id()
    logger.info(f"Received streaming cookbook analysis request [{correlation_id}]: {request.cookbook_name}")

    async def event_generator():
        saw_final = False
        try:
            cookbook_data = {"name": request.cookbook_name, "files": request.files}
            async for event in agent.analyze_cookbook_stream(cookbook_data, correlation_id):
                # If event already has a "type", stream it as-is
                if isinstance(event, dict) and event.get("type"):
                    yield f"data: {json.dumps(event)}\n\n"
                    if event.get("type") == "final_analysis":
                        saw_final = True
                else:
                    # Assume this is a "bare" final analysis, wrap it
                    yield f"data: {json.dumps({'type': 'final_analysis', 'data': event, 'correlation_id': correlation_id})}\n\n"
                    saw_final = True
                await asyncio.sleep(0.1)
            # If we never saw a final_analysis, but the agent returned a dict, wrap it
            if not saw_final:
                yield f"data: {json.dumps({'type': 'complete', 'correlation_id': correlation_id})}\n\n"
        except ChefAnalysisBaseException as e:
            logger.error(f"Streaming analysis error [{correlation_id}]: {e.message}")
            error_event = {
                "type": "error",
                "error": e.to_dict(),
                "correlation_id": correlation_id
            }
            yield f"data: {json.dumps(error_event)}\n\n"
        except Exception as e:
            logger.error(f"Unexpected streaming error [{correlation_id}]: {str(e)}")
            error_event = {
                "type": "error",
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Internal server error occurred"
                },
                "correlation_id": correlation_id
            }
            yield f"data: {json.dumps(error_event)}\n\n"
        # Always send a completion event
        yield f"data: {json.dumps({'type': 'complete', 'correlation_id': correlation_id})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Correlation-ID": correlation_id
        }
    )

@router.get(
    "/health",
    summary="Health Check",
    description="Check the health status of the Chef Analysis Agent"
)
async def health_check(
    agent: ChefAnalysisAgent = Depends(get_chef_agent)
) -> Dict[str, Any]:
    try:
        health_status = {
            "status": "healthy",
            "agent": "chef_analysis",
            "version": getattr(agent, "agent_version", "1.0.0"),
            "configuration": {
                "base_url": agent.base_url,
                "model": agent.model,
                "timeout": agent.timeout,
                "max_tokens": agent.max_tokens
            }
        }
        logger.debug("Health check passed")
        return health_status
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "error": str(e)
            }
        )

@router.get(
    "/config",
    summary="Get Agent Configuration",
    description="Get current agent configuration (non-sensitive information only)"
)
async def get_agent_config(
    agent: ChefAnalysisAgent = Depends(get_chef_agent)
) -> Dict[str, Any]:
    try:
        config_info = {
            "agent_name": "chef_analysis",
            "model": agent.model,
            "timeout_seconds": agent.timeout,
            "max_tokens": agent.max_tokens,
            "base_url_configured": bool(agent.base_url),
            "instructions_loaded": bool(agent.instructions),
            "version": getattr(agent, "agent_version", "1.0.0")
        }
        return config_info
    except Exception as e:
        logger.error(f"Failed to get agent config: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Failed to retrieve agent configuration",
                "message": str(e)
            }
        )

# --- Admin Endpoint: List LlamaStack Agents/Version ---
LLAMASTACK_URL = os.getenv("LLAMASTACK_URL", "http://llamastack:8321")

@router.get(
    "/agents/info",
    summary="LlamaStack Agent List & Version",
    description="Fetch LlamaStack agent list and version info (admin endpoint)"
)
async def get_llamastack_agents_info():
    try:
        async with httpx.AsyncClient() as client:
            # List all agents
            resp = await client.get(f"{LLAMASTACK_URL}/v1/agents")
            if resp.status_code != 200:
                raise HTTPException(status_code=502, detail="Failed to fetch LlamaStack agents")
            agents = resp.json()
            # Try to get version if available
            version = None
            try:
                vresp = await client.get(f"{LLAMASTACK_URL}/v1/version")
                if vresp.status_code == 200:
                    version = vresp.json()
            except Exception:
                version = None
        return {
            "llamastack_agents": agents,
            "llamastack_version": version,
        }
    except Exception as e:
        logger.error(f"Failed to proxy llamastack agent info: {str(e)}")
        raise HTTPException(status_code=500, detail=f"LlamaStack proxy error: {str(e)}")

