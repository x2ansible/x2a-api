from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel, Field
from typing import Dict, Optional, Literal
from datetime import datetime
from fastapi.responses import StreamingResponse
import asyncio
import json

from agents.chef_analysis.agent import ChefAnalysisAgent

router = APIRouter(prefix="/chef", tags=["chef-analysis"])

class ChefAnalyzeRequest(BaseModel):
    files: Dict[str, str] = Field(..., description="Dictionary of filename to file content")
    method: Optional[Literal["standard", "chaining", "auto"]] = Field(
        default="auto", 
        description="Analysis method: 'standard' (single-step), 'chaining' (multi-step), or 'auto' (intelligent selection)"
    )

class ChefAnalysisResponse(BaseModel):
    success: bool
    cookbook_name: str
    analysis_method: str
    version_requirements: Dict
    dependencies: Dict
    functionality: Dict
    recommendations: Dict
    session_info: Dict
    metadata: Optional[Dict] = None
    chain_details: Optional[Dict] = None

# Dependency injection for ChefAnalysisAgent
def get_chef_agent(request: Request) -> ChefAnalysisAgent:
    if not hasattr(request.app.state, 'chef_analysis_agent'):
        raise HTTPException(status_code=503, detail="Chef analysis agent not available")
    return request.app.state.chef_analysis_agent

@router.post("/analyze", response_model=ChefAnalysisResponse)
async def analyze_cookbook(
    request: ChefAnalyzeRequest,
    agent: ChefAnalysisAgent = Depends(get_chef_agent),
):
    """
    Analyze Chef cookbook using specified method (standard, chaining, or auto-detection)
    
    **Methods:**
    - `standard`: Single-step analysis (legacy, faster but less reliable)
    - `chaining`: Multi-step prompt chaining (recommended, better quality)
    - `auto`: Intelligent method selection based on cookbook complexity
    """
    cookbook_name = f"uploaded_cookbook_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    cookbook_data = {
        "name": cookbook_name,
        "files": request.files,
    }
    
    try:
        # Use the enhanced ChefAnalysisAgent with method selection
        result = await agent.analyze_cookbook(
            cookbook_data=cookbook_data,
            method=request.method
        )
        
        result["session_info"] = {
            **result.get("session_info", {}),
            "cookbook_name": cookbook_name,
            "requested_method": request.method
        }
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis error: {e}")

@router.post("/analyze/stream")
async def analyze_cookbook_stream(
    request: ChefAnalyzeRequest,
    agent: ChefAnalysisAgent = Depends(get_chef_agent),
):
    """
    Stream Chef cookbook analysis with real-time progress updates
    
    **Event Types:**
    - `progress`: Analysis progress updates
    - `final_analysis`: Complete analysis result
    - `error`: Error information
    """
    cookbook_name = f"stream_cookbook_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    cookbook_data = {
        "name": cookbook_name,
        "files": request.files,
    }
    
    async def event_generator():
        try:
            async for event in agent.analyze_cookbook_stream(
                cookbook_data=cookbook_data,
                method=request.method
            ):
                if event.get("type") == "final_analysis" and "data" in event:
                    event["data"]["session_info"] = {
                        **event["data"].get("session_info", {}),
                        "cookbook_name": cookbook_name,
                        "requested_method": request.method
                    }
                await asyncio.sleep(0.1)
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            error_event = {
                "type": "error",
                "error": str(e),
                "method": request.method,
                "cookbook_name": cookbook_name
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

@router.post("/analyze/compare")
async def compare_analysis_methods(
    files: Dict[str, str],
    agent: ChefAnalysisAgent = Depends(get_chef_agent),
):
    """
    Compare standard vs prompt chaining analysis methods side by side
    
    **Returns:**
    - Results from both methods
    - Quality comparison metrics
    - Performance statistics
    - Recommendations on which method to use
    """
    cookbook_name = f"comparison_cookbook_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    cookbook_data = {
        "name": cookbook_name,
        "files": files,
    }
    
    try:
        # Run both analyses in parallel
        import asyncio
        
        async def run_standard():
            return await agent.analyze_cookbook(cookbook_data, method="standard")
        
        async def run_chaining():
            return await agent.analyze_cookbook(cookbook_data, method="chaining")
        
        start_time = datetime.now()
        
        # Execute both methods concurrently
        standard_task = asyncio.create_task(run_standard())
        chaining_task = asyncio.create_task(run_chaining())
        
        standard_result, chaining_result = await asyncio.gather(
            standard_task, chaining_task, return_exceptions=True
        )
        
        total_time = (datetime.now() - start_time).total_seconds()
        
        # Handle any exceptions
        if isinstance(standard_result, Exception):
            standard_result = {"error": str(standard_result), "success": False}
        if isinstance(chaining_result, Exception):
            chaining_result = {"error": str(chaining_result), "success": False}
        
        # Compare results
        comparison = {
            "cookbook_name": cookbook_name,
            "timestamp": datetime.now().isoformat(),
            "total_comparison_time": total_time,
            "methods_compared": ["standard", "prompt_chaining"],
            "results": {
                "standard": {
                    "success": standard_result.get("success", False),
                    "analysis": standard_result,
                    "method": "standard"
                },
                "prompt_chaining": {
                    "success": chaining_result.get("success", False), 
                    "analysis": chaining_result,
                    "method": "prompt_chaining"
                }
            },
            "comparison_metrics": _compare_analysis_quality(standard_result, chaining_result),
            "recommendation": _get_method_recommendation(standard_result, chaining_result)
        }
        
        return comparison
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Comparison failed: {e}")

