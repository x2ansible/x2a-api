#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Complexity Analysis Tool

Focused tool for calculating infrastructure complexity scores and levels.
Analyzes components, dependencies, code size, patterns, and resource utilization
to provide comprehensive complexity assessment.
"""

from langchain_core.tools import tool


@tool
def calculate_infrastructure_complexity(
    extracted_facts: dict, 
    input_code: str, 
    platform_analysis: dict
) -> dict:
    """
    Calculate comprehensive infrastructure complexity score and level.
    
    Analyzes multiple factors including components, dependencies, code size,
    patterns, and resource utilization to determine complexity score and level.
    
    Args:
        extracted_facts: Dictionary of extracted infrastructure facts
        input_code: Original infrastructure code
        platform_analysis: Results from platform-specific analysis
        
    Returns:
        Dictionary with complexity score, level, and breakdown
    """
    try:
        # Handle string inputs from LLM agents (fix for Pydantic validation error)
        import json
        
        # Parse extracted_facts if it's a string
        if isinstance(extracted_facts, str):
            try:
                extracted_facts = json.loads(extracted_facts) if extracted_facts.strip() else {}
            except (json.JSONDecodeError, AttributeError):
                extracted_facts = {}
        elif not isinstance(extracted_facts, dict):
            extracted_facts = {}
            
        # Parse platform_analysis if it's a string  
        if isinstance(platform_analysis, str):
            try:
                platform_analysis = json.loads(platform_analysis) if platform_analysis.strip() else {}
            except (json.JSONDecodeError, AttributeError):
                platform_analysis = {}
        elif not isinstance(platform_analysis, dict):
            platform_analysis = {}
        
        score = 0
        breakdown = {}
        
        # Component complexity
        components = platform_analysis.get("components", [])
        component_score = len(components) * 2
        score += component_score
        breakdown["components"] = {
            "count": len(components),
            "score": component_score,
            "description": "2 points per component"
        }
        
        # Dependency complexity
        dependencies = platform_analysis.get("dependencies", [])
        dependency_score = len(dependencies) * 3
        score += dependency_score
        breakdown["dependencies"] = {
            "count": len(dependencies),
            "score": dependency_score,
            "description": "3 points per dependency"
        }
        
        # Code size complexity
        code_size_score = 0
        if input_code:
            lines = len([line for line in input_code.split('\n') if line.strip()])
            code_size_score = min(lines // 10, 20)  # Cap at 20 points
            score += code_size_score
            breakdown["code_size"] = {
                "lines": lines,
                "score": code_size_score,
                "description": "1 point per 10 lines (capped at 20)"
            }
        
        # Pattern complexity
        patterns = platform_analysis.get("infrastructure_patterns", [])
        pattern_score = len(patterns) * 5
        score += pattern_score
        breakdown["patterns"] = {
            "count": len(patterns),
            "patterns": patterns,
            "score": pattern_score,
            "description": "5 points per pattern"
        }
        
        # Resource utilization complexity
        resource_util = platform_analysis.get("resource_utilization", {})
        total_resources = resource_util.get("total_resources", 0)
        resource_score = min(total_resources, 30)  # Cap at 30 points
        score += resource_score
        breakdown["resource_utilization"] = {
            "total_resources": total_resources,
            "score": resource_score,
            "description": "1 point per resource (capped at 30)"
        }
        
        # Platform-specific complexity adjustments
        platform = platform_analysis.get("platform", "unknown")
        platform_score = 0
        if platform == "chef":
            # Chef-specific complexity factors
            template_count = resource_util.get("template_count", 0)
            attribute_count = resource_util.get("attribute_count", 0)
            platform_score = (template_count * 2) + (attribute_count * 1)
        elif platform == "terraform":
            # Terraform-specific complexity factors
            terraform_modules = resource_util.get("terraform_modules", 0)
            platform_score = terraform_modules * 3
        elif platform == "puppet":
            # Puppet-specific complexity factors
            puppet_classes = resource_util.get("puppet_classes", 0)
            platform_score = puppet_classes * 2
        
        score += platform_score
        breakdown["platform_specific"] = {
            "platform": platform,
            "score": platform_score,
            "description": f"{platform.title()}-specific complexity factors"
        }
        
        # Determine complexity level
        if score < 15:
            level = "low"
            level_description = "Simple infrastructure with minimal complexity"
        elif score < 40:
            level = "medium"
            level_description = "Moderate infrastructure complexity requiring careful management"
        else:
            level = "high"
            level_description = "Complex infrastructure requiring expert management and monitoring"
        
        return {
            "success": True,
            "complexity": {
                "score": score,
                "level": level,
                "description": level_description,
                "breakdown": breakdown,
                "recommendations": _get_complexity_recommendations(level, score, breakdown)
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def _get_complexity_recommendations(level: str, score: int, breakdown: dict) -> list:
    """Generate recommendations based on complexity analysis"""
    recommendations = []
    
    if level == "low":
        recommendations.extend([
            "Infrastructure is manageable with current complexity",
            "Consider establishing monitoring and documentation standards",
            "Good candidate for automation and CI/CD implementation"
        ])
    elif level == "medium":
        recommendations.extend([
            "Implement comprehensive documentation and runbooks",
            "Consider modular design patterns to manage complexity",
            "Establish robust testing and validation procedures"
        ])
    else:  # high
        recommendations.extend([
            "Critical: Implement complexity reduction strategies",
            "Break down monolithic infrastructure into smaller modules",
            "Establish comprehensive monitoring and alerting",
            "Implement progressive deployment strategies",
            "Consider infrastructure refactoring initiative"
        ])
    
    # Specific recommendations based on breakdown
    if breakdown.get("dependencies", {}).get("count", 0) > 10:
        recommendations.append("High dependency count: Review and optimize dependency relationships")
    
    if breakdown.get("code_size", {}).get("lines", 0) > 200:
        recommendations.append("Large codebase: Consider splitting into smaller, manageable components")
    
    if breakdown.get("patterns", {}).get("count", 0) > 5:
        recommendations.append("Multiple patterns detected: Ensure consistent implementation across infrastructure")
    
    return recommendations
