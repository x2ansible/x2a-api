# routes/ansible_upgrade.py

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Dict, Optional
from datetime import datetime
import asyncio
import json
import uuid

from agents.ansible_upgrade.agent import AnsibleUpgradeAnalysisAgent
from utils.streaming import stream_agent_events  # <--- USE THE UTIL

router = APIRouter(prefix="/ansible-upgrade", tags=["ansible-upgrade-analysis"])

class AnsibleUpgradeRequest(BaseModel):
    content: str = Field(..., description="Ansible content to analyze")
    filename: Optional[str] = Field("playbook.yml", description="Original filename")

def get_ansible_upgrade_agent(request: Request) -> AnsibleUpgradeAnalysisAgent:
    if not hasattr(request.app.state, 'ansible_upgrade_agent'):
        raise HTTPException(status_code=503, detail="Ansible upgrade analysis agent not available")
    return request.app.state.ansible_upgrade_agent

@router.post("/analyze")
async def analyze_ansible_content(
    request: AnsibleUpgradeRequest,
    agent: AnsibleUpgradeAnalysisAgent = Depends(get_ansible_upgrade_agent),
):
    """Analyze Ansible content for upgrade assessment (ReAct pattern)"""
    correlation_id = f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    ansible_data = {
        "content": request.content,
        "filename": request.filename
    }
    try:
        result = await agent.analyze_ansible_upgrade(
            ansible_data=ansible_data,
            correlation_id=correlation_id
        )
        return result
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "filename": request.filename,
            "correlation_id": correlation_id
        }

@router.post("/analyze/stream")
async def analyze_ansible_stream(
    request: AnsibleUpgradeRequest,
    agent: AnsibleUpgradeAnalysisAgent = Depends(get_ansible_upgrade_agent),
):
    """
    Stream Ansible analysis with real-time progress updates
    Event Types: progress, final_analysis, error
    """
    correlation_id = f"stream_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    ansible_data = {
        "content": request.content,
        "filename": request.filename
    }
    session_info = {"correlation_id": correlation_id}

    return StreamingResponse(
        stream_agent_events(agent, "analyze_stream", ansible_data, session_info),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )

@router.get("/status")
async def get_upgrade_status(request: Request):
    """Get status of the Ansible upgrade analysis agent"""
    if hasattr(request.app.state, 'ansible_upgrade_agent'):
        try:
            agent = request.app.state.ansible_upgrade_agent
            return {
                "agent_available": True,
                "agent_status": agent.get_status(),
                "health": await agent.health_check(),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {"agent_available": False, "error": str(e)}
    return {"agent_available": False, "error": "Agent not initialized"}

@router.get("/health")
async def health_check(request: Request):
    """Health check for Ansible upgrade analysis service"""
    try:
        if not hasattr(request.app.state, 'ansible_upgrade_agent'):
            return {"status": "unhealthy", "reason": "Agent not initialized"}
        agent = request.app.state.ansible_upgrade_agent
        health_ok = await agent.health_check()
        return {
            "status": "healthy" if health_ok else "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "service": "Ansible Upgrade Analysis ReAct"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "reason": str(e),
            "timestamp": datetime.now().isoformat()
        }