def _compare_analysis_quality(standard_result: Dict, chaining_result: Dict) -> Dict:
    """Compare the quality and completeness of both analysis methods"""
    metrics = {
        "completeness": {},
        "consistency": {},
        "reliability": {},
        "detail_level": {}
    }
    
    # Check completeness - how many fields are populated
    standard_fields = _count_populated_fields(standard_result)
    chaining_fields = _count_populated_fields(chaining_result)
    
    metrics["completeness"] = {
        "standard_populated_fields": standard_fields,
        "chaining_populated_fields": chaining_fields,
        "winner": "chaining" if chaining_fields > standard_fields else "standard" if standard_fields > chaining_fields else "tie",
        "improvement": abs(chaining_fields - standard_fields)
    }
    
    # Check consistency - do both methods agree on key findings
    consistency_score = _calculate_consistency_score(standard_result, chaining_result)
    metrics["consistency"] = {
        "agreement_score": consistency_score,
        "key_agreements": _find_key_agreements(standard_result, chaining_result),
        "key_disagreements": _find_key_disagreements(standard_result, chaining_result)
    }
    
    # Check reliability - success rates and error handling
    metrics["reliability"] = {
        "standard_success": standard_result.get("success", False),
        "chaining_success": chaining_result.get("success", False),
        "standard_has_errors": "error" in standard_result,
        "chaining_has_errors": "error" in chaining_result,
        "more_reliable": _determine_more_reliable_method(standard_result, chaining_result)
    }
    
    # Check detail level - quality of analysis depth
    metrics["detail_level"] = {
        "standard_has_chain_details": "chain_details" in standard_result,
        "chaining_has_chain_details": "chain_details" in chaining_result,
        "chaining_reasoning_steps": len(chaining_result.get("chain_details", {})),
        "detail_winner": "chaining" if "chain_details" in chaining_result else "standard"
    }
    
    return metrics

def _count_populated_fields(result: Dict) -> int:
    """Count how many fields are meaningfully populated"""
    if not isinstance(result, dict):
        return 0
    
    count = 0
    def count_fields(obj, path=""):
        nonlocal count
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, (dict, list)):
                    count_fields(value, f"{path}.{key}" if path else key)
                elif value is not None and value != "" and value != []:
                    count += 1
        elif isinstance(obj, list) and obj:
            count += 1
    
    count_fields(result)
    return count

def _calculate_consistency_score(standard: Dict, chaining: Dict) -> float:
    """Calculate agreement score between two analysis results"""
    if not isinstance(standard, dict) or not isinstance(chaining, dict):
        return 0.0
    
    agreements = 0
    total_comparisons = 0
    
    # Compare key fields
    key_fields = [
        "version_requirements.migration_effort",
        "dependencies.is_wrapper", 
        "functionality.reusability",
        "recommendations.consolidation_action"
    ]
    
    for field_path in key_fields:
        standard_val = _get_nested_value(standard, field_path)
        chaining_val = _get_nested_value(chaining, field_path)
        
        if standard_val is not None and chaining_val is not None:
            total_comparisons += 1
            if standard_val == chaining_val:
                agreements += 1
    
    return agreements / total_comparisons if total_comparisons > 0 else 0.0

def _get_nested_value(obj: Dict, path: str):
    """Get nested dictionary value by dot notation path"""
    try:
        keys = path.split('.')
        value = obj
        for key in keys:
            value = value[key]
        return value
    except (KeyError, TypeError):
        return None

