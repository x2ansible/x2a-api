"""
BladeLogic Facts Extractor Tool

Minimal implementation for extracting structured facts from BladeLogic scripts and configurations.
Can be extended later with more sophisticated parsing of BladeLogic NSH scripts and job definitions.
"""

import re
import os
import json
from typing import Dict, Any, List
from langchain_core.tools import tool


@tool
async def bladelogic_facts_extractor(files: Dict[str, str]) -> Dict[str, Any]:
    """
    Extract structured facts from BladeLogic scripts and configurations using pattern matching.
    
    This is a minimal implementation that can be extended later with:
    - NSH script parser
    - BladeLogic job definition analysis
    - Package and patch deployment analysis
    - Configuration template parsing
    
    Args:
        files: Dictionary of {filename: content} for BladeLogic files
        
    Returns:
        Dict containing structured BladeLogic facts and analysis
    """
    
    if not files:
        return {
            "success": False,
            "error": "No files provided",
            "structured_facts": {},
            "natural_language": {"summary": "No files to analyze"}
        }
    
    try:
        # Initialize facts structure
        facts = {
            "schema": "bladelogic-facts@1.0",
            "scripts": [],
            "jobs": [],
            "packages": [],
            "patches": [],
            "configurations": [],
            "commands": [],
            "variables": [],
            "meta": {
                "extractor_version": "1.0.0-minimal",
                "total_files": len(files),
                "total_commands": 0
            }
        }
        
        for filename, content in files.items():
            # Process different BladeLogic file types
            if _is_bladelogic_file(filename, content):
                script_facts = _extract_bladelogic_script_facts(filename, content)
                facts["scripts"].append(script_facts)
                facts["commands"].extend(script_facts["commands"])
                facts["packages"].extend(script_facts["packages"])
                facts["patches"].extend(script_facts["patches"])
                facts["configurations"].extend(script_facts["configurations"])
                facts["variables"].extend(script_facts["variables"])
                facts["jobs"].extend(script_facts["jobs"])
        
        facts["meta"]["total_commands"] = len(facts["commands"])
        
        # Generate natural language explanation
        explanations = _generate_bladelogic_explanations(facts)
        
        return {
            "success": True,
            "platform": "bladelogic",
            "structured_facts": facts,
            "natural_language": explanations,
            "method": "pattern_matching",
            "schema_version": "bladelogic-facts@1.0"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"BladeLogic facts extraction failed: {str(e)}",
            "structured_facts": {},
            "natural_language": {"summary": f"Analysis failed: {str(e)}"},
            "method": "failed"
        }


def _is_bladelogic_file(filename: str, content: str) -> bool:
    """Determine if this is a BladeLogic file"""
    
    # Check file extensions
    bladelogic_extensions = ['.nsh', '.blpackage', '.bljob', '.bl']
    if any(filename.lower().endswith(ext) for ext in bladelogic_extensions):
        return True
    
    # Check content patterns
    bladelogic_patterns = [
        r'#!/bin/nsh',  # NSH shebang
        r'blcli\s+',    # BladeLogic CLI
        r'depot\s+',    # Depot operations
        r'job\s+create', # Job creation
        r'package\s+deploy', # Package deployment
        r'patch\s+deploy',   # Patch deployment
        r'snapshot\s+',      # Snapshot operations
        r'compliance\s+',    # Compliance operations
    ]
    
    content_lower = content.lower()
    return any(re.search(pattern, content_lower) for pattern in bladelogic_patterns)


