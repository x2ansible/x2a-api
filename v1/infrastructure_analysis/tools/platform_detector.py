"""
Platform Detection Tool

Automatically detects infrastructure automation platforms from file patterns and content.
Supports Chef, Puppet, Salt, and BladeLogic detection with confidence scoring.
"""

import re
from typing import Dict, List, Tuple
from langchain_core.tools import tool


@tool
def platform_detector(files: Dict[str, str]) -> Dict[str, any]:
    """
    Detect infrastructure automation platform(s) from uploaded files.
    
    Analyzes file names, extensions, and content patterns to identify:
    - Chef cookbooks
    - Puppet manifests and modules  
    - SaltStack states
    - BladeLogic scripts
    
    Args:
        files: Dictionary of {filename: content}
        
    Returns:
        Dict with detected platforms, confidence scores, and evidence
    """
    
    if not files:
        return {
            "detected_platforms": [],
            "primary_platform": None,
            "confidence_scores": {},
            "evidence": {},
            "mixed_platform": False
        }
    
    # Platform detection results
    platform_scores = {
        "chef": 0.0,
        "puppet": 0.0, 
        "salt": 0.0,
        "bladelogic": 0.0,
        "terraform": 0.0
    }
    
    evidence = {
        "chef": [],
        "puppet": [],
        "salt": [], 
        "bladelogic": [],
        "terraform": []
    }
    
    # Analyze each file
    for filename, content in files.items():
        chef_score, chef_evidence = _detect_chef(filename, content)
        puppet_score, puppet_evidence = _detect_puppet(filename, content)
        salt_score, salt_evidence = _detect_salt(filename, content)
        bladelogic_score, bladelogic_evidence = _detect_bladelogic(filename, content)
        terraform_score, terraform_evidence = _detect_terraform(filename, content)
        
        platform_scores["chef"] += chef_score
        platform_scores["puppet"] += puppet_score
        platform_scores["salt"] += salt_score
        platform_scores["bladelogic"] += bladelogic_score
        platform_scores["terraform"] += terraform_score
        
        if chef_evidence:
            evidence["chef"].extend(chef_evidence)
        if puppet_evidence:
            evidence["puppet"].extend(puppet_evidence) 
        if salt_evidence:
            evidence["salt"].extend(salt_evidence)
        if bladelogic_evidence:
            evidence["bladelogic"].extend(bladelogic_evidence)
        if terraform_evidence:
            evidence["terraform"].extend(terraform_evidence)
    
    # Normalize scores by file count
    file_count = len(files)
    normalized_scores = {k: v/file_count for k, v in platform_scores.items()}
    
    # Determine primary platform
    primary_platform = max(normalized_scores, key=normalized_scores.get)
    primary_confidence = normalized_scores[primary_platform]
    
    # Detect if this is a mixed-platform setup
    significant_platforms = [p for p, score in normalized_scores.items() if score > 0.1]
    mixed_platform = len(significant_platforms) > 1
    
    # Get detected platforms (confidence > 0.1)
    detected_platforms = [p for p in significant_platforms]
    
    return {
        "detected_platforms": detected_platforms,
        "primary_platform": primary_platform if primary_confidence > 0.1 else None,
        "confidence_scores": normalized_scores,
        "evidence": evidence,
        "mixed_platform": mixed_platform,
        "file_count": file_count
    }


def _detect_chef(filename: str, content: str) -> Tuple[float, List[str]]:
    """Detect Chef cookbook patterns"""
    score = 0.0
    evidence = []
    
    # File name patterns (strong indicators)
    if filename == "metadata.rb":
        score += 1.0
        evidence.append("metadata.rb file found")
    elif filename == "Berksfile":
        score += 0.8
        evidence.append("Berksfile found")
    elif filename.startswith("recipes/") and filename.endswith(".rb"):
        score += 0.7
        evidence.append(f"Recipe file: {filename}")
    elif filename.startswith("resources/") and filename.endswith(".rb"):
        score += 0.7
        evidence.append(f"Custom resource file: {filename}")
    elif filename.startswith("attributes/") and filename.endswith(".rb"):
        score += 0.5
        evidence.append(f"Attributes file: {filename}")
    elif filename.startswith("templates/") and filename.endswith(".erb"):
        score += 0.5
        evidence.append(f"ERB template: {filename}")
    
    # Content patterns
    if "include_recipe" in content:
        score += 0.3
        evidence.append("include_recipe calls found")
    if re.search(r'\b(?:package|service|template|file|directory)\s+[\'"]', content):
        score += 0.4
        evidence.append("Chef resource declarations found")
    if "node[" in content:
        score += 0.3
        evidence.append("Node attribute access found")
    if "cookbook_name" in content:
        score += 0.2
        evidence.append("cookbook_name reference found")
    
    return score, evidence