def _find_key_agreements(standard: Dict, chaining: Dict) -> list:
    """Find areas where both methods agree"""
    agreements = []
    
    # Check major classifications
    standard_wrapper = _get_nested_value(standard, "dependencies.is_wrapper")
    chaining_wrapper = _get_nested_value(chaining, "dependencies.is_wrapper")
    if standard_wrapper == chaining_wrapper and standard_wrapper is not None:
        agreements.append(f"Both identify wrapper status as: {standard_wrapper}")
    
    standard_effort = _get_nested_value(standard, "version_requirements.migration_effort")
    chaining_effort = _get_nested_value(chaining, "version_requirements.migration_effort")
    if standard_effort == chaining_effort and standard_effort is not None:
        agreements.append(f"Both assess migration effort as: {standard_effort}")
    
    standard_action = _get_nested_value(standard, "recommendations.consolidation_action")
    chaining_action = _get_nested_value(chaining, "recommendations.consolidation_action")
    if standard_action == chaining_action and standard_action is not None:
        agreements.append(f"Both recommend: {standard_action}")
    
    return agreements

def _find_key_disagreements(standard: Dict, chaining: Dict) -> list:
    """Find areas where methods disagree"""
    disagreements = []
    
    # Check for disagreements in key assessments
    comparisons = [
        ("dependencies.is_wrapper", "Wrapper identification"),
        ("version_requirements.migration_effort", "Migration effort"),
        ("functionality.reusability", "Reusability assessment"),
        ("recommendations.consolidation_action", "Consolidation recommendation")
    ]
    
    for field_path, description in comparisons:
        standard_val = _get_nested_value(standard, field_path)
        chaining_val = _get_nested_value(chaining, field_path)
        
        if (standard_val is not None and chaining_val is not None and 
            standard_val != chaining_val):
            disagreements.append(f"{description}: Standard={standard_val}, Chaining={chaining_val}")
    
    return disagreements

def _determine_more_reliable_method(standard: Dict, chaining: Dict) -> str:
    """Determine which method appears more reliable"""
    standard_success = standard.get("success", False)
    chaining_success = chaining.get("success", False)
    
    if chaining_success and not standard_success:
        return "chaining"
    elif standard_success and not chaining_success:
        return "standard"
    elif chaining_success and standard_success:
        # Both succeeded, check for detailed analysis
        if "chain_details" in chaining:
            return "chaining"
        else:
            return "tie"
    else:
        return "neither"

def _get_method_recommendation(standard: Dict, chaining: Dict) -> Dict:
    """Provide recommendation on which method to use"""
    metrics = _compare_analysis_quality(standard, chaining)
    
    # Score each method
    standard_score = 0
    chaining_score = 0
    
    # Reliability scoring
    if metrics["reliability"]["standard_success"]:
        standard_score += 2
    if metrics["reliability"]["chaining_success"]:
        chaining_score += 2
    
    # Completeness scoring
    if metrics["completeness"]["winner"] == "standard":
        standard_score += 1
    elif metrics["completeness"]["winner"] == "chaining":
        chaining_score += 1
    
    # Detail level scoring
    if metrics["detail_level"]["detail_winner"] == "chaining":
        chaining_score += 2
    
    # Consistency bonus (both methods agreeing is good)
    if metrics["consistency"]["agreement_score"] > 0.7:
        standard_score += 1
        chaining_score += 1
    
    # Determine recommendation
    if chaining_score > standard_score:
        recommended = "chaining"
        rationale = "Prompt chaining provides better analysis quality and more detailed reasoning"
    elif standard_score > chaining_score:
        recommended = "standard"
        rationale = "Standard method was more reliable for this specific cookbook"
    else:
        recommended = "chaining"  # Default to chaining for ties
        rationale = "Both methods performed similarly, but chaining provides better insight into reasoning"
    
    return {
        "recommended_method": recommended,
        "rationale": rationale,
        "scores": {
            "standard": standard_score,
            "chaining": chaining_score
        },
        "when_to_use_standard": "Simple cookbooks, resource constraints, or when speed is critical",
        "when_to_use_chaining": "Complex cookbooks, detailed analysis needed, or production environments"
    }

