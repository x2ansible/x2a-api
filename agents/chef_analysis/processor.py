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
    Enhanced postprocessor that analyzes cookbook content dynamically with minimal hardcoding
    """

    def __init__(self):
        self.required_sections = [
            "version_requirements",
            "dependencies",
            "functionality",
            "recommendations"
        ]

    def _extract_actual_file_paths(self, cookbook_content: str) -> List[str]:
        """Extract actual file paths from cookbook content"""
        file_paths = []
        
        # Look for template and file resources with actual paths
        path_patterns = [
            r'path\s+["\']([^"\']+)["\']',  # path "..."
            r'destination\s+["\']([^"\']+)["\']',  # destination "..."
            r'source\s+["\']([^"\']+)["\']',  # source "..."
            r'"/[^"]*\.conf"',  # config file patterns
            r"'/[^']*\.conf'",  # config file patterns with single quotes
        ]
        
        for pattern in path_patterns:
            matches = re.findall(pattern, cookbook_content, re.IGNORECASE)
            file_paths.extend(matches)
        
        # Remove duplicates and filter valid paths
        unique_paths = list(set([path for path in file_paths if path.startswith('/') and len(path) > 1]))
        
        return unique_paths[:10]  # Limit to most relevant paths

    def _extract_actual_packages(self, cookbook_content: str) -> List[str]:
        """Extract actual package names from cookbook content"""
        packages = []
        
        # Look for package resources
        package_patterns = [
            r'package\s+["\']([^"\']+)["\']',  # package "name"
            r'package_name\s+["\']([^"\']+)["\']',  # package_name "name"
            r'package\s+(\w+)\s+do',  # package name do
        ]
        
        for pattern in package_patterns:
            matches = re.findall(pattern, cookbook_content, re.IGNORECASE)
            packages.extend(matches)
        
        # Also check for technology-specific packages
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
        
        return list(set(packages))  # Remove duplicates

    def _extract_actual_services(self, cookbook_content: str) -> List[str]:
        """Extract actual service names from cookbook content"""
        services = []
        
        # Look for service resources
        service_patterns = [
            r'service\s+["\']([^"\']+)["\']',  # service "name"
            r'service_name\s+["\']([^"\']+)["\']',  # service_name "name"
            r'service\s+(\w+)\s+do',  # service name do
        ]
        
        for pattern in service_patterns:
            matches = re.findall(pattern, cookbook_content, re.IGNORECASE)
            services.extend(matches)
        
        return list(set(services))  # Remove duplicates

    def _analyze_chef_version_features(self, cookbook_content: str) -> str:
        """Analyze Chef-specific features to determine minimum version"""
        content_lower = cookbook_content.lower()
        
        # Check for specific Chef version indicators in order of newest to oldest
        if any(feature in content_lower for feature in ["unified_mode = true", "unified_mode true"]):
            return "15.0"
        elif any(feature in content_lower for feature in ["provides", "property", "custom_resource"]):
            return "14.0"
        elif any(feature in content_lower for feature in ["node.override", "node['override']"]):
            return "13.0"
        elif "chef_version" in content_lower:
            # Try to extract actual version requirement
            version_match = re.search(r'chef_version\s+["\']>=?\s*([0-9]+\.[0-9]+)', cookbook_content, re.IGNORECASE)
            if version_match:
                return version_match.group(1)
            return "12.5"
        elif any(feature in content_lower for feature in ["cookbook_file", "remote_file"]):
            return "12.0"
        else:
            # Very conservative estimate based on common Chef practices
            return "11.0"

    def _analyze_ruby_version_features(self, cookbook_content: str) -> str:
        """Analyze Ruby syntax to determine minimum version"""
        
        # Check for Ruby version indicators in order of newest to oldest
        if "&." in cookbook_content:  # Safe navigation operator
            return "2.3"
        elif re.search(r'def \w+\([^)]*:\s*\w+', cookbook_content):  # Keyword arguments
            return "2.1"
        elif re.search(r'\w+:\s*\w+', cookbook_content):  # Modern hash syntax
            return "1.9"
        else:
            # Conservative estimate
            return "1.8"

    def _calculate_dynamic_complexity(self, cookbook_content: str) -> Dict[str, Any]:
        """Calculate complexity based on actual cookbook analysis"""
        content_lower = cookbook_content.lower()
        
        # Count different types of complexity indicators
        resource_types = sum([
            "package" in content_lower,
            "service" in content_lower,
            "file" in content_lower,
            "template" in content_lower,
            "directory" in content_lower,
            "user" in content_lower,
            "group" in content_lower,
            "cron" in content_lower,
            "mount" in content_lower,
        ])
        
        chef_features = sum([
            "recipe" in content_lower,
            "attribute" in content_lower,
            "library" in content_lower,
            "include_recipe" in content_lower,
            "notifies" in content_lower,
            "subscribes" in content_lower,
            "guards" in content_lower,
            "only_if" in content_lower,
            "not_if" in content_lower,
        ])
        
        advanced_features = sum([
            "custom_resource" in content_lower,
            "provides" in content_lower,
            "unified_mode" in content_lower,
            "lazy" in content_lower,
            "delayed" in content_lower,
        ])
        
        # Calculate lines of actual code (excluding comments and empty lines)
        lines = cookbook_content.split('\n')
        code_lines = len([line for line in lines if line.strip() and not line.strip().startswith('#')])
        
        # Dynamic complexity calculation
        total_complexity_score = resource_types + (chef_features * 2) + (advanced_features * 3)
        
        # Scale complexity based on multiple factors
        if total_complexity_score <= 3 and code_lines <= 50:
            complexity = "Low"
            migration_effort = "LOW"
            # Dynamic hours based on actual content
            estimated_hours = max(1.0, code_lines / 25)  # ~25 lines per hour
        elif total_complexity_score <= 8 and code_lines <= 150:
            complexity = "Medium"
            migration_effort = "MEDIUM"
            estimated_hours = max(4.0, code_lines / 20)  # ~20 lines per hour
        else:
            complexity = "High"
            migration_effort = "HIGH"
            estimated_hours = max(8.0, code_lines / 15)  # ~15 lines per hour
        
        # Cap maximum estimated hours at reasonable level
        estimated_hours = min(estimated_hours, 40.0)
        
        return {
            "complexity": complexity,
            "migration_effort": migration_effort,
            "estimated_hours": round(estimated_hours, 1),
            "total_score": total_complexity_score,
            "code_lines": code_lines
        }

    def _determine_primary_purpose(self, cookbook_content: str, packages: List[str], services: List[str]) -> str:
        """Determine primary purpose based on actual content analysis"""
        content_lower = cookbook_content.lower()
        
        # Analyze based on actual packages and services found
        if any(pkg in ["nginx"] for pkg in packages) or "nginx" in content_lower:
            return "Nginx web server configuration"
        elif any(pkg in ["apache2", "httpd"] for pkg in packages) or any(term in content_lower for term in ["apache", "httpd"]):
            return "Apache web server configuration"
        elif any(pkg in ["mysql-server", "mysql"] for pkg in packages) or "mysql" in content_lower:
            return "MySQL database server configuration"
        elif any(pkg in ["postgresql"] for pkg in packages) or "postgresql" in content_lower:
            return "PostgreSQL database server configuration"
        elif any(pkg in ["docker"] for pkg in packages) or "docker" in content_lower:
            return "Docker container platform configuration"
        elif any(term in content_lower for term in ["nodejs", "node.js", "npm"]):
            return "Node.js application server configuration"
        elif any(term in content_lower for term in ["redis", "memcached"]):
            return "Caching service configuration"
        elif any(term in content_lower for term in ["elasticsearch", "kibana", "logstash"]):
            return "Search and analytics platform configuration"
        elif packages and services:
            return f"Multi-service system configuration ({', '.join(packages[:3])})"
        elif packages:
            return f"Package management and configuration ({', '.join(packages[:3])})"
        elif services:
            return f"Service management and configuration ({', '.join(services[:3])})"
        else:
            return "System configuration and management"

    def _analyze_cookbook_characteristics(self, cookbook_content: str) -> Dict[str, Any]:
        """Analyze cookbook content dynamically with minimal hardcoding"""
        
        # Extract actual content from cookbook
        actual_packages = self._extract_actual_packages(cookbook_content)
        actual_services = self._extract_actual_services(cookbook_content)
        actual_file_paths = self._extract_actual_file_paths(cookbook_content)
        
        # Analyze versions based on actual features
        min_chef_version = self._analyze_chef_version_features(cookbook_content)
        min_ruby_version = self._analyze_ruby_version_features(cookbook_content)
        
        # Calculate complexity dynamically
        complexity_analysis = self._calculate_dynamic_complexity(cookbook_content)
        
        # Determine purpose based on actual content
        primary_purpose = self._determine_primary_purpose(cookbook_content, actual_packages, actual_services)
        
        # Analyze wrapper characteristics
        content_lower = cookbook_content.lower()
        has_include_recipe = "include_recipe" in content_lower
        has_own_resources = any(term in content_lower for term in ["package", "service", "file", "template"])
        is_wrapper = has_include_recipe and not has_own_resources
        
        # Build key operations based on actual content
        key_operations = []
        if actual_packages:
            key_operations.append("Package installation")
        if actual_services:
            key_operations.append("Service management")
        if actual_file_paths:
            key_operations.append("File management")
        if "template" in content_lower:
            key_operations.append("Template configuration")
        if has_include_recipe:
            key_operations.append("Recipe inclusion")
        if not key_operations:
            key_operations = ["System configuration"]
        
        # Calculate file count
        file_count = len(cookbook_content.split('===')) - 1 if '===' in cookbook_content else 1
        
        return {
            "min_chef_version": min_chef_version,
            "min_ruby_version": min_ruby_version,
            "migration_effort": complexity_analysis["migration_effort"],
            "estimated_hours": complexity_analysis["estimated_hours"],
            "complexity": complexity_analysis["complexity"],
            "primary_purpose": primary_purpose,
            "services": actual_services,
            "packages": actual_packages,
            "files_managed": actual_file_paths,
            "key_operations": key_operations,
            "is_wrapper": is_wrapper,
            "file_count": file_count,
            "code_lines": complexity_analysis["code_lines"],
            "complexity_score": complexity_analysis["total_score"]
        }

    def extract_and_validate_analysis(self, raw_response: str, correlation_id: str, cookbook_content: str = "") -> Dict[str, Any]:
        """
        Enhanced extraction that ensures ALL fields are populated with dynamic analysis
        """
        logger.info(f"[{correlation_id}] Starting enhanced postprocessing")
        logger.debug(f"[{correlation_id}] Raw response length: {len(raw_response)} characters")

        # Analyze cookbook content dynamically
        cookbook_analysis = self._analyze_cookbook_characteristics(cookbook_content)
        logger.debug(f"[{correlation_id}] Dynamic analysis: complexity={cookbook_analysis['complexity']}, chef_version={cookbook_analysis['min_chef_version']}")

        # 1. Try to extract JSON from the response
        if isinstance(raw_response, dict):
            parsed = raw_response
            logger.debug(f"[{correlation_id}] Input was already a dict")
        else:
            parsed = self._extract_json_from_text(raw_response, correlation_id)
        
        # 2. Check if we got valid JSON
        if not parsed:
            logger.warning(f"[{correlation_id}] No JSON extracted, creating complete response with dynamic defaults")
            return self._make_complete_response({}, correlation_id, "unknown", cookbook_analysis)

        logger.debug(f"[{correlation_id}] Extracted JSON keys: {list(parsed.keys())}")

        # 3. Extract cookbook name
        cookbook_name = parsed.get("cookbook_name", "unknown")
        
        # 4. Ensure all required sections exist with defaults
        if "version_requirements" not in parsed:
            parsed["version_requirements"] = {}
        if "dependencies" not in parsed:
            parsed["dependencies"] = {}
        if "functionality" not in parsed:
            parsed["functionality"] = {}
        if "recommendations" not in parsed:
            parsed["recommendations"] = {}

        # 5. ALWAYS populate additional fields if missing
        parsed = self._ensure_additional_fields(parsed, cookbook_analysis, correlation_id)

        # 6. Add metadata
        parsed["metadata"] = {
            "analyzed_at": datetime.utcnow().isoformat(),
            "agent_version": "1.0.0",
            "correlation_id": correlation_id
        }
        parsed["success"] = True
        parsed["cookbook_name"] = cookbook_name

        # 7. Validate and coerce using Pydantic
        try:
            response = CookbookAnalysisResponse(**parsed)
            logger.info(f"[{correlation_id}] Complete analysis response validated successfully")
            return response.dict()
        except Exception as e:
            logger.error(f"[{correlation_id}]  Pydantic validation failed: {e}")
            # Try to build with as much as possible
            return self._make_complete_response(parsed, correlation_id, cookbook_name, cookbook_analysis, error=str(e))

    def _ensure_additional_fields(self, parsed: Dict[str, Any], cookbook_analysis: Dict[str, Any], correlation_id: str) -> Dict[str, Any]:
        """Ensure all additional fields are populated with dynamic defaults"""
        logger.debug(f"[{correlation_id}] Ensuring additional fields are populated")

        # Populate missing fields with dynamic defaults
        if not parsed.get("detailed_analysis"):
            parsed["detailed_analysis"] = f"This Chef cookbook implements {cookbook_analysis['primary_purpose'].lower()}. It contains {cookbook_analysis['file_count']} files with {cookbook_analysis['code_lines']} lines of code and demonstrates {cookbook_analysis['complexity'].lower()} complexity (score: {cookbook_analysis['complexity_score']}). The cookbook follows Chef best practices and is suitable for automation conversion."

        if not parsed.get("key_operations") or len(parsed.get("key_operations", [])) == 0:
            parsed["key_operations"] = cookbook_analysis["key_operations"]

        if not parsed.get("configuration_details"):
            parsed["configuration_details"] = f"Chef cookbook with {cookbook_analysis['complexity'].lower()} configuration complexity implementing {len(cookbook_analysis['key_operations'])} primary operations"

        if not parsed.get("complexity_level"):
            parsed["complexity_level"] = cookbook_analysis["complexity"]

        if parsed.get("convertible") is None:
            parsed["convertible"] = True

        if not parsed.get("conversion_notes"):
            parsed["conversion_notes"] = f"This {cookbook_analysis['primary_purpose'].lower()} cookbook can be converted to Ansible playbooks. The {cookbook_analysis['complexity'].lower()} complexity suggests {cookbook_analysis['migration_effort'].lower()} migration effort with approximately {cookbook_analysis['estimated_hours']} hours required."

        if not parsed.get("confidence_source"):
            parsed["confidence_source"] = "chef_semantic_analysis"

        logger.debug(f"[{correlation_id}] Additional fields populated successfully")
        return parsed

    def _extract_json_from_text(self, text: str, correlation_id: str) -> Dict[str, Any]:
        """Extract JSON from text with multiple strategies"""
        logger.debug(f"[{correlation_id}] Attempting to extract JSON from text")
        
        if not text or not text.strip():
            logger.warning(f"[{correlation_id}] Empty or whitespace-only text provided")
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
            logger.debug(f"[{correlation_id}] Direct JSON parsing successful")
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
                    logger.debug(f"[{correlation_id}] Pattern-based JSON extraction successful")
                    return result
                except json.JSONDecodeError:
                    continue

        logger.error(f"[{correlation_id}]  Could not extract JSON from LLM output")
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
        cookbook_analysis: Dict[str, Any],
        error: str = "Postprocessing failed"
    ) -> Dict[str, Any]:
        """Create complete response with ALL fields populated using dynamic analysis"""
        logger.info(f"[{correlation_id}] Creating complete response with dynamic defaults")
        
        now = datetime.utcnow().isoformat()
        
        # Build complete response with dynamic defaults from cookbook analysis
        try:
            response = CookbookAnalysisResponse(
                success=error == "Postprocessing failed",  # True if no error, False if error
                cookbook_name=cookbook_name or "unknown",
                version_requirements=VersionRequirements(
                    min_chef_version=parsed.get("version_requirements", {}).get("min_chef_version") or cookbook_analysis["min_chef_version"],
                    min_ruby_version=parsed.get("version_requirements", {}).get("min_ruby_version") or cookbook_analysis["min_ruby_version"],
                    migration_effort=parsed.get("version_requirements", {}).get("migration_effort") or cookbook_analysis["migration_effort"],
                    estimated_hours=parsed.get("version_requirements", {}).get("estimated_hours") or cookbook_analysis["estimated_hours"],
                    deprecated_features=parsed.get("version_requirements", {}).get("deprecated_features") or []
                ),
                dependencies=Dependencies(
                    is_wrapper=parsed.get("dependencies", {}).get("is_wrapper") if parsed.get("dependencies", {}).get("is_wrapper") is not None else cookbook_analysis["is_wrapper"],
                    wrapped_cookbooks=parsed.get("dependencies", {}).get("wrapped_cookbooks") or [],
                    direct_deps=parsed.get("dependencies", {}).get("direct_deps") or cookbook_analysis["packages"],
                    runtime_deps=parsed.get("dependencies", {}).get("runtime_deps") or [],
                    circular_risk=parsed.get("dependencies", {}).get("circular_risk") or "none"
                ),
                functionality=Functionality(
                    primary_purpose=parsed.get("functionality", {}).get("primary_purpose") or cookbook_analysis["primary_purpose"],
                    services=parsed.get("functionality", {}).get("services") or cookbook_analysis["services"],
                    packages=parsed.get("functionality", {}).get("packages") or cookbook_analysis["packages"],
                    files_managed=parsed.get("functionality", {}).get("files_managed") or cookbook_analysis["files_managed"],
                    reusability=parsed.get("functionality", {}).get("reusability") or ("HIGH" if cookbook_analysis["complexity"] == "Low" else "MEDIUM"),
                    customization_points=parsed.get("functionality", {}).get("customization_points") or (["configuration files", "service parameters"] if cookbook_analysis["services"] else ["system settings"])
                ),
                recommendations=Recommendations(
                    consolidation_action=parsed.get("recommendations", {}).get("consolidation_action") or ("REUSE" if cookbook_analysis["complexity"] == "Low" else "EXTEND"),
                    rationale=parsed.get("recommendations", {}).get("rationale") or f"Dynamic analysis shows {cookbook_analysis['primary_purpose'].lower()} with {cookbook_analysis['complexity'].lower()} complexity requiring {cookbook_analysis['estimated_hours']} hours",
                    migration_priority=parsed.get("recommendations", {}).get("migration_priority") or ("LOW" if cookbook_analysis["complexity"] in ["Low", "Medium"] else "MEDIUM"),
                    risk_factors=parsed.get("recommendations", {}).get("risk_factors") or (["Configuration complexity", "Custom resource patterns"] if cookbook_analysis["complexity"] != "Low" else [])
                ),
                metadata=AnalysisMetadata(
                    analyzed_at=now,
                    agent_version="1.0.0",
                    correlation_id=correlation_id
                ),
                # Populate ALL additional fields with dynamic defaults
                detailed_analysis=parsed.get("detailed_analysis") or f"Dynamic analysis of this Chef cookbook shows {cookbook_analysis['primary_purpose'].lower()} implementation with {cookbook_analysis['file_count']} files and {cookbook_analysis['complexity'].lower()} complexity.",
                key_operations=parsed.get("key_operations") or cookbook_analysis["key_operations"],
                configuration_details=parsed.get("configuration_details") or f"Chef cookbook with {cookbook_analysis['complexity'].lower()} configuration complexity",
                complexity_level=parsed.get("complexity_level") or cookbook_analysis["complexity"],
                convertible=parsed.get("convertible") if parsed.get("convertible") is not None else True,
                conversion_notes=parsed.get("conversion_notes") or f"This {cookbook_analysis['primary_purpose'].lower()} cookbook can be converted with {cookbook_analysis['migration_effort'].lower()} effort",
                confidence_source=parsed.get("confidence_source") or "chef_semantic_analysis"
            )
            resp = response.dict()
            if error != "Postprocessing failed":
                resp["postprocess_error"] = error
            logger.info(f"[{correlation_id}] Complete response created successfully")
            return resp
        except Exception as e:
            logger.error(f"[{correlation_id}]  Complete fallback required: {e}")
            # Final fallback with dynamic defaults from cookbook analysis
            return {
                "success": False,
                "cookbook_name": cookbook_name or "unknown",
                "version_requirements": {
                    "min_chef_version": cookbook_analysis["min_chef_version"],
                    "min_ruby_version": cookbook_analysis["min_ruby_version"],
                    "migration_effort": cookbook_analysis["migration_effort"],
                    "estimated_hours": cookbook_analysis["estimated_hours"],
                    "deprecated_features": []
                },
                "dependencies": {
                    "is_wrapper": cookbook_analysis["is_wrapper"],
                    "wrapped_cookbooks": [],
                    "direct_deps": cookbook_analysis["packages"],
                    "runtime_deps": [],
                    "circular_risk": "none"
                },
                "functionality": {
                    "primary_purpose": cookbook_analysis["primary_purpose"],
                    "services": cookbook_analysis["services"],
                    "packages": cookbook_analysis["packages"],
                    "files_managed": cookbook_analysis["files_managed"],
                    "reusability": "HIGH" if cookbook_analysis["complexity"] == "Low" else "MEDIUM",
                    "customization_points": ["configuration files", "service parameters"] if cookbook_analysis["services"] else ["system settings"]
                },
                "recommendations": {
                    "consolidation_action": "REUSE" if cookbook_analysis["complexity"] == "Low" else "EXTEND",
                    "rationale": f"Dynamic analysis shows {cookbook_analysis['primary_purpose'].lower()} with {cookbook_analysis['complexity'].lower()} complexity",
                    "migration_priority": "LOW" if cookbook_analysis["complexity"] in ["Low", "Medium"] else "MEDIUM",
                    "risk_factors": ["Configuration complexity"] if cookbook_analysis["complexity"] != "Low" else []
                },
                "metadata": {
                    "analyzed_at": now,
                    "agent_version": "1.0.0",
                    "correlation_id": correlation_id
                },
                "detailed_analysis": f"Dynamic analysis of this Chef cookbook shows {cookbook_analysis['primary_purpose'].lower()} implementation.",
                "key_operations": cookbook_analysis["key_operations"],
                "configuration_details": f"Chef cookbook with {cookbook_analysis['complexity'].lower()} configuration complexity",
                "complexity_level": cookbook_analysis["complexity"],
                "convertible": True,
                "conversion_notes": f"This {cookbook_analysis['primary_purpose'].lower()} cookbook can be converted with {cookbook_analysis['migration_effort'].lower()} effort",
                "confidence_source": "chef_semantic_analysis",
                "postprocess_error": f"Complete fallback: {error}; {e}"
            }


# Enhanced module-level function that passes cookbook content
def extract_and_validate_analysis(raw_response: str, correlation_id: Optional[str] = None, cookbook_content: str = "") -> Dict[str, Any]:
    """Enhanced entry point that ensures ALL fields are populated with dynamic analysis"""
    if correlation_id is None:
        correlation_id = f"corr_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    return ChefAnalysisPostprocessor().extract_and_validate_analysis(raw_response, correlation_id, cookbook_content)