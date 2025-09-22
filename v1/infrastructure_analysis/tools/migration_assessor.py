"""
Migration Assessor Tool

Provides migration strategy and assessment capabilities for infrastructure code.
Analyzes migration feasibility, effort, and provides specific migration plans.
"""

from typing import Dict, Any, List, Optional
from langchain_core.tools import tool


@tool
def migration_assessor(
    facts: Dict[str, Any], 
    complexity_analysis: Dict[str, Any],
    target_platform: str = "ansible"
) -> Dict[str, Any]:
    """
    Assess migration strategy and feasibility for infrastructure code.
    
    Provides detailed migration analysis including:
    - Migration feasibility assessment
    - Step-by-step migration plan
    - Risk analysis and mitigation strategies
    - Resource mapping between platforms
    - Timeline and effort estimates
    
    Args:
        facts: Platform-specific facts extracted by platform tools
        complexity_analysis: Output from complexity_analyzer tool
        target_platform: Target platform for migration (default: "ansible")
        
    Returns:
        Dict with comprehensive migration assessment
    """
    
    source_platform = complexity_analysis.get("platform", "unknown")
    
    if source_platform == "unknown" or not facts:
        return {
            "feasibility": "unknown",
            "migration_plan": [],
            "risk_assessment": "Cannot assess without platform facts",
            "estimated_effort": "unknown"
        }
    
    try:
        return _create_migration_assessment(
            facts, complexity_analysis, source_platform, target_platform
        )
    except Exception as e:
        return {
            "feasibility": "error",
            "migration_plan": [],
            "risk_assessment": f"Migration assessment failed: {str(e)}",
            "estimated_effort": "unknown"
        }


def _create_migration_assessment(
    facts: Dict[str, Any],
    complexity_analysis: Dict[str, Any], 
    source_platform: str,
    target_platform: str
) -> Dict[str, Any]:
    """Create comprehensive migration assessment"""
    
    # Assess feasibility
    feasibility = _assess_migration_feasibility(facts, source_platform, target_platform)
    
    # Create migration plan
    migration_plan = _create_migration_plan(facts, source_platform, target_platform)
    
    # Risk assessment
    risk_assessment = _assess_migration_risks(facts, complexity_analysis, source_platform, target_platform)
    
    # Resource mapping
    resource_mapping = _create_resource_mapping(facts, source_platform, target_platform)
    
    # Effort estimation
    effort_estimation = _estimate_migration_effort(complexity_analysis, source_platform, target_platform)
    
    # Migration strategy
    strategy = _recommend_migration_strategy(complexity_analysis, feasibility)
    
    return {
        "source_platform": source_platform,
        "target_platform": target_platform,
        "feasibility": feasibility["overall"],
        "feasibility_details": feasibility,
        "migration_strategy": strategy,
        "migration_plan": migration_plan,
        "risk_assessment": risk_assessment,
        "resource_mapping": resource_mapping,
        "effort_estimation": effort_estimation,
        "recommendations": _get_migration_recommendations(
            feasibility, complexity_analysis, source_platform, target_platform
        )
    }