@router.get("/methods")
async def get_available_methods():
    """Get information about available analysis methods"""
    return {
        "available_methods": [
            {
                "name": "standard",
                "description": "Single-step analysis using monolithic prompt",
                "pros": ["Faster execution", "Single LLM call", "Lower resource usage"],
                "cons": ["Complex prompts", "Less reliable JSON", "Hard to debug failures", "Limited reasoning visibility"],
                "best_for": ["Simple cookbooks", "Quick analysis", "Resource-constrained environments"],
                "typical_duration": "5-15 seconds"
            },
            {
                "name": "chaining", 
                "description": "Multi-step analysis using prompt chaining",
                "pros": ["Better reasoning", "More reliable JSON", "Easier debugging", "Context awareness", "Progressive analysis"],
                "cons": ["Multiple LLM calls", "Slower execution", "Higher resource usage"],
                "best_for": ["Complex cookbooks", "Detailed analysis", "Production environments", "Migration planning"],
                "typical_duration": "15-45 seconds"
            },
            {
                "name": "auto",
                "description": "Intelligent method selection based on cookbook complexity",
                "pros": ["Best of both worlds", "Adaptive to complexity", "No manual decision needed"],
                "cons": ["Unpredictable method selection"],
                "best_for": ["General use", "Mixed cookbook types", "Automated workflows"],
                "selection_criteria": ["File count", "Content size", "Presence of attributes/recipes", "Overall complexity"]
            }
        ],
        "default_method": "auto",
        "recommendation": "Use 'auto' for general use, 'chaining' for detailed analysis, 'standard' for speed"
    }

@router.get("/status")
async def get_analysis_status(request: Request):
    """Get status of the Chef analysis agent"""
    status = {
        "timestamp": datetime.now().isoformat(),
        "agent_available": False,
        "agent_status": {}
    }
    
    # Check agent availability and status
    if hasattr(request.app.state, 'chef_analysis_agent'):
        try:
            agent = request.app.state.chef_analysis_agent
            status["agent_available"] = True
            status["agent_status"] = agent.get_status()
            status["agent_status"]["health"] = await agent.health_check()
        except Exception as e:
            status["agent_status"] = {"error": str(e), "health": False}
    
    return status

@router.get("/capabilities")
async def get_chef_capabilities():
    """Get detailed information about Chef analysis capabilities"""
    return {
        "analysis_capabilities": {
            "version_requirements": {
                "description": "Determines minimum Chef and Ruby version requirements",
                "outputs": ["min_chef_version", "min_ruby_version", "migration_effort", "estimated_hours", "deprecated_features"]
            },
            "dependency_analysis": {
                "description": "Maps cookbook dependencies and wrapper patterns",
                "outputs": ["is_wrapper", "wrapped_cookbooks", "direct_deps", "runtime_deps", "circular_risk"]
            },
            "functionality_assessment": {
                "description": "Analyzes what the cookbook does and how it can be used",
                "outputs": ["primary_purpose", "services", "packages", "files_managed", "reusability", "customization_points"]
            },
            "strategic_recommendations": {
                "description": "Provides migration and consolidation guidance",
                "outputs": ["consolidation_action", "rationale", "migration_priority", "risk_factors"]
            }
        },
        "supported_cookbook_types": [
            "wrapper cookbooks",
            "library cookbooks", 
            "application cookbooks",
            "custom cookbooks"
        ],
        "supported_file_types": [
            "metadata.rb",
            "recipes/*.rb",
            "attributes/*.rb", 
            "templates/*",
            "files/*",
            "libraries/*.rb"
        ],
        "analysis_methods": {
            "prompt_chaining": {
                "steps": [
                    "Structure Analysis",
                    "Version Requirements Analysis", 
                    "Dependency Analysis",
                    "Functionality Analysis",
                    "Strategic Recommendations"
                ],
                "context_awareness": "Each step builds on previous analysis",
                "fallback_handling": "Graceful degradation if individual steps fail"
            }
        },
        "output_formats": ["JSON", "Streaming JSON"],
        "session_management": "Dedicated sessions per analysis for context isolation"
    }

# Health check endpoint
@router.get("/health")
async def health_check(request: Request):
    """Health check for Chef analysis service"""
    try:
        if not hasattr(request.app.state, 'chef_analysis_agent'):
            return {"status": "unhealthy", "reason": "Agent not initialized"}
        
        agent = request.app.state.chef_analysis_agent
        health_ok = await agent.health_check()
        
        return {
            "status": "healthy" if health_ok else "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "agent_id": agent.agent_id,
            "prompt_chaining_enabled": agent.enable_prompt_chaining
        }
    except Exception as e:
        return {
            "status": "unhealthy", 
            "reason": str(e),
            "timestamp": datetime.now().isoformat()
        }