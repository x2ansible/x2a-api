"""
Worker Assignment Tool for Orchestrator

This tool creates specific worker task assignments based on infrastructure analysis.
"""

from typing import Dict, List, Any, Union
from langchain_core.tools import tool
from pydantic import BaseModel

from ....state import WorkerTask


class WorkerAssignment(BaseModel):
    """Structured worker assignment"""
    worker_type: str
    platform: str
    priority: int
    requirements: Dict[str, Any]
    estimated_duration: int


@tool
def create_worker_assignments(analysis: Union[dict, str], code: str = "") -> dict:
    """
    Create dynamic worker task assignments based on intelligent analysis.
    
    This tool uses the LLM's reasoning to create optimal task assignments
    for workers based on the infrastructure analysis results and code characteristics.
    
    Args:
        analysis: Results from analyze_infrastructure_requirements 
        code: Original infrastructure code
        
    Returns:
        Dictionary with success status and list of worker assignments
    """
    
    try:
        # Handle both dict and string inputs (LLM tool calling quirk)
        if isinstance(analysis, str):
            import json
            import ast
            try:
                # Try JSON parsing first
                analysis = json.loads(analysis)
            except json.JSONDecodeError:
                try:
                    # Fallback to literal_eval for dict-like strings
                    analysis = ast.literal_eval(analysis)
                except (ValueError, SyntaxError):
                    # If parsing fails, create minimal dict
                    analysis = {"detected_platforms": ["unknown"], "complexity_level": "medium"}
        
        assignments = []
        
        detected_platforms = analysis.get("detected_platforms", ["unknown"])
        complexity_level = analysis.get("complexity_level", "medium")
        code_characteristics = analysis.get("code_characteristics", {})
        processing_recommendations = analysis.get("processing_recommendations", [])
        
        # If code is empty, try to extract it from analysis
        if not code:
            code = analysis.get("input_code", analysis.get("code", ""))
        
        # Determine optimal worker strategy based on analysis
        
        # 1. Platform Detection (always first priority)
        assignments.append(WorkerAssignment(
            worker_type="platform_detector",
            platform="all",
            priority=1,
            requirements={
                "analysis_type": "comprehensive_detection",
                "confidence_threshold": 0.7 if complexity_level == "high" else 0.5,
                "multi_platform_support": len(detected_platforms) > 1
            },
            estimated_duration=3 if len(detected_platforms) > 1 else 2
        ))
        
        # 2. Platform-specific extraction workers (priority 2)
        extraction_priority = 2
        for platform in detected_platforms:
            if platform in ["chef", "puppet", "terraform", "ansible"]:
                # Determine extraction requirements based on code characteristics
                requirements = {
                    "extraction_depth": complexity_level,
                    "include_dependencies": code_characteristics.get("appears_modular", False),
                    "parse_templates": code_characteristics.get("contains_templates", False),
                    "variable_analysis": code_characteristics.get("contains_variables", False),
                    "ast_parsing": platform in ["chef", "puppet"],  # Use AST for these
                    "pattern_matching": platform in ["terraform", "ansible"]
                }
                
                duration = 3
                if complexity_level == "high":
                    duration = 6
                elif code_characteristics.get("total_length", 0) > 5000:
                    duration = 5
                
                assignments.append(WorkerAssignment(
                    worker_type=f"{platform}_extractor",
                    platform=platform,
                    priority=extraction_priority,
                    requirements=requirements,
                    estimated_duration=duration
                ))
            else:
                # Generic extractor for unknown platforms
                assignments.append(WorkerAssignment(
                    worker_type="generic_extractor",
                    platform=platform,
                    priority=extraction_priority,
                    requirements={
                        "pattern_analysis": True,
                        "language_detection": True,
                        "structure_analysis": True
                    },
                    estimated_duration=4
                ))
        
        # 3. Analysis workers (priority 3)
        analysis_requirements = {
            "analysis_depth": complexity_level,
            "security_analysis": True,
            "migration_assessment": True,
            "dependency_analysis": code_characteristics.get("appears_modular", False),
            "complexity_metrics": True
        }
        
        assignments.append(WorkerAssignment(
            worker_type="structured_analyzer",
            platform="all",
            priority=3,
            requirements=analysis_requirements,
            estimated_duration=4 if complexity_level == "high" else 3
        ))
        
        # 4. Specification generation (priority 4)
        spec_requirements = {
            "format": "natural_language",
            "spec_kit_methodology": True,
            "include_deployment_guide": complexity_level != "low",
            "detail_level": complexity_level,
            "platform_specific_guidance": len(detected_platforms) == 1
        }
        
        assignments.append(WorkerAssignment(
            worker_type="spec_generator",
            platform="all",
            priority=4,
            requirements=spec_requirements,
            estimated_duration=4 if complexity_level == "high" else 3
        ))
        
        # 5. Storage and validation (priority 5)
        storage_requirements = {
            "deduplication": True,
            "create_relationships": True,
            "vector_indexing": complexity_level == "high",
            "metadata_enrichment": True,
            "quality_validation": True
        }
        
        assignments.append(WorkerAssignment(
            worker_type="storage_manager",
            platform="all",
            priority=5,
            requirements=storage_requirements,
            estimated_duration=3
        ))
        
        return {
            "success": True,
            "worker_assignments": assignments,
            "assignment_strategy": f"Dynamic assignment for {complexity_level} complexity {detected_platforms} platforms",
            "total_workers": len(assignments),
            "estimated_total_duration": sum(w.estimated_duration for w in assignments),
            "processing_recommendations": processing_recommendations
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "worker_assignments": [],
            "fallback_message": "Failed to create dynamic assignments"
        }
