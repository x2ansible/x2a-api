import json
import re
from datetime import datetime
import logging
from typing import Dict, Any, Optional, List

from agents.chef_analysis.response_models import (
    VersionRequirements,
    Dependencies,
    Functionality,
    Recommendations,
    AnalysisMetadata,
    CookbookAnalysisResponse,
)

logger = logging.getLogger("ChefAnalysisPostprocessor")
logger.setLevel(logging.INFO)


class ChefAnalysisPostprocessor:
    """
    Enhanced postprocessor that uses LLM analysis with smart fallbacks only when needed
    """

    def __init__(self):
        self.required_sections = [
            "version_requirements",
            "dependencies",
            "functionality",
            "recommendations"
        ]

    def _extract_actual_file_paths(self, cookbook_content: str) -> List[str]:
        """Extract actual file paths from cookbook content - only used as fallback"""
        file_paths = []
        
        path_patterns = [
            r'path\s+["\']([^"\']+)["\']',
            r'destination\s+["\']([^"\']+)["\']',
            r'source\s+["\']([^"\']+)["\']',
            r'"/[^"]*\.conf"',
            r"'/[^']*\.conf'",
        ]
        
        for pattern in path_patterns:
            matches = re.findall(pattern, cookbook_content, re.IGNORECASE)
            file_paths.extend(matches)
        
        unique_paths = list(set([path for path in file_paths if path.startswith('/') and len(path) > 1]))
        return unique_paths[:10]

    def _extract_actual_packages(self, cookbook_content: str) -> List[str]:
        """Extract actual package names - only used as fallback"""
        packages = []
        
        package_patterns = [
            r'package\s+["\']([^"\']+)["\']',
            r'package_name\s+["\']([^"\']+)["\']',
            r'package\s+(\w+)\s+do',
        ]
        
        for pattern in package_patterns:
            matches = re.findall(pattern, cookbook_content, re.IGNORECASE)
            packages.extend(matches)
        
        # Technology-specific detection as fallback only
        content_lower = cookbook_content.lower()
        if "nginx" in content_lower:
            packages.append("nginx")
        if "apache" in content_lower or "httpd" in content_lower:
            packages.extend(["apache2", "httpd"])
        if "mysql" in content_lower:
            packages.append("mysql-server")
        if "postgresql" in content_lower:
            packages.append("postgresql")
        if "docker" in content_lower:
            packages.append("docker")
        
        return list(set(packages))

    def _extract_actual_services(self, cookbook_content: str) -> List[str]:
        """Extract actual service names - only used as fallback"""
        services = []
        
        service_patterns = [
            r'service\s+["\']([^"\']+)["\']',
            r'service_name\s+["\']([^"\']+)["\']',
            r'service\s+(\w+)\s+do',
        ]
        
        for pattern in service_patterns:
            matches = re.findall(pattern, cookbook_content, re.IGNORECASE)
            services.extend(matches)
        
        return list(set(services))

    def _get_minimal_fallback_defaults(self, cookbook_content: str) -> Dict[str, Any]:
        """Get minimal fallback defaults only when LLM completely fails"""
        
        # Only extract what we absolutely need for fallback
        actual_packages = self._extract_actual_packages(cookbook_content)
        actual_services = self._extract_actual_services(cookbook_content)
        actual_file_paths = self._extract_actual_file_paths(cookbook_content)
        
        # Very conservative defaults - only use when LLM provides nothing
        content_lower = cookbook_content.lower()
        lines = cookbook_content.split('\n')
        code_lines = len([line for line in lines if line.strip() and not line.strip().startswith('#')])
        file_count = len(cookbook_content.split('===')) - 1 if '===' in cookbook_content else 1
        
        # Simple purpose detection
        if "nginx" in content_lower:
            primary_purpose = "Nginx web server configuration"
        elif any(term in content_lower for term in ["apache", "httpd"]):
            primary_purpose = "Apache web server configuration"
        else:
            primary_purpose = "System configuration and management"
        
        # Very simple complexity - only 3 levels
        if code_lines <= 50:
            complexity = "Low"
            estimated_hours = 2.0
        elif code_lines <= 150:
            complexity = "Medium"
            estimated_hours = 8.0
        else:
            complexity = "High"
            estimated_hours = 16.0
        
        return {
            "min_chef_version": "12.0",  # Very conservative
            "min_ruby_version": "2.0",   # Very conservative
            "migration_effort": "MEDIUM",
            "estimated_hours": estimated_hours,
            "complexity": complexity,
            "primary_purpose": primary_purpose,
            "services": actual_services,
            "packages": actual_packages,
            "files_managed": actual_file_paths,
            "is_wrapper": "include_recipe" in content_lower and not any(term in content_lower for term in ["package", "service", "file", "template"]),
            "file_count": file_count,
            "code_lines": code_lines
        }

    def extract_and_validate_analysis(self, raw_response: str, correlation_id: str, cookbook_content: str = "") -> Dict[str, Any]:
        """
        Enhanced extraction that uses LLM analysis with minimal fallbacks
        """
        logger.info(f"[{correlation_id}] ═══ Starting enhanced postprocessing ═══")
        logger.info(f"[{correlation_id}] Raw response length: {len(raw_response)} characters")
        
        # Log first 300 chars of raw response for debugging
        if raw_response:
            preview = raw_response[:300].replace('\n', '\\n')
            logger.info(f"[{correlation_id}] Raw response preview: {preview}...")

        # Get minimal fallback defaults (only used if LLM completely fails)
        fallback_defaults = self._get_minimal_fallback_defaults(cookbook_content)
        logger.info(f"[{correlation_id}] Fallback defaults prepared: chef_ver={fallback_defaults['min_chef_version']}, complexity={fallback_defaults['complexity']}")

        # 1. Try to extract JSON from the response
        if isinstance(raw_response, dict):
            parsed = raw_response
            logger.info(f"[{correlation_id}] ✓ Input was already a dict")
        else:
            parsed = self._extract_json_from_text(raw_response, correlation_id)
        
        # 2. Check if we got valid JSON from LLM
        if not parsed:
            logger.warning(f"[{correlation_id}]  No JSON extracted from LLM, using COMPLETE FALLBACK")
            result = self._make_complete_response({}, correlation_id, "unknown", fallback_defaults)
            self._log_final_response_source(correlation_id, "COMPLETE_FALLBACK", result)
            return result

        logger.info(f"[{correlation_id}] ✓ LLM provided JSON with keys: {list(parsed.keys())}")

        # Log what the LLM actually provided
        self._log_llm_provided_values(correlation_id, parsed)

        # 3. Extract cookbook name
        cookbook_name = parsed.get("cookbook_name", "unknown")
        
        # 4. Ensure all required sections exist - but keep LLM values when present
        if "version_requirements" not in parsed:
            parsed["version_requirements"] = {}
        if "dependencies" not in parsed:
            parsed["dependencies"] = {}
        if "functionality" not in parsed:
            parsed["functionality"] = {}
        if "recommendations" not in parsed:
            parsed["recommendations"] = {}

        # 5. Fill missing fields only, preserve LLM analysis
        parsed = self._fill_missing_fields_only(parsed, fallback_defaults, correlation_id)

        # 6. Add metadata
        parsed["metadata"] = {
            "analyzed_at": datetime.utcnow().isoformat(),
            "agent_version": "1.0.0",
            "correlation_id": correlation_id
        }
        parsed["success"] = True
        parsed["cookbook_name"] = cookbook_name

        # 7. Validate using Pydantic
        try:
            response = CookbookAnalysisResponse(**parsed)
            logger.info(f"[{correlation_id}] ✓ Enhanced analysis validated successfully")
            result = response.dict()
            self._log_final_response_source(correlation_id, "LLM_WITH_MINIMAL_FALLBACK", result)
            return result
        except Exception as e:
            logger.error(f"[{correlation_id}]  Pydantic validation failed: {e}")
            result = self._make_complete_response(parsed, correlation_id, cookbook_name, fallback_defaults, error=str(e))
            self._log_final_response_source(correlation_id, "VALIDATION_FALLBACK", result)
            return result

    def _log_llm_provided_values(self, correlation_id: str, parsed: Dict[str, Any]) -> None:
        """Log what values the LLM actually provided"""
        logger.info(f"[{correlation_id}] ═══ LLM PROVIDED VALUES ═══")
        
        # Version requirements
        vr = parsed.get("version_requirements", {})
        if vr:
            logger.info(f"[{correlation_id}] LLM version_requirements:")
            logger.info(f"[{correlation_id}]   min_chef_version: {vr.get('min_chef_version', 'NOT_PROVIDED')}")
            logger.info(f"[{correlation_id}]   min_ruby_version: {vr.get('min_ruby_version', 'NOT_PROVIDED')}")
            logger.info(f"[{correlation_id}]   migration_effort: {vr.get('migration_effort', 'NOT_PROVIDED')}")
            logger.info(f"[{correlation_id}]   estimated_hours: {vr.get('estimated_hours', 'NOT_PROVIDED')}")
        else:
            logger.info(f"[{correlation_id}] LLM version_requirements: NOT_PROVIDED")
        
        # Dependencies
        deps = parsed.get("dependencies", {})
        if deps:
            logger.info(f"[{correlation_id}] LLM dependencies:")
            logger.info(f"[{correlation_id}]   is_wrapper: {deps.get('is_wrapper', 'NOT_PROVIDED')}")
            logger.info(f"[{correlation_id}]   direct_deps: {deps.get('direct_deps', 'NOT_PROVIDED')}")
        else:
            logger.info(f"[{correlation_id}] LLM dependencies: NOT_PROVIDED")
        
        # Functionality  
        func = parsed.get("functionality", {})
        if func:
            logger.info(f"[{correlation_id}] LLM functionality:")
            logger.info(f"[{correlation_id}]   primary_purpose: {func.get('primary_purpose', 'NOT_PROVIDED')}")
            logger.info(f"[{correlation_id}]   services: {func.get('services', 'NOT_PROVIDED')}")
            logger.info(f"[{correlation_id}]   packages: {func.get('packages', 'NOT_PROVIDED')}")
        else:
            logger.info(f"[{correlation_id}] LLM functionality: NOT_PROVIDED")
        
        # Additional fields
        logger.info(f"[{correlation_id}] LLM additional fields:")
        logger.info(f"[{correlation_id}]   complexity_level: {parsed.get('complexity_level', 'NOT_PROVIDED')}")
        logger.info(f"[{correlation_id}]   detailed_analysis: {'PROVIDED' if parsed.get('detailed_analysis') else 'NOT_PROVIDED'}")
        logger.info(f"[{correlation_id}]   key_operations: {parsed.get('key_operations', 'NOT_PROVIDED')}")

    def _log_final_response_source(self, correlation_id: str, source: str, result: Dict[str, Any]) -> None:
        """Log the final response showing what came from LLM vs fallback"""
        logger.info(f"[{correlation_id}] ═══ FINAL RESPONSE SOURCE: {source} ═══")
        
        vr = result.get("version_requirements", {})
        logger.info(f"[{correlation_id}] FINAL min_chef_version: {vr.get('min_chef_version')} (source: {source})")
        logger.info(f"[{correlation_id}] FINAL min_ruby_version: {vr.get('min_ruby_version')} (source: {source})")
        logger.info(f"[{correlation_id}] FINAL migration_effort: {vr.get('migration_effort')} (source: {source})")
        logger.info(f"[{correlation_id}] FINAL estimated_hours: {vr.get('estimated_hours')} (source: {source})")
        
        func = result.get("functionality", {})
        logger.info(f"[{correlation_id}] FINAL primary_purpose: {func.get('primary_purpose')} (source: {source})")
        logger.info(f"[{correlation_id}] FINAL complexity_level: {result.get('complexity_level')} (source: {source})")
        
        if source == "LLM_WITH_MINIMAL_FALLBACK":
            logger.info(f"[{correlation_id}]  SUCCESS: LLM analysis preserved with minimal fallbacks")
        elif source == "COMPLETE_FALLBACK":
            logger.warning(f"[{correlation_id}] ⚠️  FALLBACK: Used complete fallback due to LLM failure")
        elif source == "VALIDATION_FALLBACK":
            logger.warning(f"[{correlation_id}] ⚠️  FALLBACK: Used validation fallback due to Pydantic error")

    def _fill_missing_fields_only(self, parsed: Dict[str, Any], fallback_defaults: Dict[str, Any], correlation_id: str) -> Dict[str, Any]:
        """Fill only missing fields - preserve all LLM analysis values"""
        logger.info(f"[{correlation_id}] ═══ FILLING MISSING FIELDS ═══")
        llm_preserved_count = 0
        fallback_used_count = 0

        # Version requirements - use LLM values when available
        vr = parsed.get("version_requirements", {})
        if not vr.get("min_chef_version"):
            vr["min_chef_version"] = fallback_defaults["min_chef_version"]
            logger.info(f"[{correlation_id}]  FALLBACK min_chef_version: {fallback_defaults['min_chef_version']}")
            fallback_used_count += 1
        else:
            logger.info(f"[{correlation_id}]  LLM min_chef_version: {vr.get('min_chef_version')}")
            llm_preserved_count += 1
            
        if not vr.get("min_ruby_version"):
            vr["min_ruby_version"] = fallback_defaults["min_ruby_version"]
            logger.info(f"[{correlation_id}]  FALLBACK min_ruby_version: {fallback_defaults['min_ruby_version']}")
            fallback_used_count += 1
        else:
            logger.info(f"[{correlation_id}]  LLM min_ruby_version: {vr.get('min_ruby_version')}")
            llm_preserved_count += 1
            
        if not vr.get("migration_effort"):
            vr["migration_effort"] = fallback_defaults["migration_effort"]
            logger.info(f"[{correlation_id}]  FALLBACK migration_effort: {fallback_defaults['migration_effort']}")
            fallback_used_count += 1
        else:
            logger.info(f"[{correlation_id}]  LLM migration_effort: {vr.get('migration_effort')}")
            llm_preserved_count += 1
            
        if not vr.get("estimated_hours"):
            vr["estimated_hours"] = fallback_defaults["estimated_hours"]
            logger.info(f"[{correlation_id}]  FALLBACK estimated_hours: {fallback_defaults['estimated_hours']}")
            fallback_used_count += 1
        else:
            logger.info(f"[{correlation_id}]  LLM estimated_hours: {vr.get('estimated_hours')}")
            llm_preserved_count += 1
            
        if not vr.get("deprecated_features"):
            vr["deprecated_features"] = []

        # Dependencies - use LLM values when available
        deps = parsed.get("dependencies", {})
        if deps.get("is_wrapper") is None:
            deps["is_wrapper"] = fallback_defaults["is_wrapper"]
            logger.info(f"[{correlation_id}]  FALLBACK is_wrapper: {fallback_defaults['is_wrapper']}")
            fallback_used_count += 1
        else:
            logger.info(f"[{correlation_id}]  LLM is_wrapper: {deps.get('is_wrapper')}")
            llm_preserved_count += 1
            
        if not deps.get("wrapped_cookbooks"):
            deps["wrapped_cookbooks"] = []
        if not deps.get("direct_deps"):
            deps["direct_deps"] = fallback_defaults["packages"]
            logger.info(f"[{correlation_id}]  FALLBACK direct_deps: {fallback_defaults['packages']}")
            fallback_used_count += 1
        else:
            logger.info(f"[{correlation_id}]  LLM direct_deps: {deps.get('direct_deps')}")
            llm_preserved_count += 1
            
        if not deps.get("runtime_deps"):
            deps["runtime_deps"] = []
        if not deps.get("circular_risk"):
            deps["circular_risk"] = "none"

        # Functionality - use LLM values when available
        func = parsed.get("functionality", {})
        if not func.get("primary_purpose"):
            func["primary_purpose"] = fallback_defaults["primary_purpose"]
            logger.info(f"[{correlation_id}]  FALLBACK primary_purpose: {fallback_defaults['primary_purpose']}")
            fallback_used_count += 1
        else:
            logger.info(f"[{correlation_id}]  LLM primary_purpose: {func.get('primary_purpose')}")
            llm_preserved_count += 1
            
        if not func.get("services"):
            func["services"] = fallback_defaults["services"]
            logger.info(f"[{correlation_id}]  FALLBACK services: {fallback_defaults['services']}")
            fallback_used_count += 1
        else:
            logger.info(f"[{correlation_id}]  LLM services: {func.get('services')}")
            llm_preserved_count += 1
            
        if not func.get("packages"):
            func["packages"] = fallback_defaults["packages"]
            logger.info(f"[{correlation_id}]  FALLBACK packages: {fallback_defaults['packages']}")
            fallback_used_count += 1
        else:
            logger.info(f"[{correlation_id}]  LLM packages: {func.get('packages')}")
            llm_preserved_count += 1
            
        if not func.get("files_managed"):
            func["files_managed"] = fallback_defaults["files_managed"]
            logger.info(f"[{correlation_id}]  FALLBACK files_managed: {fallback_defaults['files_managed']}")
            fallback_used_count += 1
        else:
            logger.info(f"[{correlation_id}]  LLM files_managed: {func.get('files_managed')}")
            llm_preserved_count += 1
            
        if not func.get("reusability"):
            func["reusability"] = "MEDIUM"
        if not func.get("customization_points"):
            func["customization_points"] = ["configuration files", "service parameters"]

        # Recommendations - use LLM values when available
        recs = parsed.get("recommendations", {})
        if not recs.get("consolidation_action"):
            recs["consolidation_action"] = "EXTEND"
        else:
            logger.info(f"[{correlation_id}]  LLM consolidation_action: {recs.get('consolidation_action')}")
            llm_preserved_count += 1
            
        if not recs.get("rationale"):
            recs["rationale"] = f"Analysis shows {fallback_defaults['primary_purpose'].lower()} with {fallback_defaults['complexity'].lower()} complexity"
            logger.info(f"[{correlation_id}]  FALLBACK rationale: (generated)")
            fallback_used_count += 1
        else:
            logger.info(f"[{correlation_id}]  LLM rationale: {recs.get('rationale')[:50]}...")
            llm_preserved_count += 1
            
        if not recs.get("migration_priority"):
            recs["migration_priority"] = "MEDIUM"
        if not recs.get("risk_factors"):
            recs["risk_factors"] = []

        # Additional fields - use LLM values when available
        if not parsed.get("detailed_analysis"):
            parsed["detailed_analysis"] = f"Analysis of this Chef cookbook shows {fallback_defaults['primary_purpose'].lower()} implementation with {fallback_defaults['complexity'].lower()} complexity."
            logger.info(f"[{correlation_id}]  FALLBACK detailed_analysis: (generated)")
            fallback_used_count += 1
        else:
            logger.info(f"[{correlation_id}]  LLM detailed_analysis: (preserved)")
            llm_preserved_count += 1

        if not parsed.get("key_operations") or len(parsed.get("key_operations", [])) == 0:
            key_ops = []
            if fallback_defaults["packages"]:
                key_ops.append("Package installation")
            if fallback_defaults["services"]:
                key_ops.append("Service management")
            if fallback_defaults["files_managed"]:
                key_ops.append("File management")
            parsed["key_operations"] = key_ops or ["System configuration"]
            logger.info(f"[{correlation_id}]  FALLBACK key_operations: {parsed['key_operations']}")
            fallback_used_count += 1
        else:
            logger.info(f"[{correlation_id}]  LLM key_operations: {parsed.get('key_operations')}")
            llm_preserved_count += 1

        if not parsed.get("configuration_details"):
            parsed["configuration_details"] = f"Chef cookbook with {fallback_defaults['complexity'].lower()} configuration complexity"
            logger.info(f"[{correlation_id}]  FALLBACK configuration_details: (generated)")
            fallback_used_count += 1
        else:
            logger.info(f"[{correlation_id}]  LLM configuration_details: (preserved)")
            llm_preserved_count += 1

        if not parsed.get("complexity_level"):
            parsed["complexity_level"] = fallback_defaults["complexity"]
            logger.info(f"[{correlation_id}]  FALLBACK complexity_level: {fallback_defaults['complexity']}")
            fallback_used_count += 1
        else:
            logger.info(f"[{correlation_id}]  LLM complexity_level: {parsed.get('complexity_level')}")
            llm_preserved_count += 1

        if parsed.get("convertible") is None:
            parsed["convertible"] = True

        if not parsed.get("conversion_notes"):
            parsed["conversion_notes"] = f"This {fallback_defaults['primary_purpose'].lower()} cookbook can be converted with {fallback_defaults['migration_effort'].lower()} effort"
            logger.info(f"[{correlation_id}]  FALLBACK conversion_notes: (generated)")
            fallback_used_count += 1
        else:
            logger.info(f"[{correlation_id}]  LLM conversion_notes: (preserved)")
            llm_preserved_count += 1

        if not parsed.get("confidence_source"):
            parsed["confidence_source"] = "chef_semantic_analysis"

        # Summary
        logger.info(f"[{correlation_id}] ═══ FIELD SUMMARY ═══")
        logger.info(f"[{correlation_id}]  LLM values preserved: {llm_preserved_count}")
        logger.info(f"[{correlation_id}]  Fallback values used: {fallback_used_count}")
        llm_percentage = (llm_preserved_count / (llm_preserved_count + fallback_used_count) * 100) if (llm_preserved_count + fallback_used_count) > 0 else 0
        logger.info(f"[{correlation_id}] 📊 LLM analysis coverage: {llm_percentage:.1f}%")

        return parsed

    def _extract_json_from_text(self, text: str, correlation_id: str) -> Dict[str, Any]:
        """Extract JSON from text with multiple strategies"""
        logger.debug(f"[{correlation_id}] Attempting to extract JSON from LLM response")
        
        if not text or not text.strip():
            logger.warning(f"[{correlation_id}] Empty response from LLM")
            return {}

        original_text = text.strip()
        
        # Strategy 1: Remove code blocks
        code_block_match = re.search(r"```json\s*(\{.*\})\s*```", text, re.DOTALL | re.IGNORECASE)
        if code_block_match:
            logger.debug(f"[{correlation_id}] Found JSON code block")
            text = code_block_match.group(1)
        else:
            code_block_match = re.search(r"```\s*(\{.*\})\s*```", text, re.DOTALL)
            if code_block_match:
                logger.debug(f"[{correlation_id}] Found generic code block")
                text = code_block_match.group(1)

        # Strategy 2: Direct JSON parsing
        try:
            result = json.loads(text.strip())
            logger.info(f"[{correlation_id}] Successfully parsed LLM JSON response")
            return result
        except json.JSONDecodeError as e:
            logger.debug(f"[{correlation_id}] Direct JSON parsing failed: {e}")

        # Strategy 3: Find JSON patterns
        brace_patterns = [
            r'(\{[^{}]*\{[^{}]*\}[^{}]*\})',  # Nested JSON
            r'(\{.*?\})',  # Simple JSON
        ]
        
        for pattern in brace_patterns:
            matches = re.findall(pattern, original_text, re.DOTALL)
            for match in matches:
                try:
                    cleaned_match = self._clean_json_string(match)
                    result = json.loads(cleaned_match)
                    logger.info(f"[{correlation_id}] Successfully extracted JSON using pattern matching")
                    return result
                except json.JSONDecodeError:
                    continue

        logger.warning(f"[{correlation_id}] Could not extract valid JSON from LLM response")
        return {}

    def _clean_json_string(self, json_str: str) -> str:
        """Clean JSON string"""
        json_str = json_str.strip()
        json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
        return json_str

    def _make_complete_response(
        self, 
        parsed: Dict[str, Any], 
        correlation_id: str, 
        cookbook_name: str,
        fallback_defaults: Dict[str, Any],
        error: str = "Postprocessing failed"
    ) -> Dict[str, Any]:
        """Create complete response preserving LLM analysis where available"""
        logger.info(f"[{correlation_id}] Creating complete response with LLM analysis preservation")
        
        now = datetime.utcnow().isoformat()
        
        try:
            response = CookbookAnalysisResponse(
                success=error == "Postprocessing failed",
                cookbook_name=cookbook_name or "unknown",
                version_requirements=VersionRequirements(
                    min_chef_version=parsed.get("version_requirements", {}).get("min_chef_version") or fallback_defaults["min_chef_version"],
                    min_ruby_version=parsed.get("version_requirements", {}).get("min_ruby_version") or fallback_defaults["min_ruby_version"],
                    migration_effort=parsed.get("version_requirements", {}).get("migration_effort") or fallback_defaults["migration_effort"],
                    estimated_hours=parsed.get("version_requirements", {}).get("estimated_hours") or fallback_defaults["estimated_hours"],
                    deprecated_features=parsed.get("version_requirements", {}).get("deprecated_features") or []
                ),
                dependencies=Dependencies(
                    is_wrapper=parsed.get("dependencies", {}).get("is_wrapper") if parsed.get("dependencies", {}).get("is_wrapper") is not None else fallback_defaults["is_wrapper"],
                    wrapped_cookbooks=parsed.get("dependencies", {}).get("wrapped_cookbooks") or [],
                    direct_deps=parsed.get("dependencies", {}).get("direct_deps") or fallback_defaults["packages"],
                    runtime_deps=parsed.get("dependencies", {}).get("runtime_deps") or [],
                    circular_risk=parsed.get("dependencies", {}).get("circular_risk") or "none"
                ),
                functionality=Functionality(
                    primary_purpose=parsed.get("functionality", {}).get("primary_purpose") or fallback_defaults["primary_purpose"],
                    services=parsed.get("functionality", {}).get("services") or fallback_defaults["services"],
                    packages=parsed.get("functionality", {}).get("packages") or fallback_defaults["packages"],
                    files_managed=parsed.get("functionality", {}).get("files_managed") or fallback_defaults["files_managed"],
                    reusability=parsed.get("functionality", {}).get("reusability") or "MEDIUM",
                    customization_points=parsed.get("functionality", {}).get("customization_points") or ["configuration files"]
                ),
                recommendations=Recommendations(
                    consolidation_action=parsed.get("recommendations", {}).get("consolidation_action") or "EXTEND",
                    rationale=parsed.get("recommendations", {}).get("rationale") or f"Analysis shows {fallback_defaults['primary_purpose'].lower()}",
                    migration_priority=parsed.get("recommendations", {}).get("migration_priority") or "MEDIUM",
                    risk_factors=parsed.get("recommendations", {}).get("risk_factors") or []
                ),
                metadata=AnalysisMetadata(
                    analyzed_at=now,
                    agent_version="1.0.0",
                    correlation_id=correlation_id
                ),
                detailed_analysis=parsed.get("detailed_analysis") or f"Analysis shows {fallback_defaults['primary_purpose'].lower()} implementation.",
                key_operations=parsed.get("key_operations") or ["System configuration"],
                configuration_details=parsed.get("configuration_details") or f"Chef cookbook with {fallback_defaults['complexity'].lower()} complexity",
                complexity_level=parsed.get("complexity_level") or fallback_defaults["complexity"],
                convertible=parsed.get("convertible") if parsed.get("convertible") is not None else True,
                conversion_notes=parsed.get("conversion_notes") or f"Cookbook can be converted with {fallback_defaults['migration_effort'].lower()} effort",
                confidence_source=parsed.get("confidence_source") or "chef_semantic_analysis"
            )
            resp = response.dict()
            if error != "Postprocessing failed":
                resp["postprocess_error"] = error
            logger.info(f"[{correlation_id}] Complete response created with LLM analysis preserved")
            return resp
        except Exception as e:
            logger.error(f"[{correlation_id}] Complete fallback required: {e}")
            # Final minimal fallback
            return {
                "success": False,
                "cookbook_name": cookbook_name or "unknown",
                "version_requirements": {
                    "min_chef_version": fallback_defaults["min_chef_version"],
                    "min_ruby_version": fallback_defaults["min_ruby_version"],
                    "migration_effort": fallback_defaults["migration_effort"],
                    "estimated_hours": fallback_defaults["estimated_hours"],
                    "deprecated_features": []
                },
                "dependencies": {
                    "is_wrapper": fallback_defaults["is_wrapper"],
                    "wrapped_cookbooks": [],
                    "direct_deps": fallback_defaults["packages"],
                    "runtime_deps": [],
                    "circular_risk": "none"
                },
                "functionality": {
                    "primary_purpose": fallback_defaults["primary_purpose"],
                    "services": fallback_defaults["services"],
                    "packages": fallback_defaults["packages"],
                    "files_managed": fallback_defaults["files_managed"],
                    "reusability": "MEDIUM",
                    "customization_points": ["configuration files"]
                },
                "recommendations": {
                    "consolidation_action": "EXTEND",
                    "rationale": f"Analysis shows {fallback_defaults['primary_purpose'].lower()}",
                    "migration_priority": "MEDIUM",
                    "risk_factors": []
                },
                "metadata": {
                    "analyzed_at": now,
                    "agent_version": "1.0.0",
                    "correlation_id": correlation_id
                },
                "detailed_analysis": f"Analysis shows {fallback_defaults['primary_purpose'].lower()} implementation.",
                "key_operations": ["System configuration"],
                "configuration_details": f"Chef cookbook with {fallback_defaults['complexity'].lower()} complexity",
                "complexity_level": fallback_defaults["complexity"],
                "convertible": True,
                "conversion_notes": f"Cookbook can be converted with {fallback_defaults['migration_effort'].lower()} effort",
                "confidence_source": "chef_semantic_analysis",
                "postprocess_error": f"Complete fallback: {error}; {e}"
            }


# Module-level function with same signature
def extract_and_validate_analysis(raw_response: str, correlation_id: Optional[str] = None, cookbook_content: str = "") -> Dict[str, Any]:
    """Enhanced entry point that uses LLM analysis with smart fallbacks"""
    if correlation_id is None:
        correlation_id = f"corr_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    return ChefAnalysisPostprocessor().extract_and_validate_analysis(raw_response, correlation_id, cookbook_content)


# Add these methods to the ChefAnalysisPostprocessor class in processor.py
# Place these methods after the existing extract_and_validate_analysis method

    def extract_and_validate_analysis(self, raw_response: str, correlation_id: str, cookbook_content: str = "") -> Dict[str, Any]:
        """
        Enhanced extraction that preserves rich backend data for beautiful UI display
        """
        logger.info(f"[{correlation_id}] ═══ Starting enhanced postprocessing for UI display ═══")
        logger.info(f"[{correlation_id}] Raw response length: {len(raw_response)} characters")
        
        # Get minimal fallback defaults
        fallback_defaults = self._get_minimal_fallback_defaults(cookbook_content)
        logger.info(f"[{correlation_id}] Fallback defaults prepared with {len(fallback_defaults)} fields")

        # Extract JSON from response
        if isinstance(raw_response, dict):
            parsed = raw_response
            logger.info(f"[{correlation_id}]  Input was already a dict")
        else:
            parsed = self._extract_json_from_text(raw_response, correlation_id)
        
        # Check if we got valid JSON from LLM
        if not parsed:
            logger.warning(f"[{correlation_id}] ⚠️ No JSON extracted from LLM, using complete fallback")
            result = self._make_complete_response({}, correlation_id, "unknown", fallback_defaults)
            return self._enhance_for_ui_display(result, correlation_id)

        logger.info(f"[{correlation_id}]  LLM provided JSON with keys: {list(parsed.keys())}")

        # Extract cookbook name
        cookbook_name = parsed.get("cookbook_name", fallback_defaults.get("cookbook_name", "unknown"))
        
        # Ensure all required sections exist
        self._ensure_required_sections(parsed)

        # Fill missing fields while preserving LLM analysis
        parsed = self._fill_missing_fields_only(parsed, fallback_defaults, correlation_id)

        # Add metadata
        parsed["metadata"] = {
            "analyzed_at": datetime.utcnow().isoformat(),
            "agent_version": "prompt_chaining_v1",
            "correlation_id": correlation_id
        }
        parsed["success"] = True
        parsed["cookbook_name"] = cookbook_name

        # ENHANCEMENT: Add UI-friendly enhancements
        ui_enhancements = self._create_ui_enhancements(parsed, correlation_id)
        parsed.update(ui_enhancements)

        # Validate using Pydantic
        try:
            response = CookbookAnalysisResponse(**parsed)
            result = response.dict()
            
            # Preserve UI enhancements after validation
            result.update(ui_enhancements)
            
            logger.info(f"[{correlation_id}]  Enhanced analysis validated successfully")
            return self._enhance_for_ui_display(result, correlation_id)
            
        except Exception as e:
            logger.error(f"[{correlation_id}] ❌ Pydantic validation failed: {e}")
            result = self._make_complete_response(parsed, correlation_id, cookbook_name, fallback_defaults, error=str(e))
            return self._enhance_for_ui_display(result, correlation_id)

    def _ensure_required_sections(self, parsed: Dict[str, Any]) -> None:
        """Ensure all required sections exist"""
        required_sections = ["version_requirements", "dependencies", "functionality", "recommendations"]
        for section in required_sections:
            if section not in parsed:
                parsed[section] = {}

    def _create_ui_enhancements(self, parsed: Dict[str, Any], correlation_id: str) -> Dict[str, Any]:
        """Create comprehensive UI-friendly enhancements"""
        logger.info(f"[{correlation_id}] 🎨 Creating UI enhancements...")
        
        vr = parsed.get("version_requirements", {})
        func = parsed.get("functionality", {})
        recs = parsed.get("recommendations", {})
        deps = parsed.get("dependencies", {})
        
        enhancements = {
            # Core flattened fields for backward compatibility
            "migration_effort": vr.get("migration_effort", "Not assessed"),
            "complexity_level": self._enhance_complexity_display(parsed, func),
            "primary_purpose": self._enhance_primary_purpose(func, parsed),
            "reusability": func.get("reusability", "Not specified"),
            "consolidation_action": recs.get("consolidation_action", "Review needed"),
            "migration_priority": recs.get("migration_priority", "Medium"),
            "is_wrapper": deps.get("is_wrapper"),
            "services": func.get("services", []),
            "packages": func.get("packages", []),
            "files_managed": func.get("files_managed", []),
            
            # Enhanced UI-specific fields
            "ui_display_name": self._create_display_name(parsed),
            "ui_migration_summary": self._create_migration_summary(vr, func, recs),
            "ui_risk_assessment": self._assess_risk_level(vr, recs, deps),
            "ui_complexity_details": self._create_complexity_details(parsed, func, deps),
            "ui_conversion_readiness": self._assess_conversion_readiness(parsed, vr, func, deps),
            "ui_feature_summary": self._create_feature_summary(func, deps),
            "ui_timeline_estimate": self._create_timeline_estimate(vr),
            
            # Enhanced convertible logic
            "convertible": self._determine_convertible_status(parsed, vr, func, deps),
        }
        
        logger.info(f"[{correlation_id}]  Created {len(enhancements)} UI enhancements")
        return enhancements

    def _enhance_complexity_display(self, parsed: Dict, func: Dict) -> str:
        """Create rich complexity information"""
        base_complexity = parsed.get("complexity_level", "")
        
        # If we have a good complexity level, enhance it
        if base_complexity and base_complexity != "Unknown":
            return base_complexity
        
        # Otherwise, infer from data
        services_count = len(func.get("services", []))
        packages_count = len(func.get("packages", []))
        files_count = len(func.get("files_managed", []))
        customization_count = len(func.get("customization_points", []))
        
        total_items = services_count + packages_count + files_count + customization_count
        
        if total_items > 15:
            return "High - Complex multi-service configuration"
        elif total_items > 8:
            return "Medium - Standard multi-component setup"
        elif total_items > 3:
            return "Low - Simple configuration"
        elif total_items > 0:
            return "Simple - Basic setup"
        else:
            return "Minimal - Basic cookbook structure"

    def _enhance_primary_purpose(self, func: Dict, parsed: Dict) -> str:
        """Create enhanced primary purpose description"""
        base_purpose = func.get("primary_purpose", "")
        
        if base_purpose and base_purpose != "No summary available":
            return base_purpose
        
        # Generate purpose from available data
        services = func.get("services", [])
        packages = func.get("packages", [])
        
        if services:
            return f"Manages {', '.join(services[:3])} service{'s' if len(services) > 1 else ''}" + \
                   (f" and {len(services) - 3} more" if len(services) > 3 else "")
        elif packages:
            return f"Installs and configures {', '.join(packages[:3])}" + \
                   (f" and {len(packages) - 3} more packages" if len(packages) > 3 else "")
        else:
            return "Chef cookbook for system configuration and management"

    def _create_display_name(self, parsed: Dict) -> str:
        """Create user-friendly display name"""
        name = parsed.get("cookbook_name", "")
        
        if not name or "uploaded_cookbook" in name.lower():
            # Try to infer from functionality
            func = parsed.get("functionality", {})
            services = func.get("services", [])
            if services:
                return f"Chef Cookbook ({services[0].title()} Configuration)"
            else:
                return "Chef Cookbook"
        
        return name.replace("_", " ").title()

    def _create_migration_summary(self, vr: Dict, func: Dict, recs: Dict) -> str:
        """Create comprehensive migration summary"""
        parts = []
        
        # Add purpose
        purpose = func.get("primary_purpose")
        if purpose:
            parts.append(f"📋 {purpose}")
        
        # Add migration effort
        effort = vr.get("migration_effort")
        hours = vr.get("estimated_hours")
        if effort:
            effort_text = f"🔄 {effort.title()} migration effort"
            if hours:
                effort_text += f" (~{hours}h estimated)"
            parts.append(effort_text)
        
        # Add recommendation
        action = recs.get("consolidation_action")
        if action:
            action_emoji = {"REUSE": "♻️", "EXTEND": "🔧", "RECREATE": "🆕"}.get(action, "💡")
            parts.append(f"{action_emoji} Recommended: {action.title()}")
        
        return " | ".join(parts) if parts else "Analysis completed successfully"

    def _assess_risk_level(self, vr: Dict, recs: Dict, deps: Dict) -> Dict[str, Any]:
        """Comprehensive risk assessment"""
        risk_score = 0
        risk_factors = []
        
        # Migration effort risk
        effort = vr.get("migration_effort", "").upper()
        if effort == "HIGH":
            risk_score += 3
            risk_factors.append("High migration effort required")
        elif effort == "MEDIUM":
            risk_score += 1
            risk_factors.append("Moderate migration complexity")
        
        # Dependency risk
        if deps.get("circular_risk", "none") != "none":
            risk_score += 2
            risk_factors.append("Circular dependency risk detected")
        
        # Wrapper cookbook risk
        if deps.get("is_wrapper"):
            risk_score += 1
            risk_factors.append("Wrapper cookbook - dependency on other cookbooks")
        
        # Explicit risk factors
        explicit_risks = recs.get("risk_factors", [])
        risk_score += len(explicit_risks)
        risk_factors.extend(explicit_risks)
        
        # Deprecated features
        deprecated = vr.get("deprecated_features", [])
        if deprecated:
            risk_score += len(deprecated)
            risk_factors.append(f"Uses {len(deprecated)} deprecated feature(s)")
        
        # Determine level
        if risk_score >= 5:
            level = "HIGH"
            color = "red"
        elif risk_score >= 3:
            level = "MEDIUM"
            color = "yellow"
        elif risk_score >= 1:
            level = "LOW"
            color = "blue"
        else:
            level = "MINIMAL"
            color = "green"
        
        return {
            "level": level,
            "score": risk_score,
            "factors": risk_factors,
            "color": color,
            "assessment": f"{level.title()} risk migration" + (f" ({len(risk_factors)} factors)" if risk_factors else "")
        }

    def _create_complexity_details(self, parsed: Dict, func: Dict, deps: Dict) -> str:
        """Create detailed complexity breakdown"""
        details = []
        
        services = func.get("services", [])
        packages = func.get("packages", [])
        files = func.get("files_managed", [])
        customizations = func.get("customization_points", [])
        dependencies = deps.get("direct_deps", [])
        
        if services:
            details.append(f"🔧 {len(services)} service(s)")
        if packages:
            details.append(f"📦 {len(packages)} package(s)")
        if files:
            details.append(f"📁 {len(files)} managed file(s)")
        if customizations:
            details.append(f"⚙️ {len(customizations)} customization point(s)")
        if dependencies:
            details.append(f"🔗 {len(dependencies)} dependencies")
        
        return " | ".join(details) if details else "Standard Chef cookbook structure"

    def _assess_conversion_readiness(self, parsed: Dict, vr: Dict, func: Dict, deps: Dict) -> Dict[str, Any]:
        """Comprehensive conversion readiness assessment"""
        readiness_score = 0
        max_score = 8
        criteria = []
        
        # Version requirements clarity
        if vr.get("min_chef_version"):
            readiness_score += 1
            criteria.append(" Chef version requirements identified")
        else:
            criteria.append("⚠️ Chef version requirements unclear")
        
        # Migration effort assessment
        effort = vr.get("migration_effort", "").upper()
        if effort == "LOW":
            readiness_score += 2
            criteria.append(" Low migration effort")
        elif effort == "MEDIUM":
            readiness_score += 1
            criteria.append(" Moderate migration effort")
        else:
            criteria.append("⚠️ High or unknown migration effort")
        
        # Functionality clarity
        if func.get("primary_purpose"):
            readiness_score += 1
            criteria.append(" Clear primary purpose defined")
        
        # Resource identification
        if func.get("packages") or func.get("services"):
            readiness_score += 1
            criteria.append(" Resources clearly identified")
        
        # Dependency analysis
        is_wrapper = deps.get("is_wrapper")
        if is_wrapper is True:
            readiness_score += 1
            criteria.append(" Wrapper cookbook (easier conversion)")
        elif is_wrapper is False:
            readiness_score += 1
            criteria.append(" Standalone cookbook")
        
        # Risk factors
        risk_factors = parsed.get("ui_risk_assessment", {}).get("factors", [])
        if len(risk_factors) <= 2:
            readiness_score += 1
            criteria.append(" Minimal risk factors")
        
        # Reusability
        reusability = func.get("reusability", "").upper()
        if reusability in ["HIGH", "MEDIUM"]:
            readiness_score += 1
            criteria.append(" Good reusability potential")
        
        readiness_percentage = (readiness_score / max_score) * 100
        
        if readiness_percentage >= 85:
            level = "EXCELLENT"
            color = "green"
            recommendation = "Ready for immediate conversion"
        elif readiness_percentage >= 65:
            level = "GOOD"
            color = "blue"
            recommendation = "Ready for conversion with minor preparation"
        elif readiness_percentage >= 45:
            level = "FAIR"
            color = "yellow"
            recommendation = "Requires preparation before conversion"
        else:
            level = "NEEDS_REVIEW"
            color = "red"
            recommendation = "Requires significant analysis before conversion"
        
        return {
            "score": readiness_score,
            "max_score": max_score,
            "percentage": readiness_percentage,
            "level": level,
            "color": color,
            "criteria": criteria,
            "recommendation": recommendation
        }

    def _create_feature_summary(self, func: Dict, deps: Dict) -> Dict[str, Any]:
        """Create feature summary for UI display"""
        return {
            "services_count": len(func.get("services", [])),
            "packages_count": len(func.get("packages", [])),
            "files_count": len(func.get("files_managed", [])),
            "customization_count": len(func.get("customization_points", [])),
            "dependency_count": len(deps.get("direct_deps", [])),
            "is_wrapper": deps.get("is_wrapper", False),
            "has_templates": any("template" in f.lower() for f in func.get("files_managed", [])),
            "has_services": len(func.get("services", [])) > 0,
        }

    def _create_timeline_estimate(self, vr: Dict) -> Dict[str, Any]:
        """Create timeline estimates"""
        hours = vr.get("estimated_hours", 2)
        effort = vr.get("migration_effort", "MEDIUM").upper()
        
        # Adjust estimates based on effort level
        if effort == "LOW":
            analysis_hours = max(0.5, hours * 0.2)
            conversion_hours = max(1, hours * 0.6)
            testing_hours = max(0.5, hours * 0.2)
        elif effort == "HIGH":
            analysis_hours = max(2, hours * 0.3)
            conversion_hours = max(4, hours * 0.5)
            testing_hours = max(1, hours * 0.2)
        else:  # MEDIUM
            analysis_hours = max(1, hours * 0.25)
            conversion_hours = max(2, hours * 0.6)
            testing_hours = max(0.5, hours * 0.15)
        
        return {
            "total_hours": hours,
            "analysis_hours": analysis_hours,
            "conversion_hours": conversion_hours,
            "testing_hours": testing_hours,
            "effort_level": effort,
            "timeline_breakdown": {
                "analysis": f"{analysis_hours:.1f}h - Code analysis and planning",
                "conversion": f"{conversion_hours:.1f}h - Ansible playbook creation",
                "testing": f"{testing_hours:.1f}h - Validation and testing"
            }
        }

    def _determine_convertible_status(self, parsed: Dict, vr: Dict, func: Dict, deps: Dict) -> bool:
        """Smart determination of convertible status"""
        # If explicitly set, use that
        if parsed.get("convertible") is not None:
            return parsed["convertible"]
        
        # Score-based determination
        convertible_score = 0
        
        # Positive factors
        if vr.get("migration_effort") == "LOW":
            convertible_score += 3
        elif vr.get("migration_effort") == "MEDIUM":
            convertible_score += 1
        
        if func.get("services") or func.get("packages"):
            convertible_score += 2
        
        if func.get("reusability", "").upper() in ["HIGH", "MEDIUM"]:
            convertible_score += 1
        
        if not deps.get("circular_risk") or deps.get("circular_risk") == "none":
            convertible_score += 1
        
        # Negative factors
        if vr.get("deprecated_features"):
            convertible_score -= len(vr["deprecated_features"])
        
        if deps.get("circular_risk", "none") in ["high", "medium"]:
            convertible_score -= 2
        
        # Decision threshold
        return convertible_score >= 2

    def _enhance_for_ui_display(self, result: Dict[str, Any], correlation_id: str) -> Dict[str, Any]:
        """Final enhancement pass for optimal UI display"""
        logger.info(f"[{correlation_id}] 🎨 Final UI display enhancement")
        
        # Ensure all display fields have good defaults
        if not result.get("summary") or result["summary"] == "No summary available":
            result["summary"] = result.get("ui_migration_summary", "Chef cookbook analysis completed")
        
        # Enhance conversion notes if basic
        if not result.get("conversion_notes") or "No conversion notes" in result["conversion_notes"]:
            convertible = result.get("convertible", True)
            effort = result.get("migration_effort", "Medium")
            result["conversion_notes"] = (
                f"This cookbook {'can be converted' if convertible else 'requires review before conversion'} "
                f"to Ansible with {effort.lower()} effort. "
                f"{result.get('ui_conversion_readiness', {}).get('recommendation', '')}"
            )
        
        # Add UI metadata
        result["ui_enhanced"] = True
        result["ui_enhancement_timestamp"] = datetime.utcnow().isoformat()
        
        logger.info(f"[{correlation_id}]  UI enhancement completed")
        return result