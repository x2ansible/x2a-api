# routes/analysis.py - Updated for unified ReAct agent approach

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import json
import asyncio
import logging
from datetime import datetime


from app.agent_registry import UnifiedAgentRegistry, AgentRegistryError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Analysis"])

# ==== Request Models ====
class ExecuteRequest(BaseModel):
    agent_name: str
    query: str
    metadata: Optional[Dict[str, Any]] = None

class UnifiedAnalysisRequest(BaseModel):
    files: Dict[str, str]
    technology_type: Optional[str] = None  # chef, salt, bladelogic, shell, etc.
    module_name: Optional[str] = None  # for Salt modules
    metadata: Optional[Dict[str, Any]] = None

class AnsibleUpgradeRequest(BaseModel):
    content: str
    metadata: Optional[Dict[str, Any]] = None

class ContextRequest(BaseModel):
    query: str
    metadata: Optional[Dict[str, Any]] = None

class GenerateRequest(BaseModel):
    description: str
    context: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class ValidateRequest(BaseModel):
    playbook_content: str
    profile: Optional[str] = "production"
    metadata: Optional[Dict[str, Any]] = None

# ==== Dependency ====
def get_agent_registry(request: Request) -> UnifiedAgentRegistry:
    """Get agent registry with proper error handling"""
    if not hasattr(request.app.state, 'agent_registry') or not request.app.state.agent_registry:
        raise HTTPException(
            status_code=503, 
            detail="Agent registry not available - application may still be starting up"
        )
    return request.app.state.agent_registry

# ==== Core Analysis Endpoints ====