def _extract_bladelogic_script_facts(filename: str, content: str) -> Dict[str, Any]:
    """Extract facts from a BladeLogic script or configuration"""
    
    script = {
        "name": os.path.splitext(os.path.basename(filename))[0],
        "file": filename,
        "type": _detect_bladelogic_file_type(filename, content),
        "commands": [],
        "packages": [],
        "patches": [],
        "configurations": [],
        "variables": [],
        "jobs": [],
        "targets": []
    }
    
    lines = content.split('\n')
    
    # Extract BladeLogic CLI commands
    blcli_pattern = r'blcli\s+(\w+)\s+(\w+)(?:\s+(.+))?'
    for i, line in enumerate(lines):
        match = re.search(blcli_pattern, line)
        if match:
            namespace = match.group(1)
            command = match.group(2)
            args = match.group(3) if match.group(3) else ""
            
            script["commands"].append({
                "namespace": namespace,
                "command": command,
                "arguments": args.strip(),
                "file": filename,
                "line": i + 1
            })
    
    # Extract package deployments
    package_patterns = [
        r'depot\s+(\w+)\s+deploy\s+(.+)',
        r'package\s+deploy\s+(.+)',
        r'blpackage\s+(.+)'
    ]
    
    for i, line in enumerate(lines):
        for pattern in package_patterns:
            match = re.search(pattern, line)
            if match:
                if 'depot' in pattern:
                    depot_name = match.group(1)
                    package_info = match.group(2)
                else:
                    depot_name = "unknown"
                    package_info = match.group(1)
                
                script["packages"].append({
                    "depot": depot_name,
                    "package": package_info.strip(),
                    "file": filename,
                    "line": i + 1
                })
    
    # Extract patch deployments
    patch_patterns = [
        r'patch\s+deploy\s+(.+)',
        r'patch\s+catalog\s+(.+)',
        r'blpatch\s+(.+)'
    ]
    
    for i, line in enumerate(lines):
        for pattern in patch_patterns:
            match = re.search(pattern, line)
            if match:
                patch_info = match.group(1)
                
                script["patches"].append({
                    "patch": patch_info.strip(),
                    "file": filename,
                    "line": i + 1
                })
    
    # Extract job definitions
    job_patterns = [
        r'job\s+create\s+(.+)',
        r'job\s+(\w+)\s+(.+)',
        r'bljob\s+(.+)'
    ]
    
    for i, line in enumerate(lines):
        for pattern in job_patterns:
            match = re.search(pattern, line)
            if match:
                if 'create' in line:
                    job_name = match.group(1)
                    job_type = "create"
                else:
                    job_type = match.group(1) if match.lastindex >= 2 else "unknown"
                    job_name = match.group(2) if match.lastindex >= 2 else match.group(1)
                
                script["jobs"].append({
                    "name": job_name.strip(),
                    "type": job_type,
                    "file": filename,
                    "line": i + 1
                })
    
    # Extract configuration items
    config_patterns = [
        r'config\s+(\w+)\s+(.+)',
        r'template\s+(\w+)\s+(.+)',
        r'compliance\s+(\w+)\s+(.+)'
    ]
    
    for i, line in enumerate(lines):
        for pattern in config_patterns:
            match = re.search(pattern, line)
            if match:
                config_type = match.group(1)
                config_details = match.group(2)
                
                script["configurations"].append({
                    "type": config_type,
                    "details": config_details.strip(),
                    "file": filename,
                    "line": i + 1
                })
    
    # Extract variables and properties
    variable_patterns = [
        r'set\s+(\w+)=(.+)',
        r'property\s+(\w+)\s*=\s*(.+)',
        r'\$\{(\w+)\}',  # Variable references
        r'\$(\w+)'       # Variable references
    ]
    
    for i, line in enumerate(lines):
        for pattern in variable_patterns:
            matches = re.finditer(pattern, line)
            for match in matches:
                var_name = match.group(1)
                var_value = match.group(2) if match.lastindex >= 2 else "referenced"
                
                # Avoid duplicates
                if not any(v["name"] == var_name for v in script["variables"]):
                    script["variables"].append({
                        "name": var_name,
                        "value": var_value.strip() if var_value != "referenced" else None,
                        "type": "property" if "property" in pattern else "variable",
                        "file": filename,
                        "line": i + 1
                    })
    
    # Extract target servers/systems
    target_patterns = [
        r'target\s+(.+)',
        r'server\s+(.+)',
        r'host\s+(.+)'
    ]
    
    for i, line in enumerate(lines):
        for pattern in target_patterns:
            match = re.search(pattern, line)
            if match:
                target_info = match.group(1)
                
                script["targets"].append({
                    "target": target_info.strip(),
                    "file": filename,
                    "line": i + 1
                })
    
    return script


