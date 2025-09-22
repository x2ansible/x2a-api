"""
Complexity Analyzer Tool

Analyzes infrastructure code complexity across different platforms.
Provides standardized complexity metrics that work across Chef, Puppet, Salt, and BladeLogic.
"""

from typing import Dict, Any, List
from langchain_core.tools import tool


@tool
def complexity_analyzer(facts: Dict[str, Any], platform: str) -> Dict[str, Any]:
    """
    Analyze infrastructure complexity from extracted facts.
    
    Provides cross-platform complexity assessment including:
    - Resource complexity scoring
    - Dependency complexity 
    - Template/configuration complexity
    - Maintenance effort estimation
    - Migration difficulty assessment
    
    Args:
        facts: Platform-specific facts extracted by platform tools
        platform: Platform type ("chef", "puppet", "salt", "bladelogic")
        
    Returns:
        Dict with comprehensive complexity analysis
    """
    
    if not facts:
        return {
            "complexity_score": 0,
            "complexity_level": "unknown",
            "analysis_error": "No facts provided"
        }
    
    try:
        if platform == "chef":
            return _analyze_chef_complexity(facts)
        elif platform == "puppet":
            return _analyze_puppet_complexity(facts)
        elif platform == "salt":
            return _analyze_salt_complexity(facts)
        elif platform == "bladelogic":
            return _analyze_bladelogic_complexity(facts)
        else:
            return _analyze_generic_complexity(facts)
            
    except Exception as e:
        return {
            "complexity_score": 0,
            "complexity_level": "error",
            "analysis_error": f"Complexity analysis failed: {str(e)}"
        }


