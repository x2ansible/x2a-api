import json
import re
from datetime import datetime
import logging
from typing import Dict, Any, Optional, List

from agents.shell_analysis.response_models import (
    ShellVersionRequirements,
    ShellDependencies,
    ShellFunctionality,
    ShellRecommendations,
    ShellAnalysisMetadata,
    ShellAnalysisResponse,
)

logger = logging.getLogger("ShellAnalysisPostprocessor")

class ShellAnalysisPostprocessor:
    """Postprocessor for shell script analysis with smart fallbacks"""

    def __init__(self):
        self.required_sections = [
            "version_requirements",
            "dependencies", 
            "functionality",
            "recommendations"
        ]

    def _determine_shell_complexity(self, content: str, operations: Dict[str, List[str]]) -> str:
        """Determine complexity level based on shell script content"""
        complexity_score = 0
        
        # Count operations
        total_operations = sum(len(ops) for ops in operations.values())
        complexity_score += total_operations
        
        # Check for advanced shell features
        advanced_patterns = [
            r'function\s+\w+',
            r'case\s+.*\s+in',
            r'while\s+.*\s+do',
            r'for\s+.*\s+in',
            r'if\s+.*\s+then',
            r'source\s+',
            r'\$\([^)]+\)',  # command substitution
            r'trap\s+',
            r'exec\s+'
        ]
        
        for pattern in advanced_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                complexity_score += 2
        
        # Check for external dependencies
        if operations["packages"] or operations["network"]:
            complexity_score += 3
        
        # Determine complexity level
        if complexity_score >= 15:
            return "High"
        elif complexity_score >= 8:
            return "Medium"
        else:
            return "Low"

    def _determine_script_purpose(self, content: str, operations: Dict[str, List[str]]) -> str:
        """Determine the primary script purpose"""
        content_lower = content.lower()
        
        purpose_indicators = {
            "INSTALLATION": [
                "install", "setup", "apt-get", "yum", "pip install", "npm install"
            ],
            "DEPLOYMENT": [
                "deploy", "start", "systemctl", "docker run", "launch"
            ],
            "CONFIGURATION": [
                "config", "configure", "settings", "environment", "export"
            ],
            "MONITORING": [
                "monitor", "check", "health", "status", "ps aux", "netstat"
            ],
            "MAINTENANCE": [
                "backup", "cleanup", "maintenance", "cron", "archive"
            ]
        }
        
        type_scores = {}
        for purpose_type, indicators in purpose_indicators.items():
            score = sum(1 for indicator in indicators if indicator in content_lower)
            if operations.get("packages"):
                score += 2 if purpose_type == "INSTALLATION" else 0
            if operations.get("services"):
                score += 2 if purpose_type == "DEPLOYMENT" else 0
            type_scores[purpose_type] = score
        
        return max(type_scores.items(), key=lambda x: x[1])[0] if any(type_scores.values()) else "CONFIGURATION"

    def extract_and_validate_analysis(self, raw_response: str, correlation_id: str, shell_content: str = "", script_type: str = "SCRIPT") -> Dict[str, Any]:
        """Enhanced extraction for shell script analysis"""
        logger.info(f"[{correlation_id}] Starting shell script analysis postprocessing")
        
        # Extract JSON from response
        if isinstance(raw_response, dict):
            parsed = raw_response
        else:
            parsed = self._extract_json_from_text(raw_response, correlation_id)
        
        if not parsed:
            logger.warning(f"[{correlation_id}] No JSON extracted, using fallback")
            return self._create_fallback_response(shell_content, script_type, correlation_id)

        # Ensure required sections exist
        for section in self.required_sections:
            if section not in parsed:
                parsed[section] = {}

        # Fill missing fields with shell-specific defaults
        parsed = self._fill_shell_missing_fields(parsed, shell_content, script_type, correlation_id)

        # Add metadata
        parsed["metadata"] = {
            "analyzed_at": datetime.utcnow().isoformat(),
            "agent_version": "1.0.0",
            "correlation_id": correlation_id
        }
        parsed["success"] = True
        parsed["script_name"] = parsed.get("script_name", "unknown")
        parsed["script_type"] = script_type

        # Validate using Pydantic
        try:
            response = ShellAnalysisResponse(**parsed)
            logger.info(f"[{correlation_id}] Shell analysis validated successfully")
            return response.dict()
        except Exception as e:
            logger.error(f"[{correlation_id}] Pydantic validation failed: {e}")
            return self._create_fallback_response(shell_content, script_type, correlation_id)

    def _fill_shell_missing_fields(self, parsed: Dict[str, Any], shell_content: str, script_type: str, correlation_id: str) -> Dict[str, Any]:
        """Fill missing fields with shell-specific values"""
        from agents.shell_analysis.utils import ShellExtractor
        
        extractor = ShellExtractor()
        operations = extractor.extract_shell_operations(shell_content, script_type)
        complexity = self._determine_shell_complexity(shell_content, operations)
        purpose = self._determine_script_purpose(shell_content, operations)
        
        # Version requirements
        vr = parsed.get("version_requirements", {})
        if not vr.get("shell_type"):
            vr["shell_type"] = script_type.split('_')[0] if '_' in script_type else 'bash'
        if not vr.get("min_shell_version"):
            vr["min_shell_version"] = "4.0" if vr["shell_type"] == "bash" else "3.0"
        if not vr.get("migration_effort"):
            vr["migration_effort"] = "HIGH" if complexity == "High" else "MEDIUM" if complexity == "Medium" else "LOW"
        if not vr.get("estimated_hours"):
            vr["estimated_hours"] = 16.0 if complexity == "High" else 8.0 if complexity == "Medium" else 4.0

        # Dependencies
        deps = parsed.get("dependencies", {})
        if not deps.get("system_packages"):
            deps["system_packages"] = operations["packages"]
        if not deps.get("external_commands"):
            deps["external_commands"] = operations["commands"]
        if not deps.get("file_dependencies"):
            deps["file_dependencies"] = operations["files"]
        if not deps.get("service_dependencies"):
            deps["service_dependencies"] = operations["services"]

        # Functionality
        func = parsed.get("functionality", {})
        if not func.get("primary_purpose"):
            func["primary_purpose"] = f"Shell script for {purpose.lower()} automation"
        if not func.get("script_type"):
            func["script_type"] = purpose
        if not func.get("managed_services"):
            func["managed_services"] = operations["services"]
        if not func.get("managed_packages"):
            func["managed_packages"] = operations["packages"]

        # Recommendations
        recs = parsed.get("recommendations", {})
        if not recs.get("conversion_action"):
            recs["conversion_action"] = "MODERNIZE" if complexity == "High" else "REUSE"
        if not recs.get("ansible_equivalent"):
            ansible_map = {
                "INSTALLATION": "ansible.builtin.package + custom installation tasks",
                "DEPLOYMENT": "ansible.builtin.systemd + deployment playbooks",
                "CONFIGURATION": "ansible.builtin.template + configuration modules",
                "MONITORING": "ansible monitoring roles + custom checks",
                "MAINTENANCE": "ansible.posix.cron + maintenance playbooks"
            }
            recs["ansible_equivalent"] = ansible_map.get(purpose, "Custom Ansible playbooks")

        return parsed

    def _extract_json_from_text(self, text: str, correlation_id: str) -> Dict[str, Any]:
        """Extract JSON from text with multiple strategies"""
        if not text or not text.strip():
            return {}

        # Try direct JSON parsing first
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass

        # Try to find JSON in code blocks
        json_patterns = [
            r'```json\s*(\{.*?\})\s*```',
            r'```\s*(\{.*?\})\s*```',
            r'(\{[^{}]*\{[^{}]*\}[^{}]*\})',
            r'(\{.*?\})'
        ]
        
        for pattern in json_patterns:
            matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
            for match in matches:
                try:
                    return json.loads(match)
                except json.JSONDecodeError:
                    continue

        return {}

    def _create_fallback_response(self, shell_content: str, script_type: str, correlation_id: str) -> Dict[str, Any]:
        """Create fallback shell analysis response"""
        from agents.shell_analysis.utils import ShellExtractor
        
        extractor = ShellExtractor()
        operations = extractor.extract_shell_operations(shell_content, script_type)
        complexity = self._determine_shell_complexity(shell_content, operations)
        purpose = self._determine_script_purpose(shell_content, operations)
        
        return {
            "success": True,
            "script_name": "unknown",
            "script_type": script_type,
            "version_requirements": {
                "shell_type": script_type.split('_')[0] if '_' in script_type else 'bash',
                "min_shell_version": "4.0",
                "migration_effort": "MEDIUM",
                "estimated_hours": 8.0,
                "deprecated_features": []
            },
            "dependencies": {
                "system_packages": operations["packages"],
                "external_commands": operations["commands"],
                "file_dependencies": operations["files"],
                "service_dependencies": operations["services"],
                "circular_risk": "low"
            },
            "functionality": {
                "primary_purpose": f"Shell script for {purpose.lower()} automation",
                "script_type": purpose,
                "target_platforms": ["Linux", "Unix"],
                "managed_services": operations["services"],
                "managed_packages": operations["packages"],
                "configuration_files": operations["files"],
                "key_operations": list(operations.keys()),
                "reusability": "MEDIUM"
            },
            "recommendations": {
                "conversion_action": "MODERNIZE",
                "rationale": f"Shell script with {complexity.lower()} complexity",
                "migration_priority": "MEDIUM",
                "risk_factors": ["Shell dependency", "Platform-specific commands"],
                "ansible_equivalent": "Custom Ansible playbooks"
            },
            "metadata": {
                "analyzed_at": datetime.utcnow().isoformat(),
                "agent_version": "1.0.0",
                "correlation_id": correlation_id
            },
            "detailed_analysis": f"Shell script performing {purpose.lower()} automation with {complexity.lower()} complexity",
            "complexity_level": complexity,
            "convertible": True,
            "conversion_notes": f"Shell script can be converted to Ansible with {complexity.lower()} effort",
            "confidence_source": "shell_semantic_analysis"
        }


# Module-level function
def extract_and_validate_analysis(raw_response: str, correlation_id: Optional[str] = None, shell_content: str = "", script_type: str = "SCRIPT") -> Dict[str, Any]:
    """Entry point for shell script analysis postprocessing"""
    if correlation_id is None:
        correlation_id = f"shell_corr_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    return ShellAnalysisPostprocessor().extract_and_validate_analysis(raw_response, correlation_id, shell_content, script_type)