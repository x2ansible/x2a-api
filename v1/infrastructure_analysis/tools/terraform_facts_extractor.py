"""
Terraform Facts Extractor Tool

Minimal implementation for extracting structured facts from Terraform configurations.
Can be extended later with HCL AST parser or terraform-json for more sophisticated analysis.
"""

import re
import os
import json
from typing import Dict, Any, List
from langchain_core.tools import tool


@tool
async def terraform_facts_extractor(files: Dict[str, str]) -> Dict[str, Any]:
    """
    Extract structured facts from Terraform configurations using pattern matching.
    
    This is a minimal implementation that can be extended later with:
    - HCL AST parser
    - Terraform plan analysis
    - Advanced dependency graph analysis
    - Provider-specific resource analysis
    
    Args:
        files: Dictionary of {filename: content} for Terraform files
        
    Returns:
        Dict containing structured Terraform facts and analysis
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
            "schema": "terraform-facts@1.0",
            "configuration_files": [],
            "resources": [],
            "data_sources": [],
            "variables": [],
            "outputs": [],
            "providers": [],
            "modules": [],
            "meta": {
                "extractor_version": "1.0.0-minimal",
                "total_files": len(files),
                "total_resources": 0
            }
        }
        
        for filename, content in files.items():
            if not (filename.endswith('.tf') or filename.endswith('.hcl')):
                continue
                
            config_facts = _extract_terraform_config_facts(filename, content)
            facts["configuration_files"].append(config_facts)
            facts["resources"].extend(config_facts["resources"])
            facts["data_sources"].extend(config_facts["data_sources"])
            facts["variables"].extend(config_facts["variables"])
            facts["outputs"].extend(config_facts["outputs"])
            facts["providers"].extend(config_facts["providers"])
            facts["modules"].extend(config_facts["modules"])
        
        facts["meta"]["total_resources"] = len(facts["resources"])
        
        # Generate natural language explanation
        explanations = _generate_terraform_explanations(facts)
        
        return {
            "success": True,
            "platform": "terraform",
            "structured_facts": facts,
            "natural_language": explanations,
            "method": "pattern_matching",
            "schema_version": "terraform-facts@1.0"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Terraform facts extraction failed: {str(e)}",
            "structured_facts": {},
            "natural_language": {"summary": f"Analysis failed: {str(e)}"},
            "method": "failed"
        }


def _extract_terraform_config_facts(filename: str, content: str) -> Dict[str, Any]:
    """Extract facts from a single Terraform configuration file"""
    
    config = {
        "name": os.path.splitext(os.path.basename(filename))[0],
        "file": filename,
        "resources": [],
        "data_sources": [],
        "variables": [],
        "outputs": [],
        "providers": [],
        "modules": []
    }
    
    lines = content.split('\n')
    
    # Extract resources
    resource_pattern = r'resource\s+"([^"]+)"\s+"([^"]+)"\s*\{'
    for i, line in enumerate(lines):
        match = re.search(resource_pattern, line)
        if match:
            resource_type = match.group(1)
            resource_name = match.group(2)
            
            # Extract resource configuration
            config_block = _extract_terraform_block(lines, i)
            
            config["resources"].append({
                "type": resource_type,
                "name": resource_name,
                "file": filename,
                "line": i + 1,
                "configuration": config_block
            })
    
    # Extract data sources
    data_pattern = r'data\s+"([^"]+)"\s+"([^"]+)"\s*\{'
    for i, line in enumerate(lines):
        match = re.search(data_pattern, line)
        if match:
            data_type = match.group(1)
            data_name = match.group(2)
            
            config_block = _extract_terraform_block(lines, i)
            
            config["data_sources"].append({
                "type": data_type,
                "name": data_name,
                "file": filename,
                "line": i + 1,
                "configuration": config_block
            })
    
    # Extract variables
    variable_pattern = r'variable\s+"([^"]+)"\s*\{'
    for i, line in enumerate(lines):
        match = re.search(variable_pattern, line)
        if match:
            var_name = match.group(1)
            
            var_config = _extract_terraform_block(lines, i)
            
            config["variables"].append({
                "name": var_name,
                "file": filename,
                "line": i + 1,
                "type": var_config.get("type", "unknown"),
                "description": var_config.get("description", ""),
                "default": var_config.get("default", None)
            })
    
    # Extract outputs
    output_pattern = r'output\s+"([^"]+)"\s*\{'
    for i, line in enumerate(lines):
        match = re.search(output_pattern, line)
        if match:
            output_name = match.group(1)
            
            output_config = _extract_terraform_block(lines, i)
            
            config["outputs"].append({
                "name": output_name,
                "file": filename,
                "line": i + 1,
                "value": output_config.get("value", ""),
                "description": output_config.get("description", ""),
                "sensitive": output_config.get("sensitive", False)
            })
    
    # Extract providers
    provider_pattern = r'provider\s+"([^"]+)"\s*\{'
    for i, line in enumerate(lines):
        match = re.search(provider_pattern, line)
        if match:
            provider_name = match.group(1)
            
            provider_config = _extract_terraform_block(lines, i)
            
            config["providers"].append({
                "name": provider_name,
                "file": filename,
                "line": i + 1,
                "configuration": provider_config
            })
    
    # Extract modules
    module_pattern = r'module\s+"([^"]+)"\s*\{'
    for i, line in enumerate(lines):
        match = re.search(module_pattern, line)
        if match:
            module_name = match.group(1)
            
            module_config = _extract_terraform_block(lines, i)
            
            config["modules"].append({
                "name": module_name,
                "file": filename,
                "line": i + 1,
                "source": module_config.get("source", ""),
                "configuration": module_config
            })
    
    return config


def _extract_terraform_block(lines: List[str], start_line: int) -> Dict[str, Any]:
    """Extract configuration from a Terraform block"""
    block_config = {}
    brace_count = 0
    in_block = False
    
    for i in range(start_line, len(lines)):
        line = lines[i].strip()
        
        # Count braces to track block boundaries
        brace_count += line.count('{') - line.count('}')
        
        if '{' in line:
            in_block = True
        
        if in_block and brace_count == 0:
            break
        
        # Extract key-value pairs
        kv_match = re.search(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(.+)', line)
        if kv_match:
            key = kv_match.group(1)
            value = kv_match.group(2).strip()
            
            # Clean up value (remove quotes, etc.)
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            elif value.startswith('[') and value.endswith(']'):
                # Simple list parsing
                value = [item.strip().strip('"') for item in value[1:-1].split(',')]
            
            block_config[key] = value
    
    return block_config


def _generate_terraform_explanations(facts: Dict[str, Any]) -> Dict[str, str]:
    """Generate natural language explanations of Terraform facts"""
    
    total_resources = facts["meta"]["total_resources"]
    total_data_sources = len(facts["data_sources"])
    total_variables = len(facts["variables"])
    total_outputs = len(facts["outputs"])
    
    # Analyze resource types
    resource_types = {}
    for resource in facts["resources"]:
        res_type = resource["type"]
        resource_types[res_type] = resource_types.get(res_type, 0) + 1
    
    # Analyze providers
    providers = list(set([p["name"] for p in facts["providers"]]))
    
    summary = f"""Terraform Infrastructure Analysis:

**Overview:**
- Total Resources: {total_resources}
- Data Sources: {total_data_sources}
- Variables: {total_variables}
- Outputs: {total_outputs}
- Providers: {', '.join(providers) if providers else 'None explicitly defined'}

**Resource Types:**
"""
    
    for res_type, count in sorted(resource_types.items(), key=lambda x: x[1], reverse=True)[:10]:
        summary += f"- {res_type}: {count} instance{'s' if count > 1 else ''}\n"
    
    summary += f"""
**Key Resources:**
"""
    
    for resource in facts["resources"][:10]:  # Show first 10
        summary += f"- {resource['type']}.{resource['name']}\n"
    
    if len(facts["resources"]) > 10:
        summary += f"... and {len(facts['resources']) - 10} more resources\n"
    
    summary += f"""
**Variables:**
"""
    for var in facts["variables"][:5]:  # Show first 5
        summary += f"- {var['name']}: {var.get('type', 'unknown type')}\n"
    
    if len(facts["variables"]) > 5:
        summary += f"... and {len(facts['variables']) - 5} more variables\n"
    
    summary += f"""
**Analysis Method:** Pattern matching (can be enhanced with HCL parser or terraform-json)
"""
    
    # Determine complexity based on resource count and types
    complexity = "low"
    if total_resources > 20:
        complexity = "high"
    elif total_resources > 10 or len(resource_types) > 5:
        complexity = "medium"
    
    return {
        "summary": summary,
        "complexity": complexity,
        "recommendations": [
            "Consider using Terraform modules for better organization",
            "Review resource dependencies and ordering",
            "Ensure proper variable validation and descriptions",
            "Consider using remote state for team collaboration"
        ]
    }
