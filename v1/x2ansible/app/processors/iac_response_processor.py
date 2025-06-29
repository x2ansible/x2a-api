# app/processors/iac_response_processor.py - Extract structured data from ReAct agent responses

import json
import re
import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import hashlib

logger = logging.getLogger(__name__)

class IaCResponseProcessor:
    """
    Processes ReAct agent responses and extracts structured IaC analysis data
    """
    
    def __init__(self):
        self.technology_patterns = {
            'chef': ['cookbook', 'recipe', 'chef-client', 'node[', 'include_recipe'],
            'salt': ['salt://', 'pillar', 'state.apply', 'grain', '.sls'],
            'ansible': ['hosts:', 'tasks:', 'playbook', 'ansible_', 'vars:'],
            'terraform': ['resource', 'provider', 'variable', 'output', 'module'],
            'puppet': ['class', 'define', 'include', 'ensure', 'puppet'],
            'shell': ['#!/bin/', 'bash', 'systemctl', 'service', 'yum', 'apt'],
            'bladelogic': ['bladelogic', 'rscd', 'nsh', 'bl', 'server automation']
        }

    def process_react_response(self, raw_response: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a ReAct agent response and extract structured IaC analysis
        
        Args:
            raw_response: The raw response from ReAct agent
            context: Additional context (file info, etc.)
            
        Returns:
            Structured IaC analysis JSON
        """
        try:
            # Extract reasoning steps and content
            reasoning_steps = self._extract_reasoning_steps(raw_response)
            analysis_content = self._extract_analysis_content(reasoning_steps)
            
            # Get file information from context
            files_analyzed = context.get('files_analyzed', [])
            technology_type = context.get('technology_type', 'unknown')
            
            # Build structured response
            structured_analysis = self._build_structured_analysis(
                analysis_content, 
                files_analyzed, 
                technology_type,
                context
            )
            
            return {
                "success": True,
                "analysis_type": "iac_react_analysis",
                "react_reasoning": {
                    "total_steps": len(reasoning_steps),
                    "reasoning_phases": self._identify_reasoning_phases(reasoning_steps)
                },
                "structured_data": structured_analysis,
                "metadata": {
                    "files_analyzed": files_analyzed,
                    "technology_type": technology_type,
                    "analysis_timestamp": datetime.utcnow().isoformat(),
                    "processor_version": "1.0.0"
                }
            }
            
        except Exception as e:
            logger.error(f"Error processing ReAct response: {str(e)}")
            return {
                "success": False,
                "error": f"Response processing failed: {str(e)}",
                "analysis_type": "iac_react_analysis"
            }

    def _extract_reasoning_steps(self, raw_response: Any) -> List[Dict[str, Any]]:
        """Extract reasoning steps from ReAct response"""
        steps = []
        
        try:
            if hasattr(raw_response, 'steps') and raw_response.steps:
                for i, step in enumerate(raw_response.steps):
                    step_content = self._extract_step_content(step)
                    
                    steps.append({
                        "step_number": i + 1,
                        "step_type": type(step).__name__,
                        "content": step_content,
                        "thought": self._extract_thought(step_content),
                        "action": self._extract_action(step_content),
                        "observation": self._extract_observation(step_content)
                    })
            
        except Exception as e:
            logger.warning(f"Error extracting reasoning steps: {str(e)}")
        
        return steps

    def _extract_step_content(self, step: Any) -> str:
        """Extract content from a single step"""
        try:
            # Try multiple content extraction methods
            if hasattr(step, 'content'):
                return str(step.content)
            elif hasattr(step, 'api_model_response') and hasattr(step.api_model_response, 'content'):
                return str(step.api_model_response.content)
            elif hasattr(step, 'output_message') and hasattr(step.output_message, 'content'):
                return str(step.output_message.content)
            else:
                return str(step)
        except:
            return ""

    def _extract_thought(self, content: str) -> Optional[str]:
        """Extract thought from step content"""
        patterns = [
            r'(?:THOUGHT|Thought):\s*(.+?)(?=(?:ACTION|Action):|$)',
            r'(?:Think|THINK):\s*(.+?)(?=(?:ACT|Act):|$)',
            r'"thought":\s*"([^"]+)"'
        ]
        
        for pattern in patterns:
            try:
                match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
                if match:
                    return match.group(1).strip()
            except re.error as e:
                logger.warning(f"Regex error in thought extraction: {e}")
                continue
        
        return None

    def _extract_action(self, content: str) -> Optional[str]:
        """Extract action from step content"""
        patterns = [
            r'(?:ACTION|Action):\s*(.+?)(?=(?:OBSERVATION|Observation):|$)',
            r'(?:ACT|Act):\s*(.+?)(?=(?:OBSERVE|Observe):|$)',
            r'"action":\s*"([^"]+)"'
        ]
        
        for pattern in patterns:
            try:
                match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
                if match:
                    return match.group(1).strip()
            except re.error as e:
                logger.warning(f"Regex error in action extraction: {e}")
                continue
        
        return None

    def _extract_observation(self, content: str) -> Optional[str]:
        """Extract observation from step content"""
        patterns = [
            r'(?:OBSERVATION|Observation):\s*(.+?)$',
            r'(?:OBSERVE|Observe):\s*(.+?)$',
            r'"observation":\s*"([^"]+)"'
        ]
        
        for pattern in patterns:
            try:
                match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
                if match:
                    return match.group(1).strip()
            except re.error as e:
                logger.warning(f"Regex error in observation extraction: {e}")
                continue
        
        return None

    def _extract_analysis_content(self, reasoning_steps: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract key analysis insights from reasoning steps"""
        analysis = {
            "resources": [],
            "services": [],
            "packages": [],
            "files_managed": [],
            "dependencies": [],
            "complexity_factors": [],
            "purpose": "",
            "technology": "",
            "recommendations": []
        }
        
        # Combine all content for analysis
        all_content = ""
        for step in reasoning_steps:
            if step.get("content"):
                all_content += step["content"] + "\n"
        
        # Extract resources using patterns
        analysis["resources"] = self._extract_resources(all_content)
        analysis["services"] = self._extract_services(all_content)
        analysis["packages"] = self._extract_packages(all_content)
        analysis["files_managed"] = self._extract_files(all_content)
        analysis["dependencies"] = self._extract_dependencies(all_content)
        analysis["complexity_factors"] = self._extract_complexity_factors(all_content)
        analysis["purpose"] = self._extract_purpose(all_content)
        analysis["technology"] = self._detect_technology(all_content)
        analysis["recommendations"] = self._extract_recommendations(all_content)
        
        return analysis

    def _extract_resources(self, content: str) -> List[Dict[str, str]]:
        """Extract resources mentioned in the analysis"""
        resources = []
        
        # Common resource patterns - fixed regex
        patterns = {
            "package": r'(?:package|install)\s+[\'"]?([a-zA-Z0-9\-_\.]+)',
            "service": r'(?:service|systemd)\s+[\'"]?([a-zA-Z0-9\-_\.]+)',
            "file": r'(?:file|template|copy)\s+[\'"]?([/\w\-_\.]+)',
            "directory": r'(?:directory|mkdir)\s+[\'"]?([/\w\-_\.]+)'
        }
        
        for resource_type, pattern in patterns.items():
            try:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for match in matches:
                    if match and len(match) > 1:  # Filter out single characters
                        resources.append({
                            "type": resource_type,
                            "name": match.strip()
                        })
            except re.error as e:
                logger.warning(f"Regex error in {resource_type} pattern: {e}")
                continue
        
        return resources

    def _extract_services(self, content: str) -> List[str]:
        """Extract service names"""
        services = set()
        patterns = [
            r'(?:service|systemctl|systemd)\s+[\'"]?([a-zA-Z0-9\-_\.]+)',
            r'([a-zA-Z0-9\-_]+)\.service',
            r'(?:start|stop|restart|enable|disable)\s+([a-zA-Z0-9\-_\.]+)'
        ]
        
        for pattern in patterns:
            try:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for match in matches:
                    if match and len(match) > 2:
                        services.add(match.strip())
            except re.error as e:
                logger.warning(f"Regex error in service extraction: {e}")
                continue
        
        return list(services)

    def _extract_packages(self, content: str) -> List[str]:
        """Extract package names"""
        packages = set()
        patterns = [
            r'(?:package|install|yum|apt|dnf)\s+[\'"]?([a-zA-Z0-9\-_\.]+)',
            r'([a-zA-Z0-9\-_]+)\s+package',
            r'install[:\s]+([a-zA-Z0-9\-_\.]+)'
        ]
        
        for pattern in patterns:
            try:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for match in matches:
                    if match and len(match) > 2:
                        packages.add(match.strip())
            except re.error as e:
                logger.warning(f"Regex error in package extraction: {e}")
                continue
        
        return list(packages)

    def _extract_files(self, content: str) -> List[str]:
        """Extract managed files"""
        files = set()
        patterns = [
            r'(?:file|template|copy)\s+[\'"]?([/\w\-_\.]+)',
            r'([/\w\-_\.]+\.\w+)',
            r'/etc/[/\w\-_\.]+',
            r'/var/[/\w\-_\.]+',
        ]
        
        for pattern in patterns:
            try:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for match in matches:
                    if '/' in match and len(match) > 3:
                        files.add(match.strip())
            except re.error as e:
                logger.warning(f"Regex error in file pattern: {e}")
                continue
        
        return list(files)

    def _extract_dependencies(self, content: str) -> List[str]:
        """Extract dependencies"""
        dependencies = set()
        patterns = [
            r'(?:depends|dependency|require)\s+[\'"]?([a-zA-Z0-9\-_\.]+)',
            r'include_recipe\s+[\'"]?([a-zA-Z0-9\-_\.]+)',
            r'(?:cookbook|module|role)\s+[\'"]?([a-zA-Z0-9\-_\.]+)'
        ]
        
        for pattern in patterns:
            try:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for match in matches:
                    if match and len(match) > 2:
                        dependencies.add(match.strip())
            except re.error as e:
                logger.warning(f"Regex error in dependency extraction: {e}")
                continue
        
        return list(dependencies)

    def _extract_complexity_factors(self, content: str) -> List[str]:
        """Extract complexity indicators"""
        factors = []
        
        complexity_indicators = [
            ("Conditional logic", r'(?:if|when|unless|case)'),
            ("Loops", r'(?:for|each|loop|iterate)'),
            ("Templates", r'(?:template|erb|j2)'),
            ("Variables", r'(?:variable|var|attribute)'),
            ("Custom resources", r'(?:custom|define|lwrp)'),
            ("Multiple environments", r'(?:environment|env|stage)'),
            ("Error handling", r'(?:rescue|exception|error|fail)')
        ]
        
        for factor, pattern in complexity_indicators:
            try:
                if re.search(pattern, content, re.IGNORECASE):
                    factors.append(factor)
            except re.error as e:
                logger.warning(f"Regex error in complexity factor '{factor}': {e}")
                continue
        
        return factors

    def _extract_purpose(self, content: str) -> str:
        """Extract the main purpose from analysis"""
        purpose_patterns = [
            r'(?:purpose|goal|objective|intent)\s*:?\s*(.{20,100})',
            r'(?:this|it)\s+(?:is|does|performs|manages)\s+(.{20,100})',
            r'(?:installs?|configures?|manages?|deploys?)\s+(.{20,100})'
        ]
        
        for pattern in purpose_patterns:
            try:
                match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
                if match:
                    purpose = match.group(1).strip()
                    purpose = re.sub(r'[.!?]+.*', '', purpose)
                    if len(purpose) > 20:
                        return purpose
            except re.error as e:
                logger.warning(f"Regex error in purpose extraction: {e}")
                continue
        
        return "Purpose not clearly identified in analysis"

    def _detect_technology(self, content: str) -> str:
        """Detect technology type from content"""
        tech_scores = {}
        
        for tech, patterns in self.technology_patterns.items():
            score = 0
            for pattern in patterns:
                try:
                    score += len(re.findall(re.escape(pattern), content, re.IGNORECASE))
                except re.error as e:
                    logger.warning(f"Regex error in technology detection for '{tech}': {e}")
                    continue
            tech_scores[tech] = score
        
        if tech_scores:
            detected_tech = max(tech_scores.items(), key=lambda x: x[1])
            if detected_tech[1] > 0:
                return detected_tech[0]
        
        return "unknown"

    def _extract_recommendations(self, content: str) -> List[str]:
        """Extract recommendations from analysis"""
        recommendations = []
        
        rec_patterns = [
            r'(?:recommend|suggest|should|could|consider)\s+(.{20,100})',
            r'(?:migration|modernization|upgrade)\s+(.{20,100})',
            r'(?:ansible|equivalent)\s+(.{20,100})'
        ]
        
        for pattern in rec_patterns:
            try:
                matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
                for match in matches:
                    rec = match.strip()
                    rec = re.sub(r'[.!?]+.*', '', rec)
                    if len(rec) > 10:
                        recommendations.append(rec)
            except re.error as e:
                logger.warning(f"Regex error in recommendation extraction: {e}")
                continue
        
        return recommendations[:5]

    def _identify_reasoning_phases(self, reasoning_steps: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Identify the reasoning phases in the steps"""
        phases = {
            "extraction_phase": [],
            "analysis_phase": [],
            "recommendation_phase": []
        }
        
        for step in reasoning_steps:
            content = step.get("content", "").lower()
            
            if any(word in content for word in ["extract", "identify", "find", "discover"]):
                phases["extraction_phase"].append(step["step_number"])
            elif any(word in content for word in ["analyze", "assess", "evaluate", "examine"]):
                phases["analysis_phase"].append(step["step_number"])
            elif any(word in content for word in ["recommend", "suggest", "migrate", "modernize"]):
                phases["recommendation_phase"].append(step["step_number"])
        
        return phases

    def _build_structured_analysis(self, analysis_content: Dict[str, Any], 
                                   files_analyzed: List[str], 
                                   technology_type: str,
                                   context: Dict[str, Any]) -> Dict[str, Any]:
        """Build the final structured analysis response"""
        
        # Generate unique ID
        content_hash = hashlib.md5(str(files_analyzed).encode()).hexdigest()[:8]
        analysis_id = f"iac:{technology_type}:analysis:{content_hash}:1.0"
        
        # Determine complexity level
        complexity_level = self._assess_complexity_level(analysis_content)
        
        return {
            "id": analysis_id,
            "module_name": self._extract_module_name(files_analyzed, analysis_content),
            "source_tool": technology_type.title(),
            "version": "1.0",
            "last_analysis_timestamp": datetime.utcnow().isoformat(),
            "summary": {
                "purpose_and_use_case": analysis_content["purpose"],
                "plain_english_description": self._generate_plain_english_description(analysis_content),
                "tags": self._generate_tags(analysis_content, technology_type)
            },
            "analytics": {
                "metrics": {
                    "total_resources": len(analysis_content["resources"]),
                    "service_count": len(analysis_content["services"]),
                    "package_count": len(analysis_content["packages"]),
                    "files_managed": len(analysis_content["files_managed"]),
                    "dependency_count": len(analysis_content["dependencies"])
                },
                "assessment": {
                    "complexity": complexity_level,
                    "risk": self._assess_risk_level(analysis_content),
                    "reasoning": self._generate_complexity_reasoning(analysis_content)
                }
            },
            "structured_analysis": {
                "resource_inventory": analysis_content["resources"],
                "key_configurations": self._build_key_configurations(analysis_content),
                "dependencies": self._build_dependencies_list(analysis_content),
                "embedded_logic": self._build_embedded_logic(analysis_content)
            },
            "react_insights": {
                "technology_detected": analysis_content["technology"],
                "complexity_factors": analysis_content["complexity_factors"],
                "recommendations": analysis_content["recommendations"]
            }
        }

    def _assess_complexity_level(self, analysis: Dict[str, Any]) -> str:
        """Assess complexity level based on analysis"""
        complexity_score = 0
        
        complexity_score += len(analysis["complexity_factors"]) * 2
        complexity_score += min(len(analysis["resources"]), 10)
        complexity_score += len(analysis["dependencies"]) * 2
        
        if complexity_score < 5:
            return "Low"
        elif complexity_score < 15:
            return "Medium"
        else:
            return "High"

    def _assess_risk_level(self, analysis: Dict[str, Any]) -> str:
        """Assess risk level"""
        risk_factors = 0
        
        if "custom" in str(analysis).lower():
            risk_factors += 1
        if len(analysis["dependencies"]) > 5:
            risk_factors += 1
        if "template" in analysis["complexity_factors"]:
            risk_factors += 1
        
        if risk_factors == 0:
            return "Low"
        elif risk_factors <= 2:
            return "Medium"
        else:
            return "High"

    def _generate_complexity_reasoning(self, analysis: Dict[str, Any]) -> str:
        """Generate reasoning for complexity assessment"""
        factors = analysis["complexity_factors"]
        if not factors:
            return "Simple automation with straightforward resource management."
        
        return f"Complexity driven by: {', '.join(factors[:3])}. " + \
               f"Manages {len(analysis['resources'])} resources with {len(analysis['dependencies'])} dependencies."

    def _extract_module_name(self, files: List[str], analysis: Dict[str, Any]) -> str:
        """Extract module name from files or analysis"""
        if files:
            first_file = files[0]
            name = first_file.split('/')[-1].split('.')[0]
            if name and len(name) > 1:
                return name
        
        if analysis["services"]:
            return analysis["services"][0]
        
        return "unknown_module"

    def _generate_plain_english_description(self, analysis: Dict[str, Any]) -> str:
        """Generate plain English description"""
        tech = analysis["technology"]
        services = analysis["services"][:3]
        packages = analysis["packages"][:3]
        
        desc = f"A {tech} automation that"
        
        if packages:
            desc += f" installs {', '.join(packages)}"
        
        if services:
            desc += f" and manages {', '.join(services)} service{'s' if len(services) > 1 else ''}"
        
        if analysis["files_managed"]:
            desc += f" along with {len(analysis['files_managed'])} configuration file{'s' if len(analysis['files_managed']) > 1 else ''}"
        
        desc += "."
        
        return desc

    def _generate_tags(self, analysis: Dict[str, Any], tech_type: str) -> List[str]:
        """Generate tags for the analysis"""
        tags = [tech_type]
        
        tags.extend(analysis["services"][:3])
        tags.extend(analysis["packages"][:3])
        
        if "template" in analysis["complexity_factors"]:
            tags.append("templating")
        if "conditional" in str(analysis["complexity_factors"]).lower():
            tags.append("conditional")
        
        return list(set(tags))

    def _build_key_configurations(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build key configurations list"""
        configs = []
        
        for service in analysis["services"][:3]:
            configs.append({
                "resource": f"service:{service}",
                "description": f"Service {service} is managed by this automation",
                "details": {"managed": True}
            })
        
        for package in analysis["packages"][:3]:
            configs.append({
                "resource": f"package:{package}",
                "description": f"Package {package} is installed and managed",
                "details": {"action": "install"}
            })
        
        return configs

    def _build_dependencies_list(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build dependencies list"""
        deps = []
        
        for dep in analysis["dependencies"]:
            deps.append({
                "name": dep,
                "type": "Module",
                "description": f"Dependency on {dep}"
            })
        
        return deps

    def _build_embedded_logic(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build embedded logic list"""
        logic = []
        
        for factor in analysis["complexity_factors"]:
            logic.append({
                "trigger": f"{factor} detected in automation",
                "action": "Conditional processing based on runtime conditions",
                "description": f"Contains {factor.lower()} that adds complexity to execution"
            })
        
        return logic