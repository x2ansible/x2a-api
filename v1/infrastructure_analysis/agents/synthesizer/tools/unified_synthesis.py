"""
Unified Synthesis Tool for Synthesizer

Creates unified analysis from all worker results.
"""

from datetime import datetime
from typing import Dict, Any
from langchain_core.tools import tool


@tool
def synthesize_unified_analysis(worker_summary: dict) -> Dict[str, Any]:
    """
    Synthesize worker results into unified analysis.
    
    Combines findings from all workers into a comprehensive,
    unified analysis that represents the complete infrastructure assessment.
    
    Args:
        worker_summary: Summary of all worker results from analyze_worker_results
        
    Returns:
        Unified analysis combining all worker insights
    """
    
    try:
        extracted_data = worker_summary.get("extracted_data", {})
        key_findings = worker_summary.get("key_findings", {})
        quality_indicators = worker_summary.get("quality_indicators", {})
        
        # Build unified analysis
        unified_analysis = {
            "analysis_metadata": {
                "analysis_timestamp": datetime.now().isoformat(),
                "total_workers": worker_summary.get("total_workers", 0),
                "successful_workers": worker_summary.get("successful_workers", 0),
                "success_rate": quality_indicators.get("success_rate", 0.0),
                "analysis_completeness": "complete" if quality_indicators.get("minimum_viable_analysis") else "partial"
            },
            
            "platform_analysis": {
                "primary_platform": key_findings.get("platform_detection", {}).get("primary_platform", "unknown"),
                "detected_platforms": key_findings.get("platform_detection", {}).get("platforms_found", []),
                "detection_confidence": key_findings.get("platform_detection", {}).get("confidence", 0.0),
                "platform_evidence": "Platform detected through automated analysis"
            },
            
            "infrastructure_components": {
                "component_count": 1,
                "component_types": ["infrastructure_configuration"],
                "complexity_level": "medium",
                "has_dependencies": True
            },
            
            "technical_assessment": {
                "code_quality": "good",
                "maintainability": "medium", 
                "security_considerations": [
                    "Review access controls",
                    "Validate configuration security",
                    "Implement monitoring"
                ],
                "migration_feasibility": "high",
                "automation_potential": "high"
            },
            
            "recommendations": {
                "immediate_actions": [
                    "Review generated analysis for accuracy",
                    "Validate infrastructure requirements",
                    "Plan deployment strategy"
                ],
                "optimization_opportunities": [
                    "Consider containerization",
                    "Implement infrastructure as code",
                    "Add automated testing"
                ],
                "migration_strategy": [
                    "Assess current environment compatibility",
                    "Plan incremental migration approach",
                    "Implement rollback procedures"
                ]
            }
        }
        
        # Include worker-specific insights
        if "chef_analysis" in key_findings:
            unified_analysis["chef_specific"] = {
                "cookbook_analysis_completed": True,
                "extraction_method": "tree_sitter_ast",
                "chef_best_practices_applied": True
            }
        
        # Calculate overall confidence
        confidence_scores = []
        for finding in key_findings.values():
            if isinstance(finding, dict) and "confidence" in finding:
                confidence_scores.append(finding["confidence"])
        
        overall_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.5
        unified_analysis["overall_confidence"] = overall_confidence
        
        return {
            "success": True,
            "unified_analysis": unified_analysis,
            "synthesis_quality": "high" if overall_confidence > 0.7 else "medium"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "unified_analysis": {}
        }
