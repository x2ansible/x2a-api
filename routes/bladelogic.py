from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel, Field
from typing import Dict, Optional
from datetime import datetime
from fastapi.responses import StreamingResponse
import asyncio
import json

from agents.bladelogic_analysis.agent import BladeLogicAnalysisAgent

router = APIRouter(prefix="/bladelogic", tags=["bladelogic-analysis"])

class BladeLogicAnalyzeRequest(BaseModel):
    files: Dict[str, str] = Field(..., description="Dictionary of filename to file content")

class BladeLogicAnalysisResponse(BaseModel):
    success: bool
    object_name: str
    object_type: str
    analysis_method: str
    version_requirements: Dict
    dependencies: Dict
    functionality: Dict
    recommendations: Dict
    session_info: Dict
    metadata: Optional[Dict] = None

# Dependency injection for BladeLogicAnalysisAgent
def get_bladelogic_agent(request: Request) -> BladeLogicAnalysisAgent:
    if not hasattr(request.app.state, 'bladelogic_analysis_agent'):
        raise HTTPException(status_code=503, detail="BladeLogic analysis agent not available")
    return request.app.state.bladelogic_analysis_agent

@router.post("/analyze", response_model=BladeLogicAnalysisResponse)
async def analyze_bladelogic_automation(
    request: BladeLogicAnalyzeRequest,
    agent: BladeLogicAnalysisAgent = Depends(get_bladelogic_agent),
):
    """
    Analyze BladeLogic automation content (Jobs, Packages, Policies, Scripts)
    
    Supports analysis of:
    - RSCD Agent deployment scripts
    - Compliance templates (HIPAA, SOX, PCI-DSS)
    - Patch management workflows
    - NSH scripts and BlPackages
    - Job flows and automation templates
    """
    object_name = f"bladelogic_object_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    bladelogic_data = {
        "name": object_name,
        "files": request.files,
    }
    
    try:
        result = await agent.analyze_bladelogic(bladelogic_data=bladelogic_data)
        
        result["session_info"] = {
            **result.get("session_info", {}),
            "object_name": object_name
        }
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"BladeLogic analysis error: {e}")