@router.post("/execute")
async def execute_agent(
    request: ExecuteRequest,
    registry: UnifiedAgentRegistry = Depends(get_agent_registry)
):
    """Execute a query against any configured agent"""
    try:
        if not request.query or not request.query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty")
        
        if not request.agent_name or not request.agent_name.strip():
            raise HTTPException(status_code=400, detail="Agent name cannot be empty")
        
        logger.info(f"🔍 Executing query for agent '{request.agent_name}'")
        
        result = registry.execute_query(
            agent_name=request.agent_name,
            query=request.query.strip(),
            **(request.metadata or {})
        )
        
        logger.info(f" Query executed successfully for agent '{request.agent_name}'")
        return result
        
    except AgentRegistryError as e:
        logger.error(f" Agent registry error: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f" Execute error for agent '{request.agent_name}': {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Execution failed: {str(e)}")

@router.post("/analyze")
async def unified_analysis(
    request: UnifiedAnalysisRequest,
    registry: UnifiedAgentRegistry = Depends(get_agent_registry)
):
    """Unified analysis endpoint using the ReAct agent for all IaC technologies"""
    try:
        if not request.files:
            raise HTTPException(status_code=400, detail="No files provided for analysis")
        
        # Build file content for analysis
        files_content = []
        total_size = 0
        file_paths = []
        
        for filename, content in request.files.items():
            if not content.strip():
                logger.warning(f"Empty file content for {filename}")
                continue
            
            # Detect technology type if not specified
            tech_type = request.technology_type or _detect_technology_type(filename, content)
            
            files_content.append(f"File: {filename}\nTechnology: {tech_type}\nContent:\n{content}")
            file_paths.append(filename)
            total_size += len(content)
        
        if not files_content:
            raise HTTPException(status_code=400, detail="All provided files are empty")
        
        # Build query for the unified ReAct agent (simplified for natural reasoning)
        query = f"""Please analyze these Infrastructure as Code files:

Technology Type: {request.technology_type or 'auto-detected'}
Module Name: {request.module_name or 'N/A'}
Files: {file_paths}

Files content:
{chr(10).join(files_content)}

Please provide a comprehensive analysis covering:
- What does this automation accomplish?
- What resources does it manage (packages, services, files)?
- What are the dependencies and complexity factors?
- How could this be modernized or migrated to Ansible?
- What are the key configuration patterns and logic?

Use your expertise to thoroughly analyze this Infrastructure as Code."""
        
        logger.info(f"🔧 Running unified analysis on {len(request.files)} files ({total_size} bytes)")
        
        result = registry.execute_query(
            agent_name="iac_phased_analysis_agent",
            query=query,
            files_analyzed=list(request.files.keys()),
            file_count=len(request.files),
            technology_type=request.technology_type,
            module_name=request.module_name,
            total_code_size=total_size,
            analysis_type="unified_iac_analysis"
        )
        
        logger.info(f" Unified analysis completed successfully")
        return result
        
    except AgentRegistryError as e:
        logger.error(f" Unified analysis agent error: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f" Unified analysis error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Unified analysis failed: {str(e)}")

# Legacy endpoints for backward compatibility
@router.post("/chef/analyze")
async def analyze_chef(
    request: UnifiedAnalysisRequest,
    registry: UnifiedAgentRegistry = Depends(get_agent_registry)
):
    """Chef analysis (redirects to unified analysis)"""
    request.technology_type = "chef"
    return await unified_analysis(request, registry)

@router.post("/salt/analyze")
async def analyze_salt(
    request: UnifiedAnalysisRequest,
    registry: UnifiedAgentRegistry = Depends(get_agent_registry)
):
    """Salt analysis (redirects to unified analysis)"""
    request.technology_type = "salt"
    return await unified_analysis(request, registry)

@router.post("/bladelogic/analyze")
async def analyze_bladelogic(
    request: UnifiedAnalysisRequest,
    registry: UnifiedAgentRegistry = Depends(get_agent_registry)
):
    """BladeLogic analysis (redirects to unified analysis)"""
    request.technology_type = "bladelogic"
    return await unified_analysis(request, registry)

@router.post("/shell/analyze")
async def analyze_shell(
    request: UnifiedAnalysisRequest,
    registry: UnifiedAgentRegistry = Depends(get_agent_registry)
):
    """Shell script analysis (redirects to unified analysis)"""
    request.technology_type = "shell"
    return await unified_analysis(request, registry)

@router.post("/ansible/upgrade")
async def analyze_ansible_upgrade(
    request: AnsibleUpgradeRequest,
    registry: UnifiedAgentRegistry = Depends(get_agent_registry)
):
    """Analyze Ansible content for upgrade requirements"""
    try:
        if not request.content or not request.content.strip():
            raise HTTPException(status_code=400, detail="Ansible content cannot be empty")
        
        query = f"Analyze this Ansible content for upgrade requirements:\n\n```yaml\n{request.content}\n```"
        
        logger.info(f"🔧 Analyzing Ansible content for upgrade ({len(request.content)} bytes)")
        
        result = registry.execute_query(
            agent_name="ansible_upgrade_analysis",
            query=query,
            content_length=len(request.content),
            analysis_type="ansible_upgrade",
            **(request.metadata or {})
        )
        
        logger.info(f" Ansible upgrade analysis completed successfully")
        return result
        
    except AgentRegistryError as e:
        logger.error(f" Ansible upgrade analysis agent error: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f" Ansible upgrade analysis error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ansible upgrade analysis failed: {str(e)}")

@router.post("/context")
async def search_context(
    request: ContextRequest,
    registry: UnifiedAgentRegistry = Depends(get_agent_registry)
):
    """Search context using RAG agent"""
    try:
        if not request.query or not request.query.strip():
            raise HTTPException(status_code=400, detail="Search query cannot be empty")
        
        logger.info(f"🔍 Searching context with query: {request.query[:100]}...")
        
        result = registry.execute_query(
            agent_name="context",
            query=request.query.strip(),
            search_type="context_retrieval",
            **(request.metadata or {})
        )
        
        logger.info(f" Context search completed successfully")
        return result
        
    except AgentRegistryError as e:
        logger.error(f" Context search agent error: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f" Context search error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Context search failed: {str(e)}")

@router.post("/generate")
async def generate_code(
    request: GenerateRequest,
    registry: UnifiedAgentRegistry = Depends(get_agent_registry)
):
    """Generate Ansible code"""
    try:
        if not request.description or not request.description.strip():
            raise HTTPException(status_code=400, detail="Description cannot be empty")
        
        # Build query with optional context
        query = f"Generate Ansible playbook for: {request.description.strip()}"
        if request.context and request.context.strip():
            query += f"\n\nAdditional context:\n{request.context.strip()}"
        
        logger.info(f"⚡ Generating code for: {request.description[:100]}...")
        
        result = registry.execute_query(
            agent_name="generate",
            query=query,
            generation_type="ansible_playbook",
            description_length=len(request.description),
            has_context=bool(request.context and request.context.strip()),
            **(request.metadata or {})
        )
        
        logger.info(f" Code generation completed successfully")
        return result
        
    except AgentRegistryError as e:
        logger.error(f" Code generation agent error: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f" Code generation error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Code generation failed: {str(e)}")

@router.post("/validate")
async def validate_playbook(
    request: ValidateRequest,
    registry: UnifiedAgentRegistry = Depends(get_agent_registry)
):
    """Validate Ansible playbook"""
    try:
        if not request.playbook_content or not request.playbook_content.strip():
            raise HTTPException(status_code=400, detail="Playbook content cannot be empty")
        
        query = f"Validate this Ansible playbook (profile: {request.profile}):\n\n```yaml\n{request.playbook_content}\n```"
        
        logger.info(f" Validating playbook ({len(request.playbook_content)} bytes, profile: {request.profile})")
        
        result = registry.execute_query(
            agent_name="validate",
            query=query,
            validation_profile=request.profile,
            content_length=len(request.playbook_content),
            validation_type="ansible_lint",
            **(request.metadata or {})
        )
        
        logger.info(f" Playbook validation completed successfully")
        return result
        
    except AgentRegistryError as e:
        logger.error(f" Playbook validation agent error: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f" Playbook validation error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Playbook validation failed: {str(e)}")

# ==== Utility Functions ====

def _detect_technology_type(filename: str, content: str) -> str:
    """Auto-detect technology type from filename and content"""
    filename_lower = filename.lower()
    content_lower = content.lower()
    
    # Chef detection
    if (filename_lower.endswith('.rb') or 
        'cookbook' in content_lower or 
        'recipe' in content_lower or
        'chef-client' in content_lower):
        return "chef"
    
    # Salt detection
    if (filename_lower.endswith('.sls') or
        'salt://' in content_lower or
        'pillar' in content_lower or
        'state.apply' in content_lower):
        return "salt"
    
    # Ansible detection
    if (filename_lower.endswith(('.yml', '.yaml')) and
        ('hosts:' in content_lower or 
         'tasks:' in content_lower or
         'ansible' in content_lower)):
        return "ansible"
    
    # Shell script detection
    if (filename_lower.endswith(('.sh', '.bash', '.zsh')) or
        content.startswith(('#!/bin/bash', '#!/bin/sh', '#!/usr/bin/env bash'))):
        return "shell"
    
    # Terraform detection
    if filename_lower.endswith('.tf'):
        return "terraform"
    
    # Puppet detection
    if filename_lower.endswith('.pp'):
        return "puppet"
    
    # BladeLogic detection (harder to detect, use heuristics)
    if ('bladelogic' in content_lower or 
        'rscd' in content_lower or
        'nsh' in content_lower):
        return "bladelogic"
    
    # Default fallback
    return "unknown"

# ==== Streaming Analysis Endpoint ====
@router.post("/analyze/stream")
async def unified_analysis_stream(
    request: UnifiedAnalysisRequest,
    registry: UnifiedAgentRegistry = Depends(get_agent_registry)
):
    """Stream unified analysis with real-time progress updates"""
    
    async def event_generator():
        try:
            # Validate request
            if not request.files:
                error_event = {
                    "type": "error",
                    "error": "No files provided for analysis",
                    "timestamp": datetime.utcnow().isoformat()
                }
                yield f"data: {json.dumps(error_event)}\n\n"
                return
            
            # Start event
            yield f"data: {json.dumps({'type': 'start', 'message': 'Starting unified IaC analysis...', 'timestamp': datetime.utcnow().isoformat()})}\n\n"
            await asyncio.sleep(0.1)
            
            # Progress event
            yield f"data: {json.dumps({'type': 'progress', 'message': f'Analyzing {len(request.files)} files with ReAct agent...', 'timestamp': datetime.utcnow().isoformat()})}\n\n"
            await asyncio.sleep(0.1)
            
            # Build file content
            files_content = []
            total_size = 0
            file_paths = []
            
            for filename, content in request.files.items():
                if content.strip():
                    tech_type = request.technology_type or _detect_technology_type(filename, content)
                    files_content.append(f"File: {filename}\nTechnology: {tech_type}\nContent:\n{content}")
                    file_paths.append(filename)
                    total_size += len(content)
            
            if not files_content:
                error_event = {
                    "type": "error",
                    "error": "All provided files are empty",
                    "timestamp": datetime.utcnow().isoformat()
                }
                yield f"data: {json.dumps(error_event)}\n\n"
                return
            
            # Build query for the unified ReAct agent (simplified for natural reasoning)
            query = f"""Please analyze these Infrastructure as Code files:

Technology Type: {request.technology_type or 'auto-detected'}
Module Name: {request.module_name or 'N/A'}
Files: {file_paths}

Files content:
{chr(10).join(files_content)}

Please provide a comprehensive analysis covering:
- What does this automation accomplish?
- What resources does it manage (packages, services, files)?
- What are the dependencies and complexity factors?
- How could this be modernized or migrated to Ansible?
- What are the key configuration patterns and logic?

Use your expertise to thoroughly analyze this Infrastructure as Code."""
            
            # Processing event
            yield f"data: {json.dumps({'type': 'progress', 'message': 'Processing with ReAct AI agent...', 'timestamp': datetime.utcnow().isoformat()})}\n\n"
            
            # Run analysis
            result = registry.execute_query(
                agent_name="iac_phased_analysis_agent",
                query=query,
                files_analyzed=file_paths,
                file_count=len(request.files),
                technology_type=request.technology_type,
                module_name=request.module_name,
                total_code_size=total_size,
                analysis_type="unified_iac_analysis_stream",
                streaming=True
            )
            
            # Final result event
            yield f"data: {json.dumps({'type': 'result', 'data': result, 'timestamp': datetime.utcnow().isoformat()})}\n\n"
            
            # Completion event
            yield f"data: {json.dumps({'type': 'complete', 'message': 'Unified analysis completed successfully', 'timestamp': datetime.utcnow().isoformat()})}\n\n"
            
        except AgentRegistryError as e:
            error_event = {
                "type": "error",
                "error": f"Agent error: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }
            yield f"data: {json.dumps(error_event)}\n\n"
        except Exception as e:
            error_event = {
                "type": "error",
                "error": f"Analysis failed: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }
            yield f"data: {json.dumps(error_event)}\n\n"
            logger.error(f" Streaming unified analysis error: {str(e)}", exc_info=True)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "X-Accel-Buffering": "no",  # Nginx buffering control
        }
    )

# ==== Batch Analysis Endpoint ====
@router.post("/analyze/batch")
async def analyze_batch(
    requests: List[Dict[str, Any]],
    registry: UnifiedAgentRegistry = Depends(get_agent_registry)
):
    """Execute multiple analysis requests in batch"""
    try:
        if not requests:
            raise HTTPException(status_code=400, detail="No requests provided")
        
        if len(requests) > 50:  # Reasonable batch size limit
            raise HTTPException(status_code=400, detail="Batch size too large (maximum 50 requests)")
        
        logger.info(f"🔄 Processing batch of {len(requests)} requests")
        
        results = []
        successful = 0
        failed = 0
        
        for i, req in enumerate(requests):
            try:
                # Validate request structure
                agent_name = req.get("agent_name")
                query = req.get("query")
                metadata = req.get("metadata", {})
                
                if not agent_name or not isinstance(agent_name, str):
                    results.append({
                        "index": i,
                        "success": False,
                        "error": "Missing or invalid agent_name"
                    })
                    failed += 1
                    continue
                
                if not query or not isinstance(query, str) or not query.strip():
                    results.append({
                        "index": i,
                        "success": False,
                        "error": "Missing or invalid query"
                    })
                    failed += 1
                    continue
                
                # Execute query
                result = registry.execute_query(
                    agent_name=agent_name,
                    query=query.strip(),
                    batch_index=i,
                    batch_total=len(requests),
                    **metadata
                )
                
                results.append({
                    "index": i,
                    "success": True,
                    "result": result
                })
                successful += 1
                
            except AgentRegistryError as e:
                results.append({
                    "index": i,
                    "success": False,
                    "error": f"Agent error: {str(e)}"
                })
                failed += 1
            except Exception as e:
                results.append({
                    "index": i,
                    "success": False,
                    "error": f"Execution error: {str(e)}"
                })
                failed += 1
                logger.error(f" Batch request {i} failed: {str(e)}")
        
        logger.info(f" Batch processing completed: {successful} successful, {failed} failed")
        
        return {
            "batch_results": results,
            "summary": {
                "total_requests": len(requests),
                "successful": successful,
                "failed": failed,
                "success_rate": successful / len(requests) if requests else 0
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f" Batch analysis error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch analysis failed: {str(e)}")

# ==== Health and Status Endpoints ====
@router.get("/agents/status")
async def get_agents_status(
    registry: UnifiedAgentRegistry = Depends(get_agent_registry)
):
    """Get status of all configured agents"""
    try:
        agents = registry.list_available_agents()
        return {
            "agents": agents,
            "total_agents": len(agents),
            "unified_agent_enabled": any(agent["name"] == "iac_phased_analysis_agent" for agent in agents),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f" Error getting agents status: {str(e)}")
        raise HTTPException(status_code=500, detail="Error retrieving agents status")

@router.get("/analysis/capabilities")
async def get_analysis_capabilities():
    """Get supported analysis capabilities"""
    return {
        "unified_analysis": {
            "enabled": True,
            "supported_technologies": [
                "chef", "salt", "ansible", "terraform", 
                "puppet", "shell", "bladelogic", "unknown"
            ],
            "features": [
                "three_phase_react_analysis",
                "technology_auto_detection", 
                "structured_json_output",
                "streaming_support",
                "batch_processing"
            ]
        },
        "specialized_agents": {
            "ansible_upgrade_analysis": "ReAct-based upgrade assessment",
            "context": "RAG-based pattern retrieval", 
            "generate": "Ansible playbook generation",
            "validate": "Ansible lint validation"
        },
        "legacy_endpoints": [
            "/chef/analyze", "/salt/analyze", 
            "/bladelogic/analyze", "/shell/analyze"
        ],
        "timestamp": datetime.utcnow().isoformat()
    }
    
from fastapi.responses import StreamingResponse

@router.post("/context/stream")
async def stream_context(
    request: ContextRequest,
    registry: UnifiedAgentRegistry = Depends(get_agent_registry)
):
    """Stream context (RAG) search results with progress updates"""

    async def event_generator():
        try:
            # Start event
            yield f"data: {json.dumps({'type': 'start', 'message': 'Starting context search...', 'timestamp': datetime.utcnow().isoformat()})}\n\n"
            await asyncio.sleep(0.1)

            # Progress event
            yield f"data: {json.dumps({'type': 'progress', 'message': 'Retrieving RAG content from context agent...', 'timestamp': datetime.utcnow().isoformat()})}\n\n"
            await asyncio.sleep(0.1)

            # Run the context agent query (no streaming in backend, so just one big step)
            result = registry.execute_query(
                agent_name="context",
                query=request.query.strip(),
                search_type="context_retrieval",
                **(request.metadata or {})
            )

            # Result event
            yield f"data: {json.dumps({'type': 'result', 'data': result, 'timestamp': datetime.utcnow().isoformat()})}\n\n"

            # Completion event
            yield f"data: {json.dumps({'type': 'complete', 'message': 'Context search completed successfully', 'timestamp': datetime.utcnow().isoformat()})}\n\n"

        except AgentRegistryError as e:
            error_event = {
                "type": "error",
                "error": f"Agent error: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }
            yield f"data: {json.dumps(error_event)}\n\n"
        except Exception as e:
            error_event = {
                "type": "error",
                "error": f"Context streaming failed: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }
            yield f"data: {json.dumps(error_event)}\n\n"
            logger.error(f" Streaming context error: {str(e)}", exc_info=True)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "X-Accel-Buffering": "no",  # Nginx buffering control
        }
    )

@router.post("/generate/stream")
async def generate_code_stream(
    request: GenerateRequest,
    registry: UnifiedAgentRegistry = Depends(get_agent_registry)
):
    """Generate Ansible code with streaming progress"""

    async def event_generator():
        try:
            if not request.description or not request.description.strip():
                error_event = {
                    "type": "error",
                    "error": "Description cannot be empty",
                    "timestamp": datetime.utcnow().isoformat()
                }
                yield f"data: {json.dumps(error_event)}\n\n"
                return

            # Start event
            yield f"data: {json.dumps({'type': 'start', 'message': 'Starting code generation...', 'timestamp': datetime.utcnow().isoformat()})}\n\n"
            await asyncio.sleep(0.1)

            # Progress event
            yield f"data: {json.dumps({'type': 'progress', 'message': 'Generating code with codegen agent...', 'timestamp': datetime.utcnow().isoformat()})}\n\n"
            await asyncio.sleep(0.1)

            # Build query with optional context
            query = f"Generate Ansible playbook for: {request.description.strip()}"
            if request.context and request.context.strip():
                query += f"\n\nAdditional context:\n{request.context.strip()}"

            result = registry.execute_query(
                agent_name="generate",
                query=query,
                generation_type="ansible_playbook",
                description_length=len(request.description),
                has_context=bool(request.context and request.context.strip()),
                streaming=True,  # just in case your registry/agent honors this
                **(request.metadata or {})
            )

            # Final result event
            yield f"data: {json.dumps({'type': 'result', 'data': result, 'timestamp': datetime.utcnow().isoformat()})}\n\n"

            # Completion event
            yield f"data: {json.dumps({'type': 'complete', 'message': 'Code generation completed successfully', 'timestamp': datetime.utcnow().isoformat()})}\n\n"

        except AgentRegistryError as e:
            error_event = {
                "type": "error",
                "error": f"Agent error: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }
            yield f"data: {json.dumps(error_event)}\n\n"
        except Exception as e:
            error_event = {
                "type": "error",
                "error": f"Code generation failed: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }
            yield f"data: {json.dumps(error_event)}\n\n"
            logger.error(f" Streaming code generation error: {str(e)}", exc_info=True)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "X-Accel-Buffering": "no",  # Nginx buffering control
        }
    )
