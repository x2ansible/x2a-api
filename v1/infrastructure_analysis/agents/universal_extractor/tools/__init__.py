"""
Universal Extraction Tools

All platform detection and extraction tools available to the universal agent.
"""

# Import platform detection and extraction tools from main tools directory
from infrastructure_analysis.tools.platform_detector import platform_detector
from infrastructure_analysis.tools.puppet_facts_extractor import puppet_facts_extractor
from infrastructure_analysis.tools.terraform_facts_extractor import terraform_facts_extractor  
from infrastructure_analysis.tools.bladelogic_facts_extractor import bladelogic_facts_extractor
# Removed chef_facts_extractor import - now using direct Tree-sitter approach

# Create a direct string-to-facts Chef extractor (bypasses filesystem requirements)
from langchain_core.tools import tool
from typing import Dict, Any
import sys
import os
from pathlib import Path

# Add the tools directory to Python path to import chef_facts_engine directly
tools_dir = Path(__file__).parent.parent.parent.parent / "tools"
sys.path.insert(0, str(tools_dir))

from chef_facts_engine import (
    PARSER, node_text, walk, strip_quotes, 
    scan_attributes_in_text, scan_includes_split,
    find_recipe_resources, RESOURCE_TYPES,
    get_method_identifier
)

@tool
async def chef_facts_extractor_legacy(code: str) -> Dict[str, Any]:
    """
    Direct Chef facts extractor for raw code strings.
    
    Uses the comprehensive Tree-sitter based extractor directly on in-memory code,
    bypassing the filesystem requirements of the full cookbook extractor.
    
    Args:
        code: Raw Chef cookbook code (recipes, metadata, etc.)
        
    Returns:
        Dict containing extracted Chef facts and analysis
    """
    if not code or not code.strip():
        return {
            "success": False,
            "error": "No Chef code provided",
            "structured_facts": {},
            "natural_language": {"summary": "No Chef code to analyze"}
        }
    
    try:
        # Parse the code directly with Tree-sitter
        src = code.encode('utf-8')
        tree = PARSER.parse(src)
        
        # Extract resources directly from the AST
        resources = find_recipe_resources(src, tree, "default.rb")
        
        # Extract attributes and includes
        attrs = scan_attributes_in_text(code)
        includes, includes_dyn = scan_includes_split(code)
        
        # Detect cookbook name if present
        cookbook_name = "unknown"
        if 'cookbook_name' in code:
            import re
            match = re.search(r"cookbook_name\s+['\"]([^'\"]+)['\"]", code)
            if match:
                cookbook_name = match.group(1)
        
        # Build comprehensive facts structure
        facts = {
            "schema": "chef-facts@1",
            "cookbook": cookbook_name,
            "recipes": [{
                "name": "default",
                "file": "default.rb", 
                "includes": includes,
                "includes_dynamic": includes_dyn,
                "attributes_read": attrs,
                "resources": resources,
                "templates": [
                    {
                        "path": r.get("properties", {}).get("path", [None])[0],
                        "source": r.get("properties", {}).get("source", [None])[0],
                        "vars": r.get("properties", {}).get("variables_keys", []),
                    }
                    for r in resources if r["type"] == "template"
                ]
            }],
            "custom_resources": [],
            "meta": {
                "extractor_version": "1.3.0-direct",
                "coverage": {
                    "files_scanned": 1,
                    "recipe_files": 1, 
                    "recipes": 1,
                    "resources_total": len(resources),
                    "custom_resources": 0,
                    "templates_total": len([r for r in resources if r["type"] == "template"]),
                    "notes": ["Direct string analysis - no filesystem required"]
                }
            }
        }
        
        return {
            "success": True,
            "structured_facts": facts,
            "natural_language": {
                "summary": f"Chef recipe analysis: {cookbook_name}",
                "structure": f"Found {len(resources)} Chef resources including {len([r for r in resources if r['type'] == 'package'])} packages",
                "resources": [f"{r['type']}[{r['name'] or r.get('name_expr', '?')}]" for r in resources]
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Chef analysis failed: {str(e)}",
            "structured_facts": {},
            "natural_language": {"summary": f"Chef analysis failed: {str(e)}"}
        }

__all__ = [
    # Platform detection
    "platform_detector",
    
    # Extraction tools for all platforms
    "puppet_facts_extractor",      # Puppet manifest extractor
    "terraform_facts_extractor",   # Terraform configuration extractor
    "bladelogic_facts_extractor",  # BladeLogic script extractor
    "chef_facts_extractor_legacy"  # Legacy Chef extractor
]