def _analyze_chef_complexity(facts: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze Chef cookbook complexity"""
    
    complexity_score = 0
    factors = {}
    
    # Resource complexity
    if "recipes" in facts:
        total_resources = 0
        for recipe in facts["recipes"]:
            resources = recipe.get("resources", [])
            total_resources += len(resources)
            
            # Complex resource types weight more
            for resource in resources:
                resource_type = resource.get("type", "")
                if resource_type in ["template", "ruby_block", "execute"]:
                    complexity_score += 3
                elif resource_type in ["service", "package"]:
                    complexity_score += 1
                else:
                    complexity_score += 2
                    
                # Notifications and guards add complexity
                complexity_score += len(resource.get("notifies", []))
                complexity_score += len(resource.get("subscribes", []))
                complexity_score += len(resource.get("guards", []))
        
        factors["total_resources"] = total_resources
        factors["resource_complexity"] = complexity_score
    
    # Custom resources add significant complexity
    custom_resources = facts.get("custom_resources", [])
    custom_complexity = len(custom_resources) * 5
    for cr in custom_resources:
        custom_complexity += len(cr.get("properties", [])) * 2
        custom_complexity += len(cr.get("actions", [])) * 3
    
    complexity_score += custom_complexity
    factors["custom_resource_complexity"] = custom_complexity
    
    # Dependency complexity
    dependency_score = 0
    for recipe in facts.get("recipes", []):
        dependency_score += len(recipe.get("includes", [])) * 2
        dependency_score += len(recipe.get("includes_dynamic", [])) * 4  # Dynamic is more complex
    
    complexity_score += dependency_score
    factors["dependency_complexity"] = dependency_score
    
    # Template complexity
    template_score = 0
    for recipe in facts.get("recipes", []):
        for template in recipe.get("templates", []):
            template_score += 2
            template_score += len(template.get("vars", [])) * 1
    
    complexity_score += template_score
    factors["template_complexity"] = template_score
    
    # File count factor
    coverage = facts.get("meta", {}).get("coverage", {})
    file_count = coverage.get("files_scanned", 0)
    file_factor = min(file_count * 2, 20)  # Cap at 20
    complexity_score += file_factor
    factors["file_count_factor"] = file_factor
    
    # Determine complexity level
    if complexity_score <= 20:
        level = "low"
        estimated_hours = 8
        migration_effort = "easy"
    elif complexity_score <= 50:
        level = "medium"
        estimated_hours = 24
        migration_effort = "moderate"
    elif complexity_score <= 100:
        level = "high"
        estimated_hours = 80
        migration_effort = "difficult"
    else:
        level = "very_high"
        estimated_hours = 160
        migration_effort = "very_difficult"
    
    return {
        "complexity_score": complexity_score,
        "complexity_level": level,
        "estimated_maintenance_hours": estimated_hours,
        "migration_effort": migration_effort,
        "complexity_factors": factors,
        "recommendations": _get_complexity_recommendations(level, factors),
        "platform": "chef"
    }


def _analyze_puppet_complexity(facts: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze Puppet manifest complexity (placeholder for future implementation)"""
    
    return {
        "complexity_score": 10,
        "complexity_level": "medium",
        "estimated_maintenance_hours": 24,
        "migration_effort": "moderate",
        "complexity_factors": {"note": "Puppet analysis not yet implemented"},
        "platform": "puppet"
    }


def _analyze_salt_complexity(facts: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze Salt state complexity (placeholder for future implementation)"""
    
    return {
        "complexity_score": 15,
        "complexity_level": "medium",
        "estimated_maintenance_hours": 32,
        "migration_effort": "moderate", 
        "complexity_factors": {"note": "Salt analysis not yet implemented"},
        "platform": "salt"
    }


def _analyze_bladelogic_complexity(facts: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze BladeLogic script complexity (placeholder for future implementation)"""
    
    return {
        "complexity_score": 25,
        "complexity_level": "high",
        "estimated_maintenance_hours": 60,
        "migration_effort": "difficult",
        "complexity_factors": {"note": "BladeLogic analysis not yet implemented"},
        "platform": "bladelogic"
    }


def _analyze_generic_complexity(facts: Dict[str, Any]) -> Dict[str, Any]:
    """Generic complexity analysis for unknown platforms"""
    
    # Basic complexity based on file count and content size
    file_count = len(facts) if isinstance(facts, dict) else 0
    content_size = sum(len(str(v)) for v in facts.values()) if isinstance(facts, dict) else 0
    
    # Simple heuristic scoring
    complexity_score = min(file_count * 3 + content_size // 1000, 100)
    
    if complexity_score <= 20:
        level = "low"
    elif complexity_score <= 50:
        level = "medium"
    else:
        level = "high"
    
    return {
        "complexity_score": complexity_score,
        "complexity_level": level,
        "estimated_maintenance_hours": complexity_score * 2,
        "migration_effort": "unknown",
        "complexity_factors": {
            "file_count": file_count,
            "content_size": content_size
        },
        "platform": "unknown"
    }


def _get_complexity_recommendations(level: str, factors: Dict[str, Any]) -> List[str]:
    """Generate complexity-specific recommendations"""
    
    recommendations = []
    
    if level == "low":
        recommendations.append("Good candidate for automation and reuse")
        recommendations.append("Consider migrating to modern infrastructure tools")
    elif level == "medium":
        recommendations.append("Break down into smaller, focused modules")
        recommendations.append("Document complex dependencies")
        recommendations.append("Consider refactoring before migration")
    elif level in ["high", "very_high"]:
        recommendations.append("High complexity - plan migration carefully")
        recommendations.append("Consider incremental migration strategy")
        recommendations.append("Extensive testing will be required")
        recommendations.append("May benefit from redesign rather than direct migration")
        
        # Specific recommendations based on complexity factors
        if factors.get("custom_resource_complexity", 0) > 20:
            recommendations.append("Complex custom resources may need manual conversion")
        if factors.get("dependency_complexity", 0) > 15:
            recommendations.append("Complex dependencies require careful ordering")
        if factors.get("template_complexity", 0) > 10:
            recommendations.append("Template logic may need manual review")
    
    return recommendations


@tool
def estimate_migration_effort(complexity_analysis: Dict[str, Any], target_platform: str) -> Dict[str, Any]:
    """
    Estimate migration effort to target platform based on complexity.
    
    Args:
        complexity_analysis: Output from complexity_analyzer
        target_platform: Target platform ("ansible", "terraform", etc.)
        
    Returns:
        Dict with migration effort estimation
    """
    
    source_platform = complexity_analysis.get("platform", "unknown")
    complexity_score = complexity_analysis.get("complexity_score", 0)
    complexity_level = complexity_analysis.get("complexity_level", "unknown")
    
    # Base effort from complexity
    base_hours = complexity_analysis.get("estimated_maintenance_hours", 24)
    
    # Platform-specific migration multipliers
    migration_multipliers = {
        ("chef", "ansible"): 1.2,      # Fairly similar
        ("puppet", "ansible"): 1.3,    # Some differences
        ("salt", "ansible"): 1.1,      # Similar YAML structure
        ("bladelogic", "ansible"): 2.0, # Very different
        ("chef", "terraform"): 2.5,    # Different paradigm
        ("puppet", "terraform"): 2.3,
        ("salt", "terraform"): 2.2,
        ("bladelogic", "terraform"): 3.0,
    }
    
    multiplier = migration_multipliers.get((source_platform, target_platform), 1.5)
    estimated_hours = base_hours * multiplier
    
    # Risk factors
    risk_factors = []
    if complexity_level in ["high", "very_high"]:
        risk_factors.append("High complexity increases migration risk")
    if source_platform == "bladelogic":
        risk_factors.append("BladeLogic migration requires significant manual work")
    if target_platform == "terraform" and source_platform in ["chef", "puppet"]:
        risk_factors.append("Configuration management to infrastructure paradigm shift")
    
    return {
        "source_platform": source_platform,
        "target_platform": target_platform,
        "estimated_migration_hours": estimated_hours,
        "migration_complexity": complexity_level,
        "migration_multiplier": multiplier,
        "risk_factors": risk_factors,
        "confidence": "medium" if source_platform != "unknown" else "low"
    }
