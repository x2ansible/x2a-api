#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Migration Analysis Tool

Focused tool for generating migration recommendations and strategies
for infrastructure modernization. Analyzes current platform, complexity,
and patterns to provide actionable migration guidance.
"""

from langchain_core.tools import tool


@tool
def generate_migration_recommendations(
    platform: str,
    platform_analysis: dict,
    complexity_analysis: dict,
    security_analysis: dict = None
) -> dict:
    """
    Generate comprehensive migration recommendations for infrastructure.
    
    Analyzes current platform, complexity, security considerations, and patterns
    to provide strategic migration recommendations and modernization pathways.
    
    Args:
        platform: Current platform type (chef, puppet, terraform, etc.)
        platform_analysis: Results from platform-specific analysis
        complexity_analysis: Results from complexity analysis
        security_analysis: Optional security analysis results
        
    Returns:
        Dictionary with migration recommendations and strategies
    """
    try:
        recommendations = []
        migration_strategies = {}
        priority_levels = {"high": [], "medium": [], "low": []}
        
        complexity_level = complexity_analysis.get("complexity", {}).get("level", "low")
        components = platform_analysis.get("components", [])
        patterns = platform_analysis.get("infrastructure_patterns", [])
        
        # Platform-specific migration recommendations
        if platform == "chef":
            chef_migration = _analyze_chef_migration(platform_analysis, complexity_level, patterns)
            recommendations.extend(chef_migration["recommendations"])
            migration_strategies["chef_specific"] = chef_migration
            
        elif platform == "puppet":
            puppet_migration = _analyze_puppet_migration(platform_analysis, complexity_level, patterns)
            recommendations.extend(puppet_migration["recommendations"])
            migration_strategies["puppet_specific"] = puppet_migration
            
        elif platform == "terraform":
            terraform_migration = _analyze_terraform_migration(platform_analysis, complexity_level, patterns)
            recommendations.extend(terraform_migration["recommendations"])
            migration_strategies["terraform_specific"] = terraform_migration
            
        else:
            generic_migration = _analyze_generic_migration(platform_analysis, complexity_level, patterns)
            recommendations.extend(generic_migration["recommendations"])
            migration_strategies["generic"] = generic_migration
        
        # Complexity-based migration recommendations
        complexity_migration = _analyze_complexity_migration(complexity_analysis)
        recommendations.extend(complexity_migration["recommendations"])
        migration_strategies["complexity_based"] = complexity_migration
        
        # Security-informed migration recommendations
        if security_analysis:
            security_migration = _analyze_security_migration(security_analysis)
            recommendations.extend(security_migration["recommendations"])
            migration_strategies["security_informed"] = security_migration
        
        # Modernization pathway recommendations
        modernization = _generate_modernization_pathway(platform, complexity_level, patterns)
        migration_strategies["modernization_pathway"] = modernization
        recommendations.extend(modernization["recommendations"])
        
        # Prioritize recommendations
        priority_levels = _prioritize_migration_recommendations(
            recommendations, complexity_level, platform, security_analysis
        )
        
        return {
            "success": True,
            "migration_analysis": {
                "current_platform": platform,
                "complexity_level": complexity_level,
                "total_recommendations": len(recommendations),
                "recommendations": recommendations,
                "migration_strategies": migration_strategies,
                "priority_levels": priority_levels,
                "implementation_roadmap": _create_implementation_roadmap(priority_levels, complexity_level)
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def _analyze_chef_migration(platform_analysis: dict, complexity_level: str, patterns: list) -> dict:
    """Analyze Chef-specific migration recommendations"""
    recommendations = [
        "Consider migrating to containerized infrastructure using Docker/Kubernetes",
        "Evaluate Infrastructure as Code alternatives (Terraform, Pulumi, CDK)",
        "Implement GitOps workflows for configuration management"
    ]
    
    # Pattern-specific recommendations
    if "template_driven_configuration" in patterns:
        recommendations.append("Migrate template logic to Helm charts or Kustomize for Kubernetes")
    if "multi_resource_orchestration" in patterns:
        recommendations.append("Consider service mesh patterns for complex resource orchestration")
    if "attribute_parameterization" in patterns:
        recommendations.append("Migrate Chef attributes to cloud-native configuration management")
    
    # Resource-based recommendations
    resource_util = platform_analysis.get("resource_utilization", {})
    template_count = resource_util.get("template_count", 0)
    if template_count > 5:
        recommendations.append("High template usage: Consider templating engines like Jsonnet or Helm")
    
    migration_paths = [
        {
            "target": "Kubernetes + Helm",
            "effort": "medium" if complexity_level == "low" else "high",
            "benefits": ["Cloud-native deployment", "Better scalability", "Modern tooling"]
        },
        {
            "target": "Terraform + Cloud Services",
            "effort": "medium",
            "benefits": ["Infrastructure as Code", "Cloud provider integration", "Better state management"]
        }
    ]
    
    return {
        "recommendations": recommendations,
        "migration_paths": migration_paths,
        "focus_areas": ["containerization", "infrastructure_as_code", "gitops", "cloud_native"]
    }


def _analyze_puppet_migration(platform_analysis: dict, complexity_level: str, patterns: list) -> dict:
    """Analyze Puppet-specific migration recommendations"""
    recommendations = [
        "Consider migration to cloud-native configuration management",
        "Evaluate Kubernetes operators for stateful applications",
        "Implement declarative infrastructure using modern IaC tools"
    ]
    
    # Pattern-specific recommendations
    if "class_based_organization" in patterns:
        recommendations.append("Migrate Puppet classes to Kubernetes Custom Resources")
    if "modular_puppet_design" in patterns:
        recommendations.append("Convert Puppet modules to Helm charts or Terraform modules")
    
    migration_paths = [
        {
            "target": "Kubernetes Operators",
            "effort": "high",
            "benefits": ["Native Kubernetes integration", "Automated operations", "Cloud-native patterns"]
        },
        {
            "target": "Ansible + Terraform",
            "effort": "medium",
            "benefits": ["Simpler syntax", "Better cloud integration", "Agentless operations"]
        }
    ]
    
    return {
        "recommendations": recommendations,
        "migration_paths": migration_paths,
        "focus_areas": ["kubernetes_operators", "declarative_config", "cloud_native", "agentless"]
    }


def _analyze_terraform_migration(platform_analysis: dict, complexity_level: str, patterns: list) -> dict:
    """Analyze Terraform-specific migration recommendations"""
    recommendations = [
        "Consider upgrading to latest Terraform version for improved features",
        "Implement Terraform Cloud or Enterprise for team collaboration",
        "Evaluate CDK (Cloud Development Kit) for programmatic infrastructure"
    ]
    
    # Pattern-specific recommendations
    if "modular_terraform_design" in patterns:
        recommendations.append("Enhance module reusability and versioning strategies")
    if "parameterized_configuration" in patterns:
        recommendations.append("Implement advanced variable validation and workspace management")
    
    resource_util = platform_analysis.get("resource_utilization", {})
    resource_count = resource_util.get("terraform_resources", 0)
    if resource_count > 20:
        recommendations.append("Large resource count: Consider state splitting and module decomposition")
    
    migration_paths = [
        {
            "target": "Terraform Cloud/Enterprise",
            "effort": "low",
            "benefits": ["Team collaboration", "Remote state", "Policy as Code"]
        },
        {
            "target": "CDK (TypeScript/Python)",
            "effort": "medium",
            "benefits": ["Programmatic infrastructure", "Type safety", "IDE support"]
        }
    ]
    
    return {
        "recommendations": recommendations,
        "migration_paths": migration_paths,
        "focus_areas": ["version_upgrade", "team_collaboration", "programmatic_iac", "state_management"]
    }


def _analyze_generic_migration(platform_analysis: dict, complexity_level: str, patterns: list) -> dict:
    """Analyze generic infrastructure migration recommendations"""
    recommendations = [
        "Standardize on Infrastructure as Code practices",
        "Implement automated testing and validation",
        "Consider cloud-native deployment patterns",
        "Establish DevOps and GitOps workflows"
    ]
    
    # Pattern-based recommendations
    if "modular_design" in patterns:
        recommendations.append("Enhance modularity with modern IaC frameworks")
    if "template_usage" in patterns:
        recommendations.append("Modernize templating with cloud-native solutions")
    
    migration_paths = [
        {
            "target": "Terraform + CI/CD",
            "effort": "medium",
            "benefits": ["Standardized IaC", "Version control", "Automated deployment"]
        },
        {
            "target": "Cloud-Native Platform",
            "effort": "high",
            "benefits": ["Managed services", "Scalability", "Reduced operational overhead"]
        }
    ]
    
    return {
        "recommendations": recommendations,
        "migration_paths": migration_paths,
        "focus_areas": ["standardization", "automation", "cloud_native", "devops"]
    }


def _analyze_complexity_migration(complexity_analysis: dict) -> dict:
    """Analyze migration recommendations based on complexity"""
    recommendations = []
    complexity_info = complexity_analysis.get("complexity", {})
    complexity_level = complexity_info.get("level", "low")
    
    if complexity_level == "high":
        recommendations.extend([
            "Break down monolithic infrastructure into smaller, manageable modules",
            "Implement progressive migration strategy with phased approach",
            "Add comprehensive monitoring and observability during migration",
            "Consider hiring migration specialists or consulting services",
            "Implement extensive testing and rollback procedures"
        ])
    elif complexity_level == "medium":
        recommendations.extend([
            "Plan structured migration with clear milestones",
            "Implement proper testing and validation at each stage",
            "Consider parallel deployment patterns during migration"
        ])
    else:  # low
        recommendations.append("Infrastructure complexity is suitable for direct migration approaches")
    
    return {
        "recommendations": recommendations,
        "focus_areas": ["complexity_management", "phased_approach", "testing", "monitoring"]
    }


def _analyze_security_migration(security_analysis: dict) -> dict:
    """Analyze migration recommendations based on security considerations"""
    recommendations = []
    security_info = security_analysis.get("security_analysis", {})
    risk_level = security_info.get("risk_level", "low")
    
    if risk_level == "high":
        recommendations.extend([
            "Prioritize security improvements during migration",
            "Implement security-first migration strategy",
            "Conduct security assessment before and after migration"
        ])
    
    recommendations.extend([
        "Ensure security controls are maintained during migration",
        "Implement security scanning for target infrastructure",
        "Update security documentation and procedures"
    ])
    
    return {
        "recommendations": recommendations,
        "focus_areas": ["security_first", "compliance", "risk_management"]
    }


def _generate_modernization_pathway(platform: str, complexity_level: str, patterns: list) -> dict:
    """Generate modernization pathway recommendations"""
    recommendations = [
        "Adopt cloud-native principles and patterns",
        "Implement observability and monitoring solutions",
        "Establish automated testing and CI/CD pipelines",
        "Consider microservices and containerization strategies"
    ]
    
    if complexity_level == "high":
        recommendations.extend([
            "Implement gradual modernization with strangler fig pattern",
            "Establish service mesh for complex service interactions"
        ])
    
    modernization_stages = [
        {
            "stage": "Foundation",
            "activities": ["Version control", "Basic CI/CD", "Infrastructure as Code"],
            "duration": "2-4 weeks"
        },
        {
            "stage": "Containerization",
            "activities": ["Docker adoption", "Container registry", "Basic orchestration"],
            "duration": "4-8 weeks"
        },
        {
            "stage": "Cloud-Native",
            "activities": ["Kubernetes deployment", "Service mesh", "Observability"],
            "duration": "8-16 weeks"
        }
    ]
    
    return {
        "recommendations": recommendations,
        "modernization_stages": modernization_stages,
        "focus_areas": ["cloud_native", "containerization", "observability", "automation"]
    }


def _prioritize_migration_recommendations(
    recommendations: list, 
    complexity_level: str, 
    platform: str, 
    security_analysis: dict = None
) -> dict:
    """Prioritize migration recommendations based on various factors"""
    high_priority = []
    medium_priority = []
    low_priority = []
    
    # Categorize based on complexity
    if complexity_level == "high":
        high_priority.extend([
            "Break down monolithic infrastructure into manageable modules",
            "Implement comprehensive monitoring and observability"
        ])
    
    # Security-based prioritization
    if security_analysis:
        risk_level = security_analysis.get("security_analysis", {}).get("risk_level", "low")
        if risk_level == "high":
            high_priority.append("Address security vulnerabilities during migration")
    
    # Platform-specific prioritization
    platform_priorities = {
        "chef": ["Containerization strategy", "GitOps implementation"],
        "puppet": ["Cloud-native migration", "Kubernetes operators"],
        "terraform": ["Version upgrade", "State management improvement"]
    }
    
    if platform in platform_priorities:
        medium_priority.extend(platform_priorities[platform])
    
    # General recommendations go to low priority
    low_priority.extend([
        "Establish documentation and training",
        "Implement monitoring and alerting",
        "Plan rollback and disaster recovery procedures"
    ])
    
    return {
        "high": high_priority,
        "medium": medium_priority,
        "low": low_priority
    }


def _create_implementation_roadmap(priority_levels: dict, complexity_level: str) -> list:
    """Create implementation roadmap based on priorities and complexity"""
    roadmap = []
    
    # Phase 1: High Priority Items
    if priority_levels["high"]:
        roadmap.append({
            "phase": "Phase 1 - Critical Foundation",
            "duration": "2-4 weeks" if complexity_level == "low" else "4-8 weeks",
            "items": priority_levels["high"],
            "success_criteria": "Critical infrastructure components migrated successfully"
        })
    
    # Phase 2: Medium Priority Items
    if priority_levels["medium"]:
        roadmap.append({
            "phase": "Phase 2 - Core Migration",
            "duration": "4-8 weeks" if complexity_level == "low" else "8-16 weeks",
            "items": priority_levels["medium"],
            "success_criteria": "Main migration objectives achieved"
        })
    
    # Phase 3: Low Priority Items
    if priority_levels["low"]:
        roadmap.append({
            "phase": "Phase 3 - Optimization & Documentation",
            "duration": "2-4 weeks",
            "items": priority_levels["low"],
            "success_criteria": "Migration fully documented and optimized"
        })
    
    return roadmap