def _detect_bladelogic_file_type(filename: str, content: str) -> str:
    """Detect the specific type of BladeLogic file"""
    
    # Check by extension first
    if filename.lower().endswith('.nsh'):
        return "nsh_script"
    elif filename.lower().endswith('.blpackage'):
        return "package_definition"
    elif filename.lower().endswith('.bljob'):
        return "job_definition"
    elif filename.lower().endswith('.bl'):
        return "bladelogic_config"
    
    # Check by content patterns
    if 'job create' in content.lower():
        return "job_definition"
    elif 'package deploy' in content.lower():
        return "package_script"
    elif 'patch deploy' in content.lower():
        return "patch_script"
    elif 'compliance' in content.lower():
        return "compliance_script"
    elif 'blcli' in content.lower():
        return "cli_script"
    
    return "bladelogic_script"


def _generate_bladelogic_explanations(facts: Dict[str, Any]) -> Dict[str, str]:
    """Generate natural language explanations of BladeLogic facts"""
    
    total_commands = facts["meta"]["total_commands"]
    total_packages = len(facts["packages"])
    total_patches = len(facts["patches"])
    total_jobs = len(facts["jobs"])
    total_configurations = len(facts["configurations"])
    
    # Analyze command namespaces
    command_namespaces = list(set([cmd["namespace"] for cmd in facts["commands"]]))
    
    summary = f"""BladeLogic Infrastructure Analysis:

**Overview:**
- Total Commands: {total_commands}
- Package Deployments: {total_packages}
- Patch Deployments: {total_patches}
- Job Definitions: {total_jobs}
- Configuration Items: {total_configurations}

**Command Namespaces:**
{', '.join(command_namespaces) if command_namespaces else 'None detected'}

**Scripts Found:**
"""
    
    for script in facts["scripts"][:5]:  # Show first 5
        summary += f"- {script['name']} ({script['type']}) - {len(script['commands'])} commands\n"
    
    if len(facts["scripts"]) > 5:
        summary += f"... and {len(facts['scripts']) - 5} more scripts\n"
    
    summary += f"""
**Package Deployments:**
"""
    
    for package in facts["packages"][:5]:  # Show first 5
        depot = package.get('depot', 'unknown')
        summary += f"- {package['package']} (depot: {depot})\n"
    
    if len(facts["packages"]) > 5:
        summary += f"... and {len(facts['packages']) - 5} more packages\n"
    
    summary += f"""
**Jobs:**
"""
    
    for job in facts["jobs"][:5]:  # Show first 5
        summary += f"- {job['name']} ({job['type']})\n"
    
    if len(facts["jobs"]) > 5:
        summary += f"... and {len(facts['jobs']) - 5} more jobs\n"
    
    summary += f"""
**Variables:**
- Total Variables: {len(facts["variables"])}

**Analysis Method:** Pattern matching (can be enhanced with NSH parser and BladeLogic API integration)
"""
    
    # Determine complexity based on various factors
    complexity = "low"
    if total_commands > 50 or total_jobs > 10:
        complexity = "high"
    elif total_commands > 20 or total_jobs > 5 or total_packages > 10:
        complexity = "medium"
    
    return {
        "summary": summary,
        "complexity": complexity,
        "recommendations": [
            "Consider migrating BladeLogic scripts to modern automation tools",
            "Review package and patch deployment strategies",
            "Consolidate job definitions where possible",
            "Document variable usage and dependencies",
            "Plan for BladeLogic to Ansible/Chef migration path"
        ]
    }
