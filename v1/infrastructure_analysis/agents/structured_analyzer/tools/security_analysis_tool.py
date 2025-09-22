#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Security Analysis Tool

Focused tool for generating security considerations and recommendations
for infrastructure code. Analyzes platform-specific security patterns,
complexity-based risks, and common security vulnerabilities.
"""

from langchain_core.tools import tool


@tool
def generate_security_considerations(
    extracted_facts: dict,
    platform: str,
    platform_analysis: dict,
    complexity_analysis: dict
) -> dict:
    """
    Generate comprehensive security considerations for infrastructure.
    
    Analyzes platform-specific security patterns, complexity-based risks,
    and common vulnerabilities to provide actionable security recommendations.
    
    Args:
        extracted_facts: Dictionary of extracted infrastructure facts
        platform: Platform type (chef, puppet, terraform, etc.)
        platform_analysis: Results from platform-specific analysis
        complexity_analysis: Results from complexity analysis
        
    Returns:
        Dictionary with security considerations and recommendations
    """
    try:
        considerations = []
        risk_level = "low"
        security_categories = {}
        
        # Platform-specific security checks
        if platform == "chef":
            chef_security = _analyze_chef_security(extracted_facts, platform_analysis)
            considerations.extend(chef_security["considerations"])
            security_categories["chef_specific"] = chef_security
            
        elif platform == "puppet":
            puppet_security = _analyze_puppet_security(extracted_facts, platform_analysis)
            considerations.extend(puppet_security["considerations"])
            security_categories["puppet_specific"] = puppet_security
            
        elif platform == "terraform":
            terraform_security = _analyze_terraform_security(extracted_facts, platform_analysis)
            considerations.extend(terraform_security["considerations"])
            security_categories["terraform_specific"] = terraform_security
            
        else:
            generic_security = _analyze_generic_security(extracted_facts, platform_analysis)
            considerations.extend(generic_security["considerations"])
            security_categories["generic"] = generic_security
        
        # Complexity-based security considerations
        complexity_security = _analyze_complexity_security(complexity_analysis)
        considerations.extend(complexity_security["considerations"])
        security_categories["complexity_based"] = complexity_security
        
        # Determine overall risk level
        complexity_level = complexity_analysis.get("complexity", {}).get("level", "low")
        if complexity_level == "high":
            risk_level = "high"
        elif complexity_level == "medium" or len(considerations) > 5:
            risk_level = "medium"
        
        # Generate security best practices
        best_practices = _generate_security_best_practices(platform, risk_level)
        security_categories["best_practices"] = best_practices
        considerations.extend(best_practices["considerations"])
        
        return {
            "success": True,
            "security_analysis": {
                "risk_level": risk_level,
                "total_considerations": len(considerations),
                "considerations": considerations,
                "categories": security_categories,
                "recommendations": _prioritize_security_recommendations(considerations, risk_level)
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def _analyze_chef_security(extracted_facts: dict, platform_analysis: dict) -> dict:
    """Analyze Chef-specific security considerations"""
    considerations = [
        "Review cookbook dependencies for security vulnerabilities",
        "Validate template variables for injection risks",
        "Ensure proper file permissions in resource definitions"
    ]
    
    # Check for specific security patterns
    resources = extracted_facts.get("resources", {})
    if "file" in resources or "template" in resources:
        considerations.append("Audit file and template resources for sensitive data exposure")
    if "execute" in resources:
        considerations.append("Review execute resources for command injection risks")
    if "remote_file" in resources:
        considerations.append("Validate remote file sources for supply chain security")
    
    # Template security
    template_count = platform_analysis.get("resource_utilization", {}).get("template_count", 0)
    if template_count > 3:
        considerations.append("High template usage: Implement template security scanning")
    
    return {
        "considerations": considerations,
        "focus_areas": ["cookbook_dependencies", "template_security", "file_permissions", "command_execution"]
    }


def _analyze_puppet_security(extracted_facts: dict, platform_analysis: dict) -> dict:
    """Analyze Puppet-specific security considerations"""
    considerations = [
        "Review Puppet module dependencies for vulnerabilities",
        "Validate manifest file permissions and ownership",
        "Ensure secure communication between Puppet master and agents"
    ]
    
    # Check for security patterns in code
    patterns = platform_analysis.get("infrastructure_patterns", [])
    if "class_based_organization" in patterns:
        considerations.append("Review class inheritance for privilege escalation risks")
    if "modular_puppet_design" in patterns:
        considerations.append("Audit module interfaces for security boundaries")
    
    return {
        "considerations": considerations,
        "focus_areas": ["module_dependencies", "manifest_security", "agent_communication", "class_privileges"]
    }


def _analyze_terraform_security(extracted_facts: dict, platform_analysis: dict) -> dict:
    """Analyze Terraform-specific security considerations"""
    considerations = [
        "Review provider configurations for credential management",
        "Validate state file security and remote backend configuration",
        "Ensure resource configurations follow security best practices"
    ]
    
    # Check for Terraform-specific security patterns
    patterns = platform_analysis.get("infrastructure_patterns", [])
    if "parameterized_configuration" in patterns:
        considerations.append("Review variable definitions for sensitive data exposure")
    if "modular_terraform_design" in patterns:
        considerations.append("Audit module inputs/outputs for security boundaries")
    if "output_driven_design" in patterns:
        considerations.append("Review output values for sensitive data leakage")
    
    resource_count = platform_analysis.get("resource_utilization", {}).get("terraform_resources", 0)
    if resource_count > 10:
        considerations.append("Large resource count: Implement infrastructure security scanning")
    
    return {
        "considerations": considerations,
        "focus_areas": ["provider_security", "state_security", "variable_management", "module_boundaries"]
    }


def _analyze_generic_security(extracted_facts: dict, platform_analysis: dict) -> dict:
    """Analyze generic infrastructure security considerations"""
    considerations = [
        "Review configuration for hardcoded credentials",
        "Validate input parameterization and sanitization",
        "Ensure secure communication protocols",
        "Implement proper access controls and permissions"
    ]
    
    # Check for common security patterns
    patterns = platform_analysis.get("infrastructure_patterns", [])
    if "template_usage" in patterns:
        considerations.append("Review template security and variable handling")
    if "modular_design" in patterns:
        considerations.append("Audit module security boundaries and interfaces")
    
    return {
        "considerations": considerations,
        "focus_areas": ["credential_management", "input_validation", "access_controls", "communication_security"]
    }


def _analyze_complexity_security(complexity_analysis: dict) -> dict:
    """Analyze security considerations based on complexity"""
    considerations = []
    complexity_info = complexity_analysis.get("complexity", {})
    complexity_level = complexity_info.get("level", "low")
    
    if complexity_level == "high":
        considerations.extend([
            "High complexity increases attack surface - implement comprehensive security review",
            "Complex infrastructure requires enhanced monitoring and logging",
            "Consider security architecture review due to complexity",
            "Implement defense-in-depth strategies for complex systems"
        ])
    elif complexity_level == "medium":
        considerations.extend([
            "Moderate complexity requires structured security review",
            "Implement security testing in deployment pipeline"
        ])
    
    # Check specific complexity factors
    breakdown = complexity_info.get("breakdown", {})
    if breakdown.get("dependencies", {}).get("count", 0) > 10:
        considerations.append("High dependency count increases supply chain security risks")
    if breakdown.get("patterns", {}).get("count", 0) > 5:
        considerations.append("Multiple patterns require consistent security implementation")
    
    return {
        "considerations": considerations,
        "focus_areas": ["complexity_management", "attack_surface", "monitoring", "defense_in_depth"]
    }


def _generate_security_best_practices(platform: str, risk_level: str) -> dict:
    """Generate platform-specific security best practices"""
    considerations = [
        "Implement infrastructure as code security scanning",
        "Use secrets management solutions for sensitive data",
        "Enable comprehensive audit logging and monitoring",
        "Implement least privilege access principles"
    ]
    
    if risk_level == "high":
        considerations.extend([
            "Conduct regular security assessments and penetration testing",
            "Implement continuous security monitoring",
            "Establish incident response procedures for infrastructure"
        ])
    
    platform_practices = {
        "chef": [
            "Use Chef InSpec for compliance testing",
            "Implement cookbook signing and verification"
        ],
        "puppet": [
            "Use Puppet security modules and compliance profiles",
            "Implement certificate-based agent authentication"
        ],
        "terraform": [
            "Use tools like tfsec or Checkov for security scanning",
            "Implement remote state encryption and access controls"
        ]
    }
    
    if platform in platform_practices:
        considerations.extend(platform_practices[platform])
    
    return {
        "considerations": considerations,
        "focus_areas": ["scanning", "secrets_management", "monitoring", "access_control"]
    }


def _prioritize_security_recommendations(considerations: list, risk_level: str) -> list:
    """Prioritize security recommendations based on risk level"""
    if risk_level == "high":
        return [
            "CRITICAL: Conduct immediate security review of high-complexity infrastructure",
            "HIGH: Implement comprehensive security monitoring and alerting",
            "HIGH: Review and remediate identified security considerations",
            "MEDIUM: Establish security testing in deployment pipeline",
            "LOW: Document security procedures and incident response"
        ]
    elif risk_level == "medium":
        return [
            "HIGH: Review and address identified security considerations",
            "MEDIUM: Implement security scanning in CI/CD pipeline",
            "MEDIUM: Establish monitoring for security events",
            "LOW: Document security best practices"
        ]
    else:
        return [
            "MEDIUM: Review security considerations and implement fixes",
            "LOW: Establish baseline security monitoring",
            "LOW: Document current security posture"
        ]
