"""
Requirements Analyzer Tool for Orchestrator

This tool analyzes infrastructure code to understand what workers and
processing strategies are needed for optimal analysis.
"""

from typing import Dict, List, Any
from langchain_core.tools import tool
from pydantic import BaseModel

# Import existing platform detector
from ....tools import platform_detector


class PlatformAnalysis(BaseModel):
    """Structured platform analysis for orchestrator"""
    detected_platforms: List[str]
    confidence_scores: Dict[str, float]
    complexity_level: str
    code_characteristics: Dict[str, Any]
    processing_recommendations: List[str]


@tool
def analyze_infrastructure_requirements(code: str) -> PlatformAnalysis:
    """
    Analyze infrastructure code to understand what workers are needed.
    
    This tool performs initial analysis to determine:
    - What platforms are present
    - Complexity level and characteristics
    - Optimal processing strategy
    
    Args:
        code: Infrastructure code to analyze
        
    Returns:
        Structured analysis with platform detection and processing recommendations
    """
    
    # Use existing platform detector
    try:
        platform_result = platform_detector.invoke({"files": {"main": code}})
        
        # Extract platform detection results directly (no "success" field needed)
        primary_platform = platform_result.get("primary_platform")
        detected_platforms = platform_result.get("detected_platforms", [])
        confidence_scores = platform_result.get("confidence_scores", {})
        
        # If no platforms detected with confidence, use primary or fallback
        if not detected_platforms:
            if primary_platform:
                detected_platforms = [primary_platform]
            else:
                detected_platforms = ["unknown"]
                confidence_scores = {"unknown": 0.5}
        
        # Assess complexity
        complexity_level = "low"
        if len(code) > 1000:
            complexity_level = "medium" 
        if len(code) > 5000 or len(detected_platforms) > 1:
            complexity_level = "high"
        
        # Analyze code characteristics
        code_characteristics = {
            "total_length": len(code),
            "line_count": len(code.split('\n')),
            "has_multiple_platforms": len(detected_platforms) > 1,
            "contains_templates": "template" in code.lower(),
            "contains_variables": any(pattern in code for pattern in ["${", "{{", "$", "<%="]),
            "appears_modular": any(pattern in code for pattern in ["include", "import", "require"])
        }
        
        # Generate processing recommendations
        processing_recommendations = []
        
        if len(detected_platforms) > 1:
            processing_recommendations.append("Use multiple platform workers in parallel")
        
        if complexity_level == "high":
            processing_recommendations.append("Use detailed analysis with validation")
        
        if code_characteristics["contains_templates"]:
            processing_recommendations.append("Pay special attention to template processing")
        
        return PlatformAnalysis(
            detected_platforms=detected_platforms,
            confidence_scores=confidence_scores,
            complexity_level=complexity_level,
            code_characteristics=code_characteristics,
            processing_recommendations=processing_recommendations
        )
        
    except Exception as e:
        # Fallback on error
        return PlatformAnalysis(
            detected_platforms=["unknown"],
            confidence_scores={"unknown": 0.3},
            complexity_level="medium",
            code_characteristics={"total_length": len(code), "error": str(e)},
            processing_recommendations=["Use generic analysis approach"]
        )
