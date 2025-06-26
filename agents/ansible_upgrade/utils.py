# agents/ansible_upgrade/utils.py - Minimal Agentic Approach

import uuid
import re
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger("AnsibleAnalysisUtils")

def create_correlation_id(prefix: str = "ansible_analysis") -> str:
    """Create correlation ID for analysis tracking"""
    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    return f"{prefix}_{timestamp}_{uuid.uuid4().hex[:8]}"

class MinimalAnsibleExtractor:
    """
    Minimal extractor that provides ONLY basic facts to the agent.
    The agent does the reasoning and pattern recognition.
    """
    
    def __init__(self):
        # Only the most basic exclusion list (mandatory for parsing)
        self.yaml_keywords = {
            "name", "when", "become", "tags", "vars", "hosts", "tasks", "handlers",
            "notify", "register", "changed_when", "failed_when", "until", "retries",
            "delay", "block", "rescue", "always", "meta", "roles", "gather_facts"
        }

    def extract_basic_patterns(self, content: str) -> Dict[str, Any]:
        """
        Extract only basic syntactic patterns. 
        Let the agent reason about what they mean.
        """
        basic_facts = {
            "content_length": len(content),
            "line_count": len(content.split('\n')),
            "has_yaml_header": content.strip().startswith('---'),
            "module_like_patterns": self._find_module_patterns(content),
            "syntax_patterns": self._find_syntax_patterns(content),
            "structural_patterns": self._find_structural_patterns(content),
            "raw_content_sample": content[:500] + "..." if len(content) > 500 else content
        }
        
        logger.info(f"Extracted basic patterns: {len(basic_facts['module_like_patterns'])} modules, "
                   f"{len(basic_facts['syntax_patterns'])} syntax patterns")
        
        return basic_facts

    def _find_module_patterns(self, content: str) -> List[str]:
        """Find patterns that look like Ansible modules (no interpretation)"""
        module_pattern = r'^\s*-?\s*([a-zA-Z_][a-zA-Z0-9_.]*)\s*:'
        found_patterns = []
        
        for match in re.finditer(module_pattern, content, re.MULTILINE):
            pattern = match.group(1)
            # Only exclude obvious YAML structure keywords
            if pattern not in self.yaml_keywords:
                found_patterns.append(pattern)
        
        return sorted(list(set(found_patterns)))

    def _find_syntax_patterns(self, content: str) -> List[str]:
        """Find syntax patterns without interpreting them"""
        # Look for patterns that might be significant
        pattern_searches = [
            r'with_\w+:',           # with_* patterns
            r'sudo\s*:',            # sudo usage
            r'include\s*:',         # include patterns  
            r'action\s*:',          # action patterns
            r'collections\s*:',     # collections
            r'loop\s*:',            # loop patterns
            r'become\s*:',          # become patterns
        ]
        
        found_patterns = []
        for pattern_regex in pattern_searches:
            matches = re.findall(pattern_regex, content, re.IGNORECASE)
            found_patterns.extend([match.strip().rstrip(':') for match in matches])
        
        return sorted(list(set(found_patterns)))

    def _find_structural_patterns(self, content: str) -> Dict[str, Any]:
        """Find structural patterns without interpretation"""
        return {
            "plays_count": content.count('- hosts:') + content.count('- name:'),
            "tasks_sections": content.count('tasks:'),
            "handlers_sections": content.count('handlers:'),
            "roles_usage": 'roles:' in content,
            "vars_usage": 'vars:' in content or 'vars_files:' in content,
            "conditionals_usage": 'when:' in content,
            "blocks_usage": 'block:' in content,
            "includes_count": content.count('include')
        }