def _detect_puppet(filename: str, content: str) -> Tuple[float, List[str]]:
    """Detect Puppet manifest patterns"""
    score = 0.0
    evidence = []
    
    # File patterns
    if filename == "Puppetfile":
        score += 1.0
        evidence.append("Puppetfile found")
    elif filename.endswith(".pp"):
        score += 0.7
        evidence.append(f"Puppet manifest: {filename}")
    elif filename.startswith("manifests/"):
        score += 0.6
        evidence.append(f"Manifest directory file: {filename}")
    elif filename.startswith("modules/"):
        score += 0.5
        evidence.append(f"Module file: {filename}")
    elif filename.endswith(".epp"):
        score += 0.4
        evidence.append(f"EPP template: {filename}")
    
    # Content patterns
    if re.search(r'\bclass\s+\w+.*\{', content):
        score += 0.4
        evidence.append("Puppet class definitions found")
    if re.search(r'\b(?:package|service|file|user)\s*\{', content):
        score += 0.4
        evidence.append("Puppet resource declarations found")
    if "ensure =>" in content:
        score += 0.3
        evidence.append("Puppet ensure parameters found")
    if "$::" in content or "${" in content:
        score += 0.2
        evidence.append("Puppet variable syntax found")
    
    return score, evidence


def _detect_salt(filename: str, content: str) -> Tuple[float, List[str]]:
    """Detect SaltStack state patterns"""
    score = 0.0
    evidence = []
    
    # File patterns  
    if filename.endswith(".sls"):
        score += 0.8
        evidence.append(f"Salt state file: {filename}")
    elif filename == "top.sls":
        score += 1.0
        evidence.append("Salt top file found")
    elif filename.startswith("pillar/"):
        score += 0.6
        evidence.append(f"Salt pillar file: {filename}")
    elif filename.endswith("_grain.py"):
        score += 0.5
        evidence.append(f"Salt grain: {filename}")
    
    # Content patterns
    if re.search(r'^\w+:$', content, re.MULTILINE):
        score += 0.3
        evidence.append("YAML state structure found")
    if re.search(r'\s+- name:', content):
        score += 0.3
        evidence.append("Salt state name parameters found")
    if "salt://" in content:
        score += 0.4
        evidence.append("Salt file references found")
    if "pillar[" in content or "grains[" in content:
        score += 0.3
        evidence.append("Salt pillar/grains usage found")
    
    return score, evidence


def _detect_bladelogic(filename: str, content: str) -> Tuple[float, List[str]]:
    """Detect BladeLogic script patterns"""
    score = 0.0
    evidence = []
    
    # File patterns
    if filename.endswith(".blcli"):
        score += 0.8
        evidence.append(f"BladeLogic CLI script: {filename}")
    elif filename.endswith(".nsh"):
        score += 0.7
        evidence.append(f"NSH script: {filename}")
    elif "bladelogic" in filename.lower():
        score += 0.5
        evidence.append(f"BladeLogic in filename: {filename}")
    
    # Content patterns
    if "blcli" in content or "BLCLI" in content:
        score += 0.5
        evidence.append("BladeLogic CLI commands found")
    if "nexec" in content or "ncp" in content:
        score += 0.3
        evidence.append("NSH commands found")
    if "BMC Software" in content or "BladeLogic" in content:
        score += 0.4
        evidence.append("BladeLogic references found")
    
    return score, evidence


def _detect_terraform(filename: str, content: str) -> Tuple[float, List[str]]:
    """Detect Terraform configuration patterns"""
    score = 0.0
    evidence = []
    
    # File name patterns (strong indicators)
    if filename.endswith(".tf"):
        score += 1.0
        evidence.append(f"Terraform file: {filename}")
    elif filename.endswith(".tfvars"):
        score += 0.8
        evidence.append(f"Terraform variables file: {filename}")
    elif filename.endswith(".tfstate"):
        score += 0.9
        evidence.append(f"Terraform state file: {filename}")
    elif filename == "terraform.tf":
        score += 0.9
        evidence.append("Main Terraform configuration file")
    elif filename == "main.tf":
        score += 0.8
        evidence.append("Terraform main configuration file")
    elif filename == "variables.tf":
        score += 0.7
        evidence.append("Terraform variables definition file")
    elif filename == "outputs.tf":
        score += 0.7
        evidence.append("Terraform outputs definition file")
    elif filename == "providers.tf":
        score += 0.7
        evidence.append("Terraform providers configuration file")
    elif filename.startswith("modules/") and filename.endswith(".tf"):
        score += 0.6
        evidence.append(f"Terraform module file: {filename}")
    
    # Content patterns
    if re.search(r'\bprovider\s+"[\w-]+"', content):
        score += 0.5
        evidence.append("Terraform provider declarations found")
    if re.search(r'\bresource\s+"[\w-]+"\s+"[\w-]+"', content):
        score += 0.6
        evidence.append("Terraform resource declarations found")
    if re.search(r'\bdata\s+"[\w-]+"\s+"[\w-]+"', content):
        score += 0.4
        evidence.append("Terraform data source declarations found")
    if re.search(r'\bmodule\s+"[\w-]+"', content):
        score += 0.4
        evidence.append("Terraform module declarations found")
    if re.search(r'\bvariable\s+"[\w-]+"', content):
        score += 0.3
        evidence.append("Terraform variable declarations found")
    if re.search(r'\boutput\s+"[\w-]+"', content):
        score += 0.3
        evidence.append("Terraform output declarations found")
    if re.search(r'\bterraform\s*\{', content):
        score += 0.4
        evidence.append("Terraform configuration block found")
    if "${var." in content:
        score += 0.3
        evidence.append("Terraform variable references found")
    if "${local." in content:
        score += 0.2
        evidence.append("Terraform local value references found")
    if "aws_" in content or "azurerm_" in content or "google_" in content:
        score += 0.3
        evidence.append("Cloud provider resource references found")
    
    return score, evidence