def _assess_migration_feasibility(
    facts: Dict[str, Any], 
    source_platform: str, 
    target_platform: str
) -> Dict[str, Any]:
    """Assess how feasible the migration is"""
    
    feasibility_scores = {}
    overall_feasible = True
    blockers = []
    
    if source_platform == "chef" and target_platform == "ansible":
        # Chef to Ansible is generally feasible
        feasibility_scores["resource_compatibility"] = 0.9
        feasibility_scores["template_conversion"] = 0.8
        feasibility_scores["dependency_management"] = 0.7
        
        # Check for complex custom resources
        custom_resources = facts.get("custom_resources", [])
        if len(custom_resources) > 5:
            feasibility_scores["custom_resources"] = 0.4
            blockers.append("Many custom resources may require manual conversion")
        else:
            feasibility_scores["custom_resources"] = 0.8
            
    elif source_platform == "puppet" and target_platform == "ansible":
        feasibility_scores["resource_compatibility"] = 0.8
        feasibility_scores["template_conversion"] = 0.7
        feasibility_scores["dependency_management"] = 0.6
        feasibility_scores["custom_resources"] = 0.6
        
    elif source_platform == "salt" and target_platform == "ansible":
        feasibility_scores["resource_compatibility"] = 0.9
        feasibility_scores["template_conversion"] = 0.8
        feasibility_scores["dependency_management"] = 0.8
        feasibility_scores["custom_resources"] = 0.7
        
    elif source_platform == "bladelogic":
        feasibility_scores["resource_compatibility"] = 0.3
        feasibility_scores["template_conversion"] = 0.2
        feasibility_scores["dependency_management"] = 0.4
        feasibility_scores["custom_resources"] = 0.2
        blockers.append("BladeLogic requires significant manual conversion")
        overall_feasible = False
        
    else:
        # Unknown combinations
        feasibility_scores["resource_compatibility"] = 0.5
        feasibility_scores["template_conversion"] = 0.5
        feasibility_scores["dependency_management"] = 0.5
        feasibility_scores["custom_resources"] = 0.5
        blockers.append("Unfamiliar platform combination")
    
    # Calculate overall feasibility
    avg_score = sum(feasibility_scores.values()) / len(feasibility_scores)
    
    if avg_score >= 0.7:
        overall = "high"
    elif avg_score >= 0.5:
        overall = "medium"
    else:
        overall = "low"
        overall_feasible = False
    
    return {
        "overall": overall,
        "score": avg_score,
        "feasible": overall_feasible,
        "component_scores": feasibility_scores,
        "blockers": blockers
    }


def _create_migration_plan(
    facts: Dict[str, Any], 
    source_platform: str, 
    target_platform: str
) -> List[Dict[str, Any]]:
    """Create step-by-step migration plan"""
    
    plan = []
    
    if source_platform == "chef" and target_platform == "ansible":
        plan = [
            {
                "phase": "preparation",
                "title": "Migration Preparation",
                "steps": [
                    "Analyze cookbook dependencies and execution order",
                    "Document current Chef cookbook functionality",
                    "Set up Ansible development environment",
                    "Plan testing strategy for converted playbooks"
                ],
                "estimated_time": "1-2 days"
            },
            {
                "phase": "conversion",
                "title": "Core Conversion",
                "steps": [
                    "Convert Chef resources to Ansible modules",
                    "Transform ERB templates to Jinja2 templates", 
                    "Map Chef attributes to Ansible variables",
                    "Convert Chef guards to Ansible conditionals"
                ],
                "estimated_time": "3-5 days"
            },
            {
                "phase": "dependencies",
                "title": "Dependency Management", 
                "steps": [
                    "Replace cookbook dependencies with Ansible roles",
                    "Convert include_recipe to include/import tasks",
                    "Handle dynamic includes and complex dependencies",
                    "Set up Ansible Galaxy or custom role structure"
                ],
                "estimated_time": "1-3 days"
            },
            {
                "phase": "testing",
                "title": "Testing & Validation",
                "steps": [
                    "Test individual converted playbooks",
                    "Validate template rendering with test data",
                    "Test playbook execution order and dependencies",
                    "Compare results with original Chef runs"
                ],
                "estimated_time": "2-4 days"
            },
            {
                "phase": "optimization",
                "title": "Optimization & Documentation",
                "steps": [
                    "Optimize playbook structure and performance",
                    "Document migration decisions and configurations", 
                    "Create deployment and maintenance procedures",
                    "Train team on new Ansible playbooks"
                ],
                "estimated_time": "1-2 days"
            }
        ]
    
    else:
        # Generic migration plan
        plan = [
            {
                "phase": "analysis",
                "title": "Infrastructure Analysis",
                "steps": [
                    f"Analyze {source_platform} infrastructure code",
                    f"Map {source_platform} concepts to {target_platform}",
                    "Identify migration challenges and blockers",
                    "Plan migration strategy and timeline"
                ],
                "estimated_time": "1-2 days"
            },
            {
                "phase": "conversion",
                "title": "Code Conversion",
                "steps": [
                    f"Convert {source_platform} resources to {target_platform}",
                    "Transform templates and configuration files",
                    "Handle platform-specific features and syntax",
                    "Test basic functionality of converted code"
                ],
                "estimated_time": "3-7 days"
            },
            {
                "phase": "validation",
                "title": "Testing & Validation",
                "steps": [
                    "Test converted infrastructure code",
                    "Validate functionality matches original",
                    "Performance testing and optimization",
                    "Documentation and knowledge transfer"
                ],
                "estimated_time": "2-4 days"
            }
        ]
    
    return plan


def _assess_migration_risks(
    facts: Dict[str, Any],
    complexity_analysis: Dict[str, Any],
    source_platform: str,
    target_platform: str
) -> Dict[str, Any]:
    """Assess migration risks and provide mitigation strategies"""
    
    risks = []
    mitigation_strategies = []
    
    complexity_level = complexity_analysis.get("complexity_level", "medium")
    
    # Complexity-based risks
    if complexity_level in ["high", "very_high"]:
        risks.append({
            "category": "complexity",
            "level": "high",
            "description": "High complexity increases migration risk and effort",
            "impact": "Extended timeline, potential for errors"
        })
        mitigation_strategies.append("Break migration into smaller phases")
        mitigation_strategies.append("Extensive testing at each phase")
    
    # Platform-specific risks
    if source_platform == "chef":
        # Check for complex Chef features
        custom_resources = facts.get("custom_resources", [])
        if custom_resources:
            risks.append({
                "category": "custom_resources",
                "level": "medium",
                "description": f"{len(custom_resources)} custom resources require manual conversion",
                "impact": "Manual work, potential for missed functionality"
            })
            mitigation_strategies.append("Manually review and test each custom resource conversion")
        
        # Check for dynamic includes
        dynamic_includes = 0
        for recipe in facts.get("recipes", []):
            dynamic_includes += len(recipe.get("includes_dynamic", []))
        
        if dynamic_includes > 0:
            risks.append({
                "category": "dynamic_dependencies",
                "level": "medium", 
                "description": f"{dynamic_includes} dynamic include_recipe calls",
                "impact": "Runtime dependencies may not be captured correctly"
            })
            mitigation_strategies.append("Review dynamic includes and convert to static where possible")
    
    # Target platform risks
    if target_platform == "terraform":
        risks.append({
            "category": "paradigm_shift",
            "level": "high",
            "description": "Configuration management to infrastructure as code paradigm shift",
            "impact": "Fundamental architectural changes required"
        })
        mitigation_strategies.append("Consider using Terraform + Ansible combination")
        mitigation_strategies.append("Plan for infrastructure vs configuration separation")
    
    return {
        "risk_level": "high" if any(r["level"] == "high" for r in risks) else "medium",
        "risks": risks,
        "mitigation_strategies": mitigation_strategies,
        "confidence": "medium"
    }


def _create_resource_mapping(
    facts: Dict[str, Any], 
    source_platform: str, 
    target_platform: str
) -> Dict[str, Any]:
    """Create mapping between source and target platform resources"""
    
    mappings = {}
    
    if source_platform == "chef" and target_platform == "ansible":
        mappings = {
            "package": {"ansible_module": "package", "compatibility": "high"},
            "service": {"ansible_module": "service", "compatibility": "high"},
            "template": {"ansible_module": "template", "compatibility": "medium", "notes": "ERB to Jinja2 conversion required"},
            "file": {"ansible_module": "copy", "compatibility": "high"},
            "directory": {"ansible_module": "file", "compatibility": "high"},
            "user": {"ansible_module": "user", "compatibility": "high"},
            "group": {"ansible_module": "group", "compatibility": "high"},
            "execute": {"ansible_module": "command/shell", "compatibility": "medium", "notes": "Review for idempotency"},
            "ruby_block": {"ansible_module": "N/A", "compatibility": "low", "notes": "Requires manual conversion"},
            "bash": {"ansible_module": "shell", "compatibility": "medium"}
        }
    
    return {
        "source_platform": source_platform,
        "target_platform": target_platform,
        "resource_mappings": mappings,
        "mapping_confidence": "high" if source_platform == "chef" and target_platform == "ansible" else "medium"
    }


