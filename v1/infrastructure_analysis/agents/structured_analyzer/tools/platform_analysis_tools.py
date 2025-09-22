#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Platform Analysis Tools

Focused tools for analyzing different infrastructure platforms.
Each tool specializes in a specific platform (Chef, Puppet, Terraform, etc.)
allowing the agent to choose the appropriate analysis method.
"""

from langchain_core.tools import tool


@tool
def analyze_chef_infrastructure(extracted_facts: dict, input_code: str) -> dict:
    """
    Analyze Chef-specific infrastructure facts.
    
    Specializes in analyzing Chef cookbooks, recipes, resources, and templates
    to extract components, dependencies, and platform-specific patterns.
    
    Args:
        extracted_facts: Chef-specific extracted facts
        input_code: Original Chef code for additional analysis
        
    Returns:
        Dictionary with Chef analysis results
    """
    try:
        components = []
        dependencies = []
        patterns = []
        
        # Extract resources from Chef facts
        resources = extracted_facts.get("resources", {})
        for resource_type, resource_list in resources.items():
            for resource in resource_list:
                components.append({
                    "type": f"chef_{resource_type}",
                    "name": resource.get("name", "unnamed"),
                    "actions": resource.get("actions", []),
                    "properties": len(resource.get("properties", {}))
                })
        
        # Extract dependencies from includes
        recipes = extracted_facts.get("recipes", [])
        if isinstance(recipes, list):
            for recipe in recipes:
                dependencies.extend(recipe if isinstance(recipe, list) else [])
        
        # Identify Chef-specific patterns
        if extracted_facts.get("templates"):
            patterns.append("template_driven_configuration")
        if extracted_facts.get("attributes"):
            patterns.append("attribute_parameterization")
        if len(resources) > 3:
            patterns.append("multi_resource_orchestration")
        
        return {
            "success": True,
            "platform": "chef",
            "components": components,
            "dependencies": dependencies, 
            "infrastructure_patterns": patterns,
            "resource_utilization": {
                "total_resources": sum(len(r) for r in resources.values()),
                "resource_types": list(resources.keys()),
                "template_count": len(extracted_facts.get("templates", [])),
                "attribute_count": len(extracted_facts.get("attributes", {}))
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e), "platform": "chef"}


@tool
def analyze_puppet_infrastructure(extracted_facts: dict, input_code: str) -> dict:
    """
    Analyze Puppet-specific infrastructure facts.
    
    Specializes in analyzing Puppet manifests, classes, modules, and resources
    to extract components, dependencies, and platform-specific patterns.
    
    Args:
        extracted_facts: Puppet-specific extracted facts
        input_code: Original Puppet code for additional analysis
        
    Returns:
        Dictionary with Puppet analysis results
    """
    try:
        components = []
        dependencies = []
        patterns = []
        
        # Basic Puppet analysis - similar to Chef but with Puppet specifics
        if "class" in input_code.lower():
            patterns.append("class_based_organization")
        if "module" in input_code.lower():
            patterns.append("modular_puppet_design")
        if "template" in input_code.lower():
            patterns.append("template_driven_configuration")
        
        # Estimate resources from code
        lines = [line for line in input_code.split('\n') if line.strip()]
        estimated_resources = max(1, len([line for line in lines if "=>" in line]) // 3)
        
        components.append({
            "type": "puppet_manifest",
            "name": "main_manifest",
            "estimated_resources": estimated_resources,
            "line_count": len(lines)
        })
        
        return {
            "success": True,
            "platform": "puppet",
            "components": components,
            "dependencies": dependencies,
            "infrastructure_patterns": patterns,
            "resource_utilization": {
                "estimated_resources": estimated_resources,
                "line_count": len(lines),
                "puppet_classes": len([line for line in lines if "class " in line.lower()])
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e), "platform": "puppet"}


@tool
def analyze_terraform_infrastructure(extracted_facts: dict, input_code: str) -> dict:
    """
    Analyze Terraform-specific infrastructure facts.
    
    Specializes in analyzing Terraform configurations, resources, modules, and variables
    to extract components, dependencies, and platform-specific patterns.
    
    Args:
        extracted_facts: Terraform-specific extracted facts
        input_code: Original Terraform code for additional analysis
        
    Returns:
        Dictionary with Terraform analysis results
    """
    try:
        components = []
        dependencies = []
        patterns = []
        
        # Basic Terraform analysis
        if "resource " in input_code:
            patterns.append("resource_based_infrastructure")
        if "module " in input_code:
            patterns.append("modular_terraform_design")
        if "variable " in input_code:
            patterns.append("parameterized_configuration")
        if "output " in input_code:
            patterns.append("output_driven_design")
        
        # Estimate resources and modules
        lines = [line for line in input_code.split('\n') if line.strip()]
        resource_count = len([line for line in lines if line.strip().startswith("resource ")])
        module_count = len([line for line in lines if line.strip().startswith("module ")])
        
        components.append({
            "type": "terraform_configuration",
            "name": "main_config",
            "resource_count": resource_count,
            "module_count": module_count,
            "line_count": len(lines)
        })
        
        return {
            "success": True,
            "platform": "terraform",
            "components": components,
            "dependencies": dependencies,
            "infrastructure_patterns": patterns,
            "resource_utilization": {
                "terraform_resources": resource_count,
                "terraform_modules": module_count,
                "line_count": len(lines)
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e), "platform": "terraform"}


@tool
def analyze_generic_infrastructure(extracted_facts: dict, input_code: str) -> dict:
    """
    Analyze generic infrastructure facts.
    
    Fallback analysis for unrecognized platforms or mixed infrastructure.
    Provides basic analysis capabilities for any infrastructure code.
    
    Args:
        extracted_facts: Generic extracted facts
        input_code: Original infrastructure code for analysis
        
    Returns:
        Dictionary with generic analysis results
    """
    try:
        components = []
        patterns = []
        
        # Basic code analysis
        lines = input_code.split('\n') if input_code else []
        non_empty_lines = [line for line in lines if line.strip()]
        
        # Look for common patterns
        if any("template" in line.lower() for line in non_empty_lines):
            patterns.append("template_usage")
        if any("variable" in line.lower() for line in non_empty_lines):
            patterns.append("variable_parameterization")
        if any("include" in line.lower() or "import" in line.lower() for line in non_empty_lines):
            patterns.append("modular_design")
        
        components.append({
            "type": "infrastructure_code",
            "name": "main_configuration",
            "line_count": len(non_empty_lines),
            "estimated_resources": max(1, len(non_empty_lines) // 10)
        })
        
        return {
            "success": True,
            "platform": "generic",
            "components": components,
            "dependencies": [],
            "infrastructure_patterns": patterns,
            "resource_utilization": {
                "line_count": len(non_empty_lines),
                "estimated_complexity": "low" if len(non_empty_lines) < 50 else "medium" if len(non_empty_lines) < 200 else "high"
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e), "platform": "generic"}
