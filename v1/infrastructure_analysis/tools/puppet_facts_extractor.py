"""
Puppet Facts Extractor Tool

Minimal implementation for extracting structured facts from Puppet manifests.
Can be extended later with more sophisticated parsing (e.g., Puppet AST parser).
"""

import re
import os
import tempfile
import json
from typing import Dict, Any, List
from langchain_core.tools import tool


@tool
async def puppet_facts_extractor(files: Dict[str, str]) -> Dict[str, Any]:
    """
    Extract structured facts from Puppet manifests using pattern matching.
    
    This is a minimal implementation that can be extended later with:
    - Puppet AST parser
    - More sophisticated dependency analysis
    - Advanced template variable extraction
    
    Args:
        files: Dictionary of {filename: content} for Puppet files
        
    Returns:
        Dict containing structured Puppet facts and analysis
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
            "schema": "puppet-facts@1.0",
            "manifests": [],
            "classes": [],
            "resources": [],
            "dependencies": [],
            "variables": [],
            "meta": {
                "extractor_version": "1.0.0-minimal",
                "total_files": len(files),
                "total_resources": 0
            }
        }
        
        for filename, content in files.items():
            if not filename.endswith('.pp'):
                continue
                
            manifest_facts = _extract_manifest_facts(filename, content)
            facts["manifests"].append(manifest_facts)
            facts["resources"].extend(manifest_facts["resources"])
            facts["classes"].extend(manifest_facts["classes"])
            facts["dependencies"].extend(manifest_facts["dependencies"])
            facts["variables"].extend(manifest_facts["variables"])
        
        facts["meta"]["total_resources"] = len(facts["resources"])
        
        # Generate natural language explanation
        explanations = _generate_puppet_explanations(facts)
        
        return {
            "success": True,
            "platform": "puppet",
            "structured_facts": facts,
            "natural_language": explanations,
            "method": "pattern_matching",
            "schema_version": "puppet-facts@1.0"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Puppet facts extraction failed: {str(e)}",
            "structured_facts": {},
            "natural_language": {"summary": f"Analysis failed: {str(e)}"},
            "method": "failed"
        }


def _extract_manifest_facts(filename: str, content: str) -> Dict[str, Any]:
    """Extract facts from a single Puppet manifest"""
    
    manifest = {
        "name": os.path.splitext(os.path.basename(filename))[0],
        "file": filename,
        "classes": [],
        "resources": [],
        "dependencies": [],
        "variables": []
    }
    
    lines = content.split('\n')
    
    # Extract classes
    class_pattern = r'class\s+([a-zA-Z_][a-zA-Z0-9_:]*)\s*(?:\([^)]*\))?\s*\{'
    for i, line in enumerate(lines):
        match = re.search(class_pattern, line)
        if match:
            class_name = match.group(1)
            manifest["classes"].append({
                "name": class_name,
                "file": filename,
                "line": i + 1
            })
    
    # Extract resources
    resource_patterns = [
        r'(package|service|file|user|group|cron|exec)\s*\{\s*[\'"]([^\'"]+)[\'"]',
        r'([a-zA-Z_][a-zA-Z0-9_]*)\s*\{\s*[\'"]([^\'"]+)[\'"]'  # Custom resources
    ]
    
    for i, line in enumerate(lines):
        for pattern in resource_patterns:
            matches = re.finditer(pattern, line)
            for match in matches:
                resource_type = match.group(1)
                resource_name = match.group(2)
                
                # Extract resource properties
                properties = _extract_resource_properties(lines, i)
                
                manifest["resources"].append({
                    "type": resource_type,
                    "name": resource_name,
                    "file": filename,
                    "line": i + 1,
                    "properties": properties
                })
    
    # Extract dependencies (require, before, notify, subscribe)
    dependency_pattern = r'(require|before|notify|subscribe)\s*=>\s*([^,\}]+)'
    for i, line in enumerate(lines):
        matches = re.finditer(dependency_pattern, line)
        for match in matches:
            dep_type = match.group(1)
            dep_target = match.group(2).strip()
            
            manifest["dependencies"].append({
                "type": dep_type,
                "target": dep_target,
                "file": filename,
                "line": i + 1
            })
    
    # Extract variables
    variable_pattern = r'\$([a-zA-Z_][a-zA-Z0-9_]*)'
    for i, line in enumerate(lines):
        matches = re.finditer(variable_pattern, line)
        for match in matches:
            var_name = match.group(1)
            if var_name not in [v["name"] for v in manifest["variables"]]:
                manifest["variables"].append({
                    "name": var_name,
                    "file": filename,
                    "line": i + 1
                })
    
    return manifest


def _extract_resource_properties(lines: List[str], start_line: int) -> Dict[str, Any]:
    """Extract properties from a Puppet resource block"""
    properties = {}
    
    # Look for properties in the next few lines
    for i in range(start_line, min(start_line + 20, len(lines))):
        line = lines[i].strip()
        
        # End of resource block
        if line.startswith('}'):
            break
            
        # Property pattern: key => value
        prop_match = re.search(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*=>\s*([^,\}]+)', line)
        if prop_match:
            key = prop_match.group(1)
            value = prop_match.group(2).strip().strip('\'"')
            properties[key] = value
    
    return properties


def _generate_puppet_explanations(facts: Dict[str, Any]) -> Dict[str, str]:
    """Generate natural language explanations of Puppet facts"""
    
    total_resources = facts["meta"]["total_resources"]
    total_classes = len(facts["classes"])
    resource_types = list(set([r["type"] for r in facts["resources"]]))
    
    summary = f"""Puppet Infrastructure Analysis:

**Overview:**
- Total Resources: {total_resources}
- Total Classes: {total_classes}
- Resource Types: {', '.join(resource_types)}

**Classes Found:**
"""
    
    for class_info in facts["classes"][:5]:  # Show first 5
        summary += f"- {class_info['name']} ({class_info['file']})\n"
    
    if len(facts["classes"]) > 5:
        summary += f"... and {len(facts['classes']) - 5} more classes\n"
    
    summary += f"""
**Common Resources:**
"""
    
    for resource in facts["resources"][:10]:  # Show first 10
        summary += f"- {resource['type']}: {resource['name']}\n"
    
    if len(facts["resources"]) > 10:
        summary += f"... and {len(facts['resources']) - 10} more resources\n"
    
    summary += f"""
**Dependencies:**
- Total Dependencies: {len(facts["dependencies"])}

**Analysis Method:** Pattern matching (can be enhanced with Puppet AST parser)
"""
    
    return {
        "summary": summary,
        "complexity": "medium" if total_resources > 10 else "low",
        "recommendations": [
            "Consider using Puppet modules for better organization",
            "Review dependencies for optimization opportunities",
            "Validate resource relationships"
        ]
    }