@router.post("/analyze/stream")
async def analyze_bladelogic_stream(
    request: BladeLogicAnalyzeRequest,
    agent: BladeLogicAnalysisAgent = Depends(get_bladelogic_agent),
):
    """
    Stream BladeLogic automation analysis with real-time progress updates
    
    **Event Types:**
    - `progress`: Analysis progress updates
    - `final_analysis`: Complete analysis result
    - `error`: Error information
    """
    object_name = f"stream_bladelogic_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    bladelogic_data = {
        "name": object_name,
        "files": request.files,
    }
    
    async def event_generator():
        try:
            async for event in agent.analyze_bladelogic_stream(bladelogic_data=bladelogic_data):
                if event.get("type") == "final_analysis" and "data" in event:
                    event["data"]["session_info"] = {
                        **event["data"].get("session_info", {}),
                        "object_name": object_name
                    }
                await asyncio.sleep(0.1)
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            error_event = {
                "type": "error",
                "error": str(e),
                "object_name": object_name
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
async def get_bladelogic_status(request: Request):
    """Get status of the BladeLogic analysis agent"""
    status = {
        "timestamp": datetime.now().isoformat(),
        "agent_available": False,
        "agent_status": {}
    }
    
    # Check agent availability and status
    if hasattr(request.app.state, 'bladelogic_analysis_agent'):
        try:
            agent = request.app.state.bladelogic_analysis_agent
            status["agent_available"] = True
            status["agent_status"] = agent.get_status()
            status["agent_status"]["health"] = await agent.health_check()
        except Exception as e:
            status["agent_status"] = {"error": str(e), "health": False}
    
    return status

@router.get("/capabilities")
async def get_bladelogic_capabilities():
    """Get detailed information about BladeLogic analysis capabilities"""
    return {
        "analysis_capabilities": {
            "version_requirements": {
                "description": "Determines minimum BladeLogic and NSH version requirements",
                "outputs": ["min_bladelogic_version", "min_nsh_version", "migration_effort", "estimated_hours", "deprecated_features"]
            },
            "dependency_analysis": {
                "description": "Maps BladeLogic dependencies and composite automation patterns",
                "outputs": ["is_composite", "composite_jobs", "package_dependencies", "policy_dependencies", "external_scripts", "circular_risk"]
            },
            "functionality_assessment": {
                "description": "Analyzes automation type and enterprise functionality",
                "outputs": ["primary_purpose", "automation_type", "target_platforms", "managed_services", "managed_packages", "managed_files", "compliance_policies", "reusability"]
            },
            "strategic_recommendations": {
                "description": "Provides modernization and Ansible conversion guidance",
                "outputs": ["consolidation_action", "rationale", "migration_priority", "risk_factors", "ansible_equivalent"]
            }
        },
        "supported_automation_types": [
            "COMPLIANCE - HIPAA, SOX, PCI-DSS compliance scanning and enforcement",
            "PATCHING - Patch management workflows and security updates", 
            "DEPLOYMENT - Application and software deployment automation",
            "CONFIGURATION - System configuration and infrastructure management",
            "MONITORING - Health checks and performance monitoring"
        ],
        "supported_object_types": [
            "JOB - BladeLogic automation jobs and workflows",
            "PACKAGE - BlPackages for software deployment",
            "POLICY - Compliance policies and security templates", 
            "SCRIPT - NSH scripts and shell automation",
            "COMPLIANCE_TEMPLATE - YAML compliance templates"
        ],
        "supported_file_types": [
            "*.nsh - NSH (Network Shell) scripts",
            "*.sh - Shell scripts with BladeLogic commands",
            "*.yaml, *.yml - Compliance templates",
            "*.txt - Job definitions and workflows",
            "*job*.* - Job configuration files",
            "*patch*.* - Patch management scripts",
            "*compliance*.* - Compliance scanning templates"
        ],
        "enterprise_features": {
            "multi_platform_support": ["Windows", "Linux", "AIX", "Solaris", "HPUX"],
            "compliance_frameworks": ["HIPAA", "SOX", "PCI-DSS", "CIS", "STIG"],
            "automation_workflows": ["RSCD agent deployment", "Patch catalog analysis", "Security hardening", "Application deployment"],
            "modernization_guidance": "Expert recommendations for Ansible conversion and cloud migration"
        },
        "analysis_method": {
            "type": "expert_bladelogic_analysis",
            "description": "Enterprise-grade BladeLogic automation analysis with pattern recognition",
            "benefits": ["Expert BladeLogic knowledge", "Enterprise context awareness", "Ansible migration guidance", "Risk assessment"]
        },
        "output_formats": ["JSON", "Streaming JSON"],
        "session_management": "Dedicated sessions per analysis for enterprise scalability"
    }

@router.get("/automation-types")
async def get_automation_types():
    """Get detailed information about supported BladeLogic automation types"""
    return {
        "automation_types": {
            "COMPLIANCE": {
                "description": "Security compliance scanning and policy enforcement",
                "examples": ["HIPAA compliance templates", "SOX audit automation", "PCI-DSS scanning", "CIS benchmark verification"],
                "typical_components": ["Compliance policies", "Audit scripts", "Remediation workflows", "Compliance reporting"],
                "migration_complexity": "HIGH",
                "ansible_equivalent": "ansible-hardening + custom compliance modules + SCAP content"
            },
            "PATCHING": {
                "description": "Patch management and security update automation",
                "examples": ["Security patch deployment", "Patch catalog analysis", "Vulnerability remediation", "Staged patch rollouts"],
                "typical_components": ["Patch catalogs", "Deployment scripts", "Reboot coordination", "Rollback procedures"],
                "migration_complexity": "MEDIUM",
                "ansible_equivalent": "ansible.posix.patch + yum/apt modules + reboot management"
            },
            "DEPLOYMENT": {
                "description": "Application and software deployment automation",
                "examples": ["Application deployment", "Software installation", "BlPackage distribution", "Configuration management"],
                "typical_components": ["BlPackages", "Installation scripts", "Configuration templates", "Validation checks"],
                "migration_complexity": "MEDIUM",
                "ansible_equivalent": "ansible.builtin package modules + application deployment playbooks"
            },
            "CONFIGURATION": {
                "description": "System configuration and infrastructure management",
                "examples": ["Service configuration", "File management", "Registry updates", "Environment setup"],
                "typical_components": ["Configuration templates", "Service management", "File operations", "Registry modifications"],
                "migration_complexity": "LOW",
                "ansible_equivalent": "ansible.builtin template + file modules + service management"
            },
            "MONITORING": {
                "description": "Health monitoring and performance tracking automation",
                "examples": ["Health checks", "Performance monitoring", "Alert generation", "Log management"],
                "typical_components": ["Monitoring scripts", "Alert configurations", "Performance counters", "Log analysis"],
                "migration_complexity": "MEDIUM",
                "ansible_equivalent": "ansible monitoring roles + notification modules"
            }
        },
        "migration_guidance": {
            "assessment_criteria": [
                "Automation complexity and dependencies",
                "Enterprise compliance requirements", 
                "Multi-platform support needs",
                "Integration with existing infrastructure",
                "Business criticality and risk tolerance"
            ],
            "modernization_benefits": [
                "Cloud-native automation with Ansible",
                "Infrastructure as Code principles",
                "Version control and GitOps workflows",
                "Container and Kubernetes integration",
                "Modern CI/CD pipeline integration"
            ]
        }
    }

# Health check endpoint
@router.get("/health")
async def health_check(request: Request):
    """Health check for BladeLogic analysis service"""
    try:
        if not hasattr(request.app.state, 'bladelogic_analysis_agent'):
            return {"status": "unhealthy", "reason": "Agent not initialized"}
        
        agent = request.app.state.bladelogic_analysis_agent
        health_ok = await agent.health_check()
        
        return {
            "status": "healthy" if health_ok else "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "agent_id": agent.agent_id,
            "service": "BladeLogic Automation Analysis"
        }
    except Exception as e:
        return {
            "status": "unhealthy", 
            "reason": str(e),
            "timestamp": datetime.now().isoformat(),
            "service": "BladeLogic Automation Analysis"
        }