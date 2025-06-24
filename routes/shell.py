# ========== 1. routes/shell.py ==========
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel, Field
from typing import Dict, Optional
from datetime import datetime
from fastapi.responses import StreamingResponse
import asyncio
import json

from agents.shell_analysis.agent import ShellAnalysisAgent

router = APIRouter(prefix="/shell", tags=["shell-analysis"])

class ShellAnalyzeRequest(BaseModel):
    files: Dict[str, str] = Field(..., description="Dictionary of filename to file content")

class ShellAnalysisResponse(BaseModel):
    success: bool
    script_name: str
    script_type: str
    analysis_method: str
    version_requirements: Dict
    dependencies: Dict
    functionality: Dict
    recommendations: Dict
    session_info: Dict
    metadata: Optional[Dict] = None

# Dependency injection for ShellAnalysisAgent
def get_shell_agent(request: Request) -> ShellAnalysisAgent:
    if not hasattr(request.app.state, 'shell_analysis_agent'):
        raise HTTPException(status_code=503, detail="Shell analysis agent not available")
    return request.app.state.shell_analysis_agent

@router.post("/analyze", response_model=ShellAnalysisResponse)
async def analyze_shell_script(
    request: ShellAnalyzeRequest,
    agent: ShellAnalysisAgent = Depends(get_shell_agent),
):
    """
    Analyze shell scripts for infrastructure automation
    
    Supports analysis of:
    - Bash/Zsh deployment scripts
    - System configuration scripts
    - Installation and setup scripts
    - Monitoring and maintenance scripts
    - CI/CD automation scripts
    """
    script_name = f"shell_script_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shell_data = {
        "name": script_name,
        "files": request.files,
    }
    
    try:
        result = await agent.analyze_shell(shell_data=shell_data)
        
        result["session_info"] = {
            **result.get("session_info", {}),
            "script_name": script_name
        }
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Shell analysis error: {e}")

@router.post("/analyze/stream")
async def analyze_shell_stream(
    request: ShellAnalyzeRequest,
    agent: ShellAnalysisAgent = Depends(get_shell_agent),
):
    """
    Stream shell script analysis with real-time progress updates
    """
    script_name = f"stream_shell_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shell_data = {
        "name": script_name,
        "files": request.files,
    }
    
    async def event_generator():
        try:
            async for event in agent.analyze_shell_stream(shell_data=shell_data):
                if event.get("type") == "final_analysis" and "data" in event:
                    event["data"]["session_info"] = {
                        **event["data"].get("session_info", {}),
                        "script_name": script_name
                    }
                await asyncio.sleep(0.1)
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            error_event = {
                "type": "error",
                "error": str(e),
                "script_name": script_name
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
async def get_shell_status(request: Request):
    """Get status of the shell analysis agent"""
    status = {
        "timestamp": datetime.now().isoformat(),
        "agent_available": False,
        "agent_status": {}
    }
    
    if hasattr(request.app.state, 'shell_analysis_agent'):
        try:
            agent = request.app.state.shell_analysis_agent
            status["agent_available"] = True
            status["agent_status"] = agent.get_status()
            status["agent_status"]["health"] = await agent.health_check()
        except Exception as e:
            status["agent_status"] = {"error": str(e), "health": False}
    
    return status

@router.get("/capabilities")
async def get_shell_capabilities():
    """Get detailed information about shell script analysis capabilities"""
    return {
        "analysis_capabilities": {
            "script_detection": {
                "description": "Automatically detects shell script type and purpose",
                "outputs": ["script_type", "shell_version", "automation_type", "complexity"]
            },
            "dependency_analysis": {
                "description": "Analyzes external dependencies and requirements",
                "outputs": ["system_packages", "external_commands", "file_dependencies", "service_dependencies"]
            },
            "functionality_assessment": {
                "description": "Evaluates script functionality and operations",
                "outputs": ["primary_purpose", "key_operations", "managed_services", "configuration_files"]
            },
            "modernization_recommendations": {
                "description": "Provides Ansible conversion guidance",
                "outputs": ["conversion_action", "ansible_equivalent", "migration_effort", "best_practices"]
            }
        },
        "supported_script_types": [
            "DEPLOYMENT - Application and service deployment scripts",
            "CONFIGURATION - System configuration and setup scripts", 
            "MONITORING - Health checks and monitoring scripts",
            "MAINTENANCE - Backup, cleanup, and maintenance scripts",
            "INSTALLATION - Software installation and package management"
        ],
        "supported_shells": [
            "bash - Bourne Again Shell scripts",
            "zsh - Z Shell scripts", 
            "sh - POSIX shell scripts",
            "dash - Debian Almquist shell scripts"
        ],
        "supported_file_types": [
            "*.sh - Shell script files",
            "*.bash - Bash script files",
            "*.zsh - Zsh script files", 
            "*install* - Installation scripts",
            "*deploy* - Deployment scripts",
            "*setup* - Setup and configuration scripts"
        ]
    }

@router.get("/health")
async def health_check(request: Request):
    """Health check for shell analysis service"""
    try:
        if not hasattr(request.app.state, 'shell_analysis_agent'):
            return {"status": "unhealthy", "reason": "Agent not initialized"}
        
        agent = request.app.state.shell_analysis_agent
        health_ok = await agent.health_check()
        
        return {
            "status": "healthy" if health_ok else "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "agent_id": agent.agent_id,
            "service": "Shell Script Analysis"
        }
    except Exception as e:
        return {
            "status": "unhealthy", 
            "reason": str(e),
            "timestamp": datetime.now().isoformat(),
            "service": "Shell Script Analysis"
        }