class AgenticAnalysisHelper:
    """
    Helper that provides context to the agent without hardcoded knowledge.
    Just gives the agent tools to reason.
    """
    
    def prepare_analysis_context(self, content: str, filename: str = "playbook.yml") -> Dict[str, Any]:
        """
        Prepare context for the agent to analyze.
        No hardcoded interpretations - just structured facts.
        """
        extractor = MinimalAnsibleExtractor()
        
        context = {
            "filename": filename,
            "analysis_timestamp": datetime.utcnow().isoformat(),
            "basic_patterns": extractor.extract_basic_patterns(content),
            "agent_guidance": {
                "analysis_focus": [
                    "Identify version era from syntax patterns",
                    "Determine which modules lack namespace prefixes", 
                    "Assess deprecated syntax usage",
                    "Evaluate upgrade complexity factors",
                    "Recommend modernization approach"
                ],
                "questions_to_consider": [
                    "What patterns indicate older Ansible versions?",
                    "Which modules should use fully-qualified names?",
                    "What syntax patterns are deprecated in modern Ansible?",
                    "How complex would modernization be?",
                    "What's the recommended upgrade strategy?"
                ]
            }
        }
        
        logger.info(f"Prepared analysis context for {filename}")
        return context

    def validate_agent_response(self, response: Dict[str, Any], correlation_id: str) -> Dict[str, Any]:
        """
        Minimal validation - just structure checks, no content validation.
        Let the agent be responsible for accuracy.
        """
        validation = {
            "structure_valid": True,
            "missing_fields": [],
            "validation_timestamp": datetime.utcnow().isoformat(),
            "correlation_id": correlation_id
        }
        
        # Only check for required structure, not content accuracy
        required_fields = ["success", "analysis_type"]
        for field in required_fields:
            if field not in response:
                validation["missing_fields"].append(field)
                validation["structure_valid"] = False
        
        return validation

# Utility functions (minimal and focused)

def format_content_for_agent(content: str, max_length: int = 4000) -> str:
    """Format content for agent analysis (handle length limits)"""
    if len(content) <= max_length:
        return content
    
    # If too long, provide structured sample
    lines = content.split('\n')
    total_lines = len(lines)
    
    if total_lines > 100:
        # Sample from beginning, middle, and end
        sample_lines = (
            lines[:30] +
            [f"... [{total_lines - 60} lines omitted] ..."] +
            lines[total_lines//2-15:total_lines//2+15] +
            ["... [content continues] ..."] +
            lines[-30:]
        )
        return '\n'.join(sample_lines)
    else:
        # Just truncate if not too many lines
        return content[:max_length] + f"\n... [truncated from {len(content)} chars]"

def extract_agent_reasoning(agent_response: str) -> Optional[Dict[str, str]]:
    """Extract ReAct reasoning from agent response (if present)"""
    reasoning = {}
    
    # Look for ReAct patterns in the response
    think_pattern = r'THINK:\s*(.*?)(?=ACT:|OBSERVE:|$)'
    act_pattern = r'ACT:\s*(.*?)(?=THINK:|OBSERVE:|$)'
    observe_pattern = r'OBSERVE:\s*(.*?)(?=THINK:|ACT:|$)'
    
    think_match = re.search(think_pattern, agent_response, re.DOTALL | re.IGNORECASE)
    if think_match:
        reasoning["think"] = think_match.group(1).strip()
    
    act_match = re.search(act_pattern, agent_response, re.DOTALL | re.IGNORECASE)
    if act_match:
        reasoning["act"] = act_match.group(1).strip()
    
    observe_match = re.search(observe_pattern, agent_response, re.DOTALL | re.IGNORECASE)
    if observe_match:
        reasoning["observe"] = observe_match.group(1).strip()
    
    return reasoning if reasoning else None

def create_analysis_prompt_context(content: str, filename: str = "playbook.yml") -> Dict[str, Any]:
    """
    Create context for agent prompt - minimal facts, maximum reasoning space.
    """
    helper = AgenticAnalysisHelper()
    
    # Get basic facts (no interpretation)
    context = helper.prepare_analysis_context(content, filename)
    
    # Format for agent consumption
    formatted_context = {
        "ansible_content": format_content_for_agent(content),
        "filename": filename,
        "content_stats": {
            "lines": context["basic_patterns"]["line_count"],
            "length": context["basic_patterns"]["content_length"],
            "has_yaml_header": context["basic_patterns"]["has_yaml_header"]
        },
        "detected_patterns": {
            "modules": context["basic_patterns"]["module_like_patterns"],
            "syntax": context["basic_patterns"]["syntax_patterns"],
            "structure": context["basic_patterns"]["structural_patterns"]
        },
        "agent_instructions": context["agent_guidance"]
    }
    
    return formatted_context