"""
Spec Kit Planning Integration for Orchestrator

Leverages GitHub Spec Kit planning methodology for worker assignment.
Based on: https://github.com/github/spec-kit.git
"""

from typing import Dict, List, Any, Union
from langchain_core.tools import tool


class InfrastructurePlanningTemplate:
    """
    Infrastructure planning template based on Spec Kit principles.
    Adapted from GitHub Spec Kit for infrastructure analysis orchestration.
    """
    
    @staticmethod
    def create_analysis_constitution(platform: str, complexity: str) -> Dict[str, Any]:
        """Create analysis constitution based on Spec Kit principles"""
        
        return {
            "core_principles": [
                "Prioritize accuracy over speed in platform detection",
                "Ensure comprehensive fact extraction before analysis", 
                "Generate actionable specifications with clear acceptance criteria",
                "Include security considerations in all analyses",
                "Provide migration recommendations based on best practices"
            ],
            "quality_standards": {
                "minimum_confidence": 0.7,
                "required_workers": ["platform_detector", "structured_analyzer", "spec_generator"],
                "validation_required": True,
                "documentation_required": True
            },
            "platform_specific": {
                platform: {
                    "specialized_extraction": True,
                    "template_analysis": "chef" in platform.lower(),
                    "dependency_mapping": True,
                    "security_scan": True
                }
            },
            "complexity_adjustments": {
                complexity: {
                    "analysis_depth": "comprehensive" if complexity == "high" else "standard",
                    "validation_level": "thorough" if complexity == "high" else "standard",
                    "documentation_detail": "extensive" if complexity == "high" else "standard"
                }
            }
        }
    
    @staticmethod
    def generate_worker_plan(
        detected_platforms: List[str], 
        complexity: str,
        constitution: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate worker execution plan using Spec Kit methodology"""
        
        worker_plan = []
        task_counter = 1
        
        # Phase 1: Discovery (Spec Kit principle - understand requirements first)
        worker_plan.append({
            "phase": "discovery",
            "task_id": f"task_{task_counter:03d}",
            "worker_type": "platform_detector",
            "priority": 1,
            "description": "Comprehensive platform detection and initial assessment",
            "success_criteria": [
                "Platform identified with >70% confidence",
                "Multiple platform scenarios handled",
                "Evidence documented for detection"
            ],
            "dependencies": [],
            "estimated_duration": 3
        })
        task_counter += 1
        
        # Phase 2: Extraction (platform-specific fact gathering)
        primary_platform = detected_platforms[0] if detected_platforms else "unknown"
        
        if primary_platform in ["chef", "puppet", "terraform"]:
            worker_plan.append({
                "phase": "extraction",
                "task_id": f"task_{task_counter:03d}",
                "worker_type": f"{primary_platform}_extractor",
                "priority": 2,
                "description": f"Specialized {primary_platform} fact extraction using domain tools",
                "success_criteria": [
                    f"{primary_platform.title()} facts extracted successfully",
                    "Component relationships mapped",
                    "Dependencies identified"
                ],
                "dependencies": ["task_001"],
                "estimated_duration": 5 if complexity == "high" else 3
            })
        else:
            worker_plan.append({
                "phase": "extraction", 
                "task_id": f"task_{task_counter:03d}",
                "worker_type": "generic_extractor",
                "priority": 2,
                "description": "Generic infrastructure fact extraction for unknown platform",
                "success_criteria": [
                    "Basic infrastructure facts extracted",
                    "Configuration patterns identified",
                    "Best-effort component analysis"
                ],
                "dependencies": ["task_001"],
                "estimated_duration": 4
            })
        task_counter += 1
        
        # Phase 3: Analysis (Spec Kit principle - thorough analysis before recommendations)
        worker_plan.append({
            "phase": "analysis",
            "task_id": f"task_{task_counter:03d}",
            "worker_type": "structured_analyzer",
            "priority": 3,
            "description": "Comprehensive structured analysis generation",
            "success_criteria": [
                "JSON analysis generated with all required sections",
                "Security considerations documented", 
                "Migration recommendations provided",
                "Quality metrics meet standards"
            ],
            "dependencies": [f"task_{task_counter-1:03d}"],
            "estimated_duration": 4 if complexity == "high" else 3
        })
        task_counter += 1
        
        # Phase 4: Specification (Spec Kit enhanced specification generation)
        worker_plan.append({
            "phase": "specification",
            "task_id": f"task_{task_counter:03d}",
            "worker_type": "spec_generator",
            "priority": 4,
            "description": "Enhanced specification generation using Spec Kit methodology",
            "success_criteria": [
                "Professional-grade specification created",
                "Review checklists included",
                "Acceptance criteria defined",
                "Implementation guidelines provided"
            ],
            "dependencies": [f"task_{task_counter-1:03d}"],
            "estimated_duration": 3
        })
        task_counter += 1
        
        # Phase 5: Storage (with deduplication)
        worker_plan.append({
            "phase": "storage",
            "task_id": f"task_{task_counter:03d}",
            "worker_type": "storage_manager",
            "priority": 5,
            "description": "Neo4j storage with intelligent deduplication",
            "success_criteria": [
                "Analysis stored successfully",
                "Deduplication checks completed",
                "Knowledge graph relationships created",
                "Storage integrity verified"
            ],
            "dependencies": [f"task_{task_counter-1:03d}", f"task_{task_counter-2:03d}"],
            "estimated_duration": 2
        })
        task_counter += 1
        
        # Phase 6: Validation (optional for high complexity)
        if complexity == "high" or constitution["quality_standards"]["validation_required"]:
            worker_plan.append({
                "phase": "validation",
                "task_id": f"task_{task_counter:03d}",
                "worker_type": "validator",
                "priority": 6,
                "description": "Comprehensive quality validation and consistency checking",
                "success_criteria": [
                    "All outputs validated for consistency",
                    "Quality standards verified",
                    "Specification review completed",
                    "Final approval criteria met"
                ],
                "dependencies": [f"task_{task_counter-1:03d}"],
                "estimated_duration": 2
            })
        
        return worker_plan


@tool
def create_spec_kit_plan(
    platform_analysis: Union[dict, str],
    code: str,
    requirements: Union[dict, str] = None
) -> Dict[str, Any]:
    """
    Create prod-grade orchestration plan using Spec Kit methodology.
    
    Based on GitHub Spec Kit planning principles adapted for infrastructure analysis.
    Creates comprehensive, phase-based execution plans with success criteria.
    
    Args:
        platform_analysis: Initial platform detection results
        code: Infrastructure code being analyzed
        requirements: Additional orchestration requirements
        
    Returns:
        Prod-grade orchestration plan with Spec Kit structure and quality
    """
    
    try:
        # Handle both dict and string inputs (LLM tool calling quirk)
        if isinstance(platform_analysis, str):
            import json
            import ast
            try:
                # Try JSON parsing first
                platform_analysis = json.loads(platform_analysis)
            except json.JSONDecodeError:
                try:
                    # Fallback to literal_eval for dict-like strings
                    platform_analysis = ast.literal_eval(platform_analysis)
                except (ValueError, SyntaxError):
                    # If parsing fails, create minimal dict
                    platform_analysis = {"detected_platforms": ["unknown"], "complexity_level": "medium"}
        
        # Handle requirements parameter similarly
        if isinstance(requirements, str):
            import json
            import ast
            try:
                requirements = json.loads(requirements)
            except json.JSONDecodeError:
                try:
                    requirements = ast.literal_eval(requirements)
                except (ValueError, SyntaxError):
                    requirements = {}
        elif requirements is None:
            requirements = {}
        
        # Extract analysis information
        detected_platforms = platform_analysis.get("detected_platforms", ["unknown"])
        complexity_level = platform_analysis.get("complexity_level", "medium")
        confidence_scores = platform_analysis.get("confidence_scores", {})
        
        # Create analysis constitution (Spec Kit principle)
        primary_platform = detected_platforms[0] if detected_platforms else "unknown"
        constitution = InfrastructurePlanningTemplate.create_analysis_constitution(
            primary_platform, complexity_level
        )
        
        # Generate worker execution plan
        worker_plan = InfrastructurePlanningTemplate.generate_worker_plan(
            detected_platforms, complexity_level, constitution
        )
        
        # Calculate plan metrics
        total_tasks = len(worker_plan)
        total_duration = sum(task["estimated_duration"] for task in worker_plan)
        critical_path = max(task["priority"] for task in worker_plan)
        
        # Create plan summary
        plan_summary = {
            "plan_metadata": {
                "methodology": "spec_kit_enhanced",
                "primary_platform": primary_platform,
                "complexity_level": complexity_level,
                "total_tasks": total_tasks,
                "estimated_duration": total_duration,
                "critical_path_length": critical_path
            },
            "constitution": constitution,
            "execution_phases": {
                "discovery": [t for t in worker_plan if t["phase"] == "discovery"],
                "extraction": [t for t in worker_plan if t["phase"] == "extraction"],
                "analysis": [t for t in worker_plan if t["phase"] == "analysis"],
                "specification": [t for t in worker_plan if t["phase"] == "specification"],
                "storage": [t for t in worker_plan if t["phase"] == "storage"],
                "validation": [t for t in worker_plan if t["phase"] == "validation"]
            },
            "worker_assignments": worker_plan,
            "quality_gates": [
                {
                    "gate_name": "Platform Detection Quality",
                    "criteria": f"Confidence > {constitution['quality_standards']['minimum_confidence']:.0%}",
                    "dependencies": ["task_001"]
                },
                {
                    "gate_name": "Extraction Completeness",
                    "criteria": "All required facts extracted successfully",
                    "dependencies": ["task_002"]
                },
                {
                    "gate_name": "Analysis Quality",
                    "criteria": "Structured analysis meets all success criteria",
                    "dependencies": ["task_003"]
                },
                {
                    "gate_name": "Specification Quality",
                    "criteria": "Spec Kit enhanced specification with checklists",
                    "dependencies": ["task_004"]
                }
            ]
        }
        
        return {
            "success": True,
            "spec_kit_plan": plan_summary,
            "methodology": "spec_kit_planning",
            "plan_quality": "prod_grade",
            "includes_constitution": True,
            "includes_quality_gates": True
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "spec_kit_plan": {},
            "methodology": "spec_kit_planning_failed"
        }