def _estimate_migration_effort(
    complexity_analysis: Dict[str, Any],
    source_platform: str,
    target_platform: str
) -> Dict[str, Any]:
    """Estimate migration effort in hours and timeline"""
    
    base_hours = complexity_analysis.get("estimated_maintenance_hours", 24)
    complexity_level = complexity_analysis.get("complexity_level", "medium")
    
    # Migration multipliers based on platform combination
    multipliers = {
        ("chef", "ansible"): 1.2,
        ("puppet", "ansible"): 1.4,
        ("salt", "ansible"): 1.1,
        ("bladelogic", "ansible"): 2.5,
        ("chef", "terraform"): 2.0,
        ("puppet", "terraform"): 2.2,
        ("salt", "terraform"): 1.8
    }
    
    multiplier = multipliers.get((source_platform, target_platform), 1.5)
    estimated_hours = base_hours * multiplier
    
    # Add complexity buffer
    if complexity_level == "high":
        estimated_hours *= 1.3
    elif complexity_level == "very_high":
        estimated_hours *= 1.6
    
    # Convert to timeline estimate
    if estimated_hours <= 40:
        timeline = "1 week"
    elif estimated_hours <= 80:
        timeline = "2 weeks"
    elif estimated_hours <= 160:
        timeline = "1 month"
    else:
        timeline = "2+ months"
    
    return {
        "estimated_hours": round(estimated_hours),
        "base_hours": base_hours,
        "migration_multiplier": multiplier,
        "complexity_factor": complexity_level,
        "timeline_estimate": timeline,
        "confidence": "medium"
    }


def _recommend_migration_strategy(
    complexity_analysis: Dict[str, Any],
    feasibility: Dict[str, Any]
) -> Dict[str, Any]:
    """Recommend migration strategy based on complexity and feasibility"""
    
    complexity_level = complexity_analysis.get("complexity_level", "medium")
    feasibility_level = feasibility.get("overall", "medium")
    
    if feasibility_level == "high" and complexity_level in ["low", "medium"]:
        strategy = {
            "approach": "direct_migration",
            "description": "Direct conversion with minimal refactoring",
            "phases": ["analyze", "convert", "test", "deploy"],
            "parallel_work": True
        }
    elif feasibility_level == "medium" or complexity_level == "high":
        strategy = {
            "approach": "phased_migration", 
            "description": "Incremental migration in phases with validation",
            "phases": ["analyze", "pilot_conversion", "iterative_conversion", "validation", "deployment"],
            "parallel_work": False
        }
    else:
        strategy = {
            "approach": "redesign_migration",
            "description": "Significant redesign required due to complexity or platform differences",
            "phases": ["analyze", "redesign", "implement", "extensive_testing", "phased_deployment"],
            "parallel_work": False
        }
    
    return strategy


def _get_migration_recommendations(
    feasibility: Dict[str, Any],
    complexity_analysis: Dict[str, Any],
    source_platform: str,
    target_platform: str
) -> List[str]:
    """Generate specific migration recommendations"""
    
    recommendations = []
    
    feasibility_level = feasibility.get("overall", "medium")
    complexity_level = complexity_analysis.get("complexity_level", "medium")
    
    if feasibility_level == "high":
        recommendations.append("Migration is highly feasible - proceed with confidence")
        recommendations.append("Consider automated conversion tools where available")
    elif feasibility_level == "medium":
        recommendations.append("Migration feasible with careful planning")
        recommendations.append("Complex components may require additional planning")
    else:
        recommendations.append("Migration challenging - consider alternatives")
        recommendations.append("Extensive manual work required")
    
    if complexity_level in ["high", "very_high"]:
        recommendations.append("High complexity - plan for extended timeline")
        recommendations.append("Consider incremental migration approach")
        recommendations.append("Invest in comprehensive testing strategy")
    
    # Platform-specific recommendations
    if source_platform == "chef" and target_platform == "ansible":
        recommendations.append("Chef to Ansible migration is well-supported")
        recommendations.append("Focus on ERB to Jinja2 template conversion")
        recommendations.append("Map Chef attributes to Ansible variables systematically")
    elif source_platform == "bladelogic":
        recommendations.append("BladeLogic migration requires significant manual effort")
        recommendations.append("Consider modernizing approach rather than direct conversion")
    
    return recommendations
