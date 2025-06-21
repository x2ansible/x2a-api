import json
import re
from datetime import datetime
import logging
from typing import Dict, Any, Optional, List

from agents.bladelogic_analysis.response_models import (
    BladeLogicVersionRequirements,
    BladeLogicDependencies,
    BladeLogicFunctionality,
    BladeLogicRecommendations,
    BladeLogicAnalysisMetadata,
    BladeLogicAnalysisResponse,
)

logger = logging.getLogger("BladeLogicAnalysisPostprocessor")
logger.setLevel(logging.INFO)


class BladeLogicAnalysisPostprocessor:
    """
    Enhanced postprocessor for BladeLogic analysis with smart fallbacks
    """

    def __init__(self):
        self.required_sections = [
            "version_requirements",
            "dependencies", 
            "functionality",
            "recommendations"
        ]

    def _extract_actual_bladelogic_operations(self, content: str, object_type: str) -> Dict[str, List[str]]:
        """Extract actual BladeLogic operations from content"""
        operations = {
            "services": [],
            "packages": [],
            "files": [],
            "policies": [],
            "scripts": [],
            "targets": []
        }
        
        # BladeLogic-specific command patterns
        service_patterns = [
            r'blcli\s+service\s+([^\\s]+)',
            r'systemctl\s+(?:start|stop|restart|enable|disable)\s+([\\w\\-\\.]+)',
            r'service\s+([\\w\\-\\.]+)\s+(?:start|stop|restart)',
            r'net\s+(?:start|stop)\s+([\\w\\-\\.]+)',
            r'sc\s+(?:start|stop)\s+([\\w\\-\\.]+)'
        ]
        
        package_patterns = [
            r'blpackage\s+install\s+([^\\s]+)',
            r'depot\s+object\s+([^\\s]+)',
            r'software\s+package\s+["\']([^"\']+)["\']',
            r'msiexec.*["\']([^"\']+\\.msi)["\']',
            r'rpm\s+-[iU]\s+([^\\s]+)',
            r'yum\s+install\s+([^\\s]+)',
            r'apt-get\s+install\s+([^\\s]+)'
        ]
        
        file_patterns = [
            r'blcli\s+file\s+deploy\s+["\']([^"\']+)["\']',
            r'blcli\s+template\s+deploy\s+["\']([^"\']+)["\']',
            r'copyfile\s+["\']([^"\']+)["\']',
            r'echo\s+.*>\s*["\']?([^"\'\\s]+)["\']?',
            r'//*[Cc]opy.*["\']([^"\']+\\.(?:conf|cfg|xml|properties|txt))["\']'
        ]
        
        policy_patterns = [
            r'blpolicy\s+([^\\s]+)',
            r'compliance\s+policy\s+["\']([^"\']+)["\']',
            r'audit\s+policy\s+["\']([^"\']+)["\']',
            r'security\s+policy\s+["\']([^"\']+)["\']'
        ]
        
        script_patterns = [
            r'nexec\s+-f\s+["\']([^"\']+\\.(?:sh|nsh|bat|ps1))["\']',
            r'blcli_execute\s+["\']([^"\']+)["\']',
            r'script\s+execute\s+["\']([^"\']+)["\']'
        ]
        
        target_patterns = [
            r'target\s+server\s+([^\\s]+)',
            r'server\s+group\s+["\']([^"\']+)["\']',
            r'host\s*:\s*([^\\s,]+)',
            r'ServerName\s*=\s*["\']?([^"\'\\s]+)["\']?'
        ]
        
        # Extract operations
        for pattern in service_patterns:
            operations["services"].extend(re.findall(pattern, content, re.IGNORECASE))
        
        for pattern in package_patterns:
            operations["packages"].extend(re.findall(pattern, content, re.IGNORECASE))
        
        for pattern in file_patterns:
            operations["files"].extend(re.findall(pattern, content, re.IGNORECASE))
        
        for pattern in policy_patterns:
            operations["policies"].extend(re.findall(pattern, content, re.IGNORECASE))
        
        for pattern in script_patterns:
            operations["scripts"].extend(re.findall(pattern, content, re.IGNORECASE))
        
        for pattern in target_patterns:
            operations["targets"].extend(re.findall(pattern, content, re.IGNORECASE))
        
        # Clean and deduplicate
        for key in operations:
            operations[key] = list(dict.fromkeys([
                op.strip().replace('"', '').replace("'", '') 
                for op in operations[key] if op.strip()
            ]))[:15]  # Limit results
        
        return operations

    def _determine_bladelogic_complexity(self, content: str, operations: Dict[str, List[str]]) -> str:
        """Determine complexity level based on BladeLogic content"""
        complexity_score = 0
        
        # Count operations
        total_operations = sum(len(ops) for ops in operations.values())
        complexity_score += total_operations
        
        # Check for advanced BladeLogic features
        advanced_patterns = [
            r'blcli\s+workflow',
            r'compliance\s+scan',
            r'patch\s+catalog',
            r'custom\s+property',
            r'role\s+based',
            r'approval\s+process',
            r'notification\s+template',
            r'scheduled\s+job'
        ]
        
        for pattern in advanced_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                complexity_score += 3
        
        # Check for multiple file types
        file_types = len(set(re.findall(r'\\.([a-zA-Z0-9]+)', content)))
        complexity_score += file_types
        
        # Determine complexity level
        if complexity_score >= 20:
            return "High"
        elif complexity_score >= 10:
            return "Medium"
        else:
            return "Low"

    def _determine_automation_type(self, content: str, operations: Dict[str, List[str]]) -> str:
        """Determine the primary automation type"""
        content_lower = content.lower()
        
        # Prioritized automation type detection
        automation_indicators = {
            "COMPLIANCE": [
                "compliance", "audit", "policy", "security", "hardening", 
                "baseline", "vulnerability", "cis", "stig"
            ],
            "PATCHING": [
                "patch", "update", "hotfix", "security update", "kb", 
                "windows update", "yum update", "apt upgrade"
            ],
            "DEPLOYMENT": [
                "deploy", "install", "software package", "application", 
                "msi", "rpm", "installer", "setup"
            ],
            "CONFIGURATION": [
                "config", "template", "properties", "setting", "parameter",
                "environment", "registry", "service config"
            ],
            "MONITORING": [
                "monitor", "alert", "notification", "health check", 
                "performance", "log", "metric"
            ]
        }
        
        type_scores = {}
        for auto_type, indicators in automation_indicators.items():
            score = sum(1 for indicator in indicators if indicator in content_lower)
            if operations.get("policies"):
                score += 2 if auto_type == "COMPLIANCE" else 0
            if operations.get("packages"):
                score += 2 if auto_type in ["DEPLOYMENT", "PATCHING"] else 0
            type_scores[auto_type] = score
        
        return max(type_scores.items(), key=lambda x: x[1])[0] if any(type_scores.values()) else "CONFIGURATION"

    def _get_bladelogic_fallback_defaults(self, content: str, object_type: str) -> Dict[str, Any]:
        """Get BladeLogic-specific fallback defaults"""
        operations = self._extract_actual_bladelogic_operations(content, object_type)
        complexity = self._determine_bladelogic_complexity(content, operations)
        automation_type = self._determine_automation_type(content, operations)
        
        # Determine migration effort based on complexity and type
        if complexity == "High" or automation_type == "COMPLIANCE":
            migration_effort = "HIGH"
            estimated_hours = 24.0
        elif complexity == "Medium" or automation_type == "PATCHING":
            migration_effort = "MEDIUM" 
            estimated_hours = 12.0
        else:
            migration_effort = "LOW"
            estimated_hours = 6.0
        
        # Determine primary purpose
        if operations["services"] and operations["packages"]:
            primary_purpose = f"{automation_type.title()} automation for {len(operations['services'])} services and {len(operations['packages'])} packages"
        elif operations["services"]:
            primary_purpose = f"Service management and {automation_type.lower()} for {', '.join(operations['services'][:3])}"
        elif operations["packages"]:
            primary_purpose = f"Package {automation_type.lower()} for {', '.join(operations['packages'][:3])}"
        elif operations["policies"]:
            primary_purpose = f"Compliance policy enforcement: {', '.join(operations['policies'][:3])}"
        else:
            primary_purpose = f"BladeLogic {automation_type.lower()} automation"
        
        # Determine if composite (like wrapper cookbooks)
        is_composite = bool(
            re.search(r'blcli.*job.*execute', content, re.IGNORECASE) or
            len(operations.get("scripts", [])) > 2 or
            "workflow" in content.lower()
        )
        
        return {
            "min_bladelogic_version": "8.6",  # Common enterprise version
            "min_nsh_version": "8.6",
            "migration_effort": migration_effort,
            "estimated_hours": estimated_hours,
            "complexity": complexity,
            "automation_type": automation_type,
            "primary_purpose": primary_purpose,
            "is_composite": is_composite,
            "services": operations["services"],
            "packages": operations["packages"],
            "files": operations["files"],
            "policies": operations["policies"],
            "scripts": operations["scripts"],
            "targets": operations["targets"],
            "object_type": object_type
        }

    def extract_and_validate_analysis(self, raw_response: str, correlation_id: str, bladelogic_content: str = "", object_type: str = "JOB") -> Dict[str, Any]:
        """Enhanced extraction for BladeLogic analysis"""
        logger.info(f"[{correlation_id}] ═══ Starting BladeLogic analysis postprocessing ═══")
        logger.info(f"[{correlation_id}] Raw response length: {len(raw_response)} characters")
        logger.info(f"[{correlation_id}] Object type: {object_type}")
        
        # Get BladeLogic-specific fallback defaults
        fallback_defaults = self._get_bladelogic_fallback_defaults(bladelogic_content, object_type)
        logger.info(f"[{correlation_id}] Fallback defaults prepared for {object_type}")

        # Extract JSON from response
        if isinstance(raw_response, dict):
            parsed = raw_response
            logger.info(f"[{correlation_id}] ✓ Input was already a dict")
        else:
            parsed = self._extract_json_from_text(raw_response, correlation_id)
        
        if not parsed:
            logger.warning(f"[{correlation_id}] ⚠️ No JSON extracted from LLM, using complete fallback")
            result = self._make_complete_bladelogic_response({}, correlation_id, "unknown", object_type, fallback_defaults)
            return result

        logger.info(f"[{correlation_id}] ✓ LLM provided JSON with keys: {list(parsed.keys())}")

        # Extract object name
        object_name = parsed.get("object_name", fallback_defaults.get("object_name", "unknown"))
        
        # Ensure required sections exist
        for section in self.required_sections:
            if section not in parsed:
                parsed[section] = {}

        # Fill missing fields with BladeLogic-specific defaults
        parsed = self._fill_bladelogic_missing_fields(parsed, fallback_defaults, correlation_id)

        # Add metadata
        parsed["metadata"] = {
            "analyzed_at": datetime.utcnow().isoformat(),
            "agent_version": "1.0.0",
            "correlation_id": correlation_id
        }
        parsed["success"] = True
        parsed["object_name"] = object_name
        parsed["object_type"] = object_type

        # Validate using Pydantic
        try:
            response = BladeLogicAnalysisResponse(**parsed)
            logger.info(f"[{correlation_id}] ✓ BladeLogic analysis validated successfully")
            return response.dict()
        except Exception as e:
            logger.error(f"[{correlation_id}]  Pydantic validation failed: {e}")
            result = self._make_complete_bladelogic_response(parsed, correlation_id, object_name, object_type, fallback_defaults, error=str(e))
            return result

    def _fill_bladelogic_missing_fields(self, parsed: Dict[str, Any], fallback_defaults: Dict[str, Any], correlation_id: str) -> Dict[str, Any]:
        """Fill missing fields with BladeLogic-specific values"""
        logger.info(f"[{correlation_id}] ═══ FILLING BLADELOGIC MISSING FIELDS ═══")
        
        # Version requirements
        vr = parsed.get("version_requirements", {})
        if not vr.get("min_bladelogic_version"):
            vr["min_bladelogic_version"] = fallback_defaults["min_bladelogic_version"]
        if not vr.get("min_nsh_version"):
            vr["min_nsh_version"] = fallback_defaults["min_nsh_version"]
        if not vr.get("migration_effort"):
            vr["migration_effort"] = fallback_defaults["migration_effort"]
        if not vr.get("estimated_hours"):
            vr["estimated_hours"] = fallback_defaults["estimated_hours"]
        if not vr.get("deprecated_features"):
            vr["deprecated_features"] = []

        # Dependencies
        deps = parsed.get("dependencies", {})
        if deps.get("is_composite") is None:
            deps["is_composite"] = fallback_defaults["is_composite"]
        if not deps.get("composite_jobs"):
            deps["composite_jobs"] = []
        if not deps.get("package_dependencies"):
            deps["package_dependencies"] = fallback_defaults["packages"]
        if not deps.get("policy_dependencies"):
            deps["policy_dependencies"] = fallback_defaults["policies"]
        if not deps.get("external_scripts"):
            deps["external_scripts"] = fallback_defaults["scripts"]
        if not deps.get("circular_risk"):
            deps["circular_risk"] = "low" if not fallback_defaults["is_composite"] else "medium"

        # Functionality
        func = parsed.get("functionality", {})
        if not func.get("primary_purpose"):
            func["primary_purpose"] = fallback_defaults["primary_purpose"]
        if not func.get("automation_type"):
            func["automation_type"] = fallback_defaults["automation_type"]
        if not func.get("target_platforms"):
            func["target_platforms"] = ["Windows", "Linux"]  # Common defaults
        if not func.get("managed_services"):
            func["managed_services"] = fallback_defaults["services"]
        if not func.get("managed_packages"):
            func["managed_packages"] = fallback_defaults["packages"]
        if not func.get("managed_files"):
            func["managed_files"] = fallback_defaults["files"]
        if not func.get("compliance_policies"):
            func["compliance_policies"] = fallback_defaults["policies"]
        if not func.get("reusability"):
            func["reusability"] = "HIGH" if not fallback_defaults["is_composite"] else "MEDIUM"
        if not func.get("customization_points"):
            func["customization_points"] = ["target servers", "parameters", "schedules"]

        # Recommendations
        recs = parsed.get("recommendations", {})
        if not recs.get("consolidation_action"):
            if fallback_defaults["automation_type"] == "COMPLIANCE":
                recs["consolidation_action"] = "MODERNIZE"
            elif fallback_defaults["is_composite"]:
                recs["consolidation_action"] = "EXTEND"
            else:
                recs["consolidation_action"] = "REUSE"
        if not recs.get("rationale"):
            recs["rationale"] = f"BladeLogic {fallback_defaults['automation_type'].lower()} automation with {fallback_defaults['complexity'].lower()} complexity"
        if not recs.get("migration_priority"):
            recs["migration_priority"] = "HIGH" if fallback_defaults["automation_type"] == "COMPLIANCE" else "MEDIUM"
        if not recs.get("risk_factors"):
            recs["risk_factors"] = []
        if not recs.get("ansible_equivalent"):
            equivalents = {
                "COMPLIANCE": "ansible-hardening + custom compliance modules",
                "PATCHING": "ansible.posix.patch + yum/apt modules",
                "DEPLOYMENT": "ansible.builtin package modules + custom deployment playbooks",
                "CONFIGURATION": "ansible.builtin template + file modules",
                "MONITORING": "ansible monitoring roles + custom notification modules"
            }
            recs["ansible_equivalent"] = equivalents.get(fallback_defaults["automation_type"], "Custom Ansible playbooks")

        # Additional fields
        if not parsed.get("detailed_analysis"):
            parsed["detailed_analysis"] = f"BladeLogic {fallback_defaults['object_type']} performing {fallback_defaults['automation_type'].lower()} automation with {fallback_defaults['complexity'].lower()} complexity"
        
        if not parsed.get("key_operations"):
            key_ops = []
            if fallback_defaults["services"]:
                key_ops.append("Service management")
            if fallback_defaults["packages"]:
                key_ops.append("Package management")
            if fallback_defaults["policies"]:
                key_ops.append("Policy enforcement")
            if fallback_defaults["files"]:
                key_ops.append("File management")
            parsed["key_operations"] = key_ops or ["System automation"]

        if not parsed.get("automation_details"):
            parsed["automation_details"] = f"{fallback_defaults['automation_type']} automation targeting {len(fallback_defaults['targets']) or 'multiple'} servers"
        
        if not parsed.get("complexity_level"):
            parsed["complexity_level"] = fallback_defaults["complexity"]
        
        if parsed.get("convertible") is None:
            # BladeLogic to Ansible conversion assessment
            parsed["convertible"] = fallback_defaults["automation_type"] in ["CONFIGURATION", "DEPLOYMENT"]
        
        if not parsed.get("conversion_notes"):
            notes = f"BladeLogic {fallback_defaults['object_type']} can be converted to Ansible using {recs.get('ansible_equivalent', 'custom modules')} with {fallback_defaults['migration_effort'].lower()} effort"
            parsed["conversion_notes"] = notes

        return parsed

    def _extract_json_from_text(self, text: str, correlation_id: str) -> Dict[str, Any]:
        """Extract JSON from text with multiple strategies"""
        logger.debug(f"[{correlation_id}] Attempting to extract JSON from LLM response")
        
        if not text or not text.strip():
            logger.warning(f"[{correlation_id}] Empty response from LLM")
            return {}

        # Try direct JSON parsing first
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass

        # Try to find JSON in code blocks or text
        json_patterns = [
            r'```json\\s*(\\{.*?\\})\\s*```',
            r'```\\s*(\\{.*?\\})\\s*```',
            r'(\\{[^{}]*\\{[^{}]*\\}[^{}]*\\})',
            r'(\\{.*?\\})'
        ]
        
        for pattern in json_patterns:
            matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
            for match in matches:
                try:
                    cleaned = re.sub(r',\\s*([}\\]])', r'\\1', match)
                    return json.loads(cleaned)
                except json.JSONDecodeError:
                    continue

        logger.warning(f"[{correlation_id}] Could not extract valid JSON from LLM response")
        return {}

    def _make_complete_bladelogic_response(
        self, 
        parsed: Dict[str, Any], 
        correlation_id: str, 
        object_name: str,
        object_type: str,
        fallback_defaults: Dict[str, Any],
        error: str = "Postprocessing failed"
    ) -> Dict[str, Any]:
        """Create complete BladeLogic response"""
        logger.info(f"[{correlation_id}] Creating complete BladeLogic response")
        
        now = datetime.utcnow().isoformat()
        
        return {
            "success": error == "Postprocessing failed",
            "object_name": object_name or "unknown",
            "object_type": object_type,
            "version_requirements": {
                "min_bladelogic_version": fallback_defaults["min_bladelogic_version"],
                "min_nsh_version": fallback_defaults["min_nsh_version"],
                "migration_effort": fallback_defaults["migration_effort"],
                "estimated_hours": fallback_defaults["estimated_hours"],
                "deprecated_features": []
            },
            "dependencies": {
                "is_composite": fallback_defaults["is_composite"],
                "composite_jobs": [],
                "package_dependencies": fallback_defaults["packages"],
                "policy_dependencies": fallback_defaults["policies"],
                "external_scripts": fallback_defaults["scripts"],
                "circular_risk": "low"
            },
            "functionality": {
                "primary_purpose": fallback_defaults["primary_purpose"],
                "automation_type": fallback_defaults["automation_type"],
                "target_platforms": ["Windows", "Linux"],
                "managed_services": fallback_defaults["services"],
                "managed_packages": fallback_defaults["packages"],
                "managed_files": fallback_defaults["files"],
                "compliance_policies": fallback_defaults["policies"],
                "reusability": "MEDIUM",
                "customization_points": ["target servers", "parameters"]
            },
            "recommendations": {
                "consolidation_action": "MODERNIZE",
                "rationale": fallback_defaults["primary_purpose"],
                "migration_priority": "MEDIUM",
                "risk_factors": [],
                "ansible_equivalent": "Custom Ansible playbooks"
            },
            "metadata": {
                "analyzed_at": now,
                "agent_version": "1.0.0",
                "correlation_id": correlation_id
            },
            "detailed_analysis": fallback_defaults["primary_purpose"],
            "key_operations": ["System automation"],
            "automation_details": f"{fallback_defaults['automation_type']} automation",
            "complexity_level": fallback_defaults["complexity"],
            "convertible": True,
            "conversion_notes": f"BladeLogic {object_type} conversion with {fallback_defaults['migration_effort'].lower()} effort",
            "confidence_source": "bladelogic_semantic_analysis",
            "postprocess_error": error if error != "Postprocessing failed" else None
        }


# Module-level function
def extract_and_validate_analysis(raw_response: str, correlation_id: Optional[str] = None, bladelogic_content: str = "", object_type: str = "JOB") -> Dict[str, Any]:
    """Entry point for BladeLogic analysis postprocessing"""
    if correlation_id is None:
        correlation_id = f"bl_corr_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    return BladeLogicAnalysisPostprocessor().extract_and_validate_analysis(raw_response, correlation_id, bladelogic_content, object_type)