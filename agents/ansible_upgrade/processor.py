import json
import logging
import re
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger("AnsibleUpgradeAnalysisProcessor")

class AnsibleUpgradeAnalysisPostprocessor:
    """Agent-driven processor that relies on ReAct agent intelligence"""
    
    def __init__(self):
        # Minimal required fields - let agent provide the intelligence
        self.required_analysis_fields = [
            "analysis_type",
            "current_state", 
            "upgrade_requirements",
            "complexity_assessment",
            "recommendations",
            "detailed_analysis"
        ]

    def extract_analysis_from_response(self, raw_response: str, correlation_id: str) -> Dict[str, Any]:
        """Extract analysis using agent's intelligence, minimal fallback"""
        
        logger.info(f"[{correlation_id}] Processing agent response ({len(raw_response)} chars)")
        
        # 1. Try to extract JSON from OBSERVATION section (where agent should put it)
        json_from_observation = self._extract_json_from_observation(raw_response, correlation_id)
        if json_from_observation:
            return self._enhance_with_react_context(json_from_observation, raw_response, correlation_id)
        
        # 2. Try to find JSON anywhere in the response
        json_anywhere = self._extract_json_from_anywhere(raw_response, correlation_id)
        if json_anywhere:
            return self._enhance_with_react_context(json_anywhere, raw_response, correlation_id)
        
        # 3. If agent provided ReAct format but no JSON, extract agent's analysis
        if any(marker in raw_response.upper() for marker in ["THOUGHT:", "ACTION:", "OBSERVATION:"]):
            return self._extract_agent_analysis_from_react(raw_response, correlation_id)
        
        # 4. Minimal fallback only if agent completely failed
        logger.warning(f"[{correlation_id}] Agent analysis extraction failed, using minimal fallback")
        return self._minimal_fallback(raw_response, correlation_id)

    def _extract_json_from_observation(self, text: str, correlation_id: str) -> Optional[Dict[str, Any]]:
        """Extract JSON specifically from OBSERVATION section where agent should put it"""
        
        # Look for OBSERVATION section
        observation_match = re.search(r'OBSERVATION:\s*(.*?)(?=THOUGHT|ACTION|$)', text, re.DOTALL | re.IGNORECASE)
        if not observation_match:
            return None
        
        observation_content = observation_match.group(1).strip()
        logger.info(f"[{correlation_id}] Found OBSERVATION section ({len(observation_content)} chars)")
        
        # Try to extract JSON from observation
        return self._parse_json_from_text(observation_content, correlation_id)

    def _extract_json_from_anywhere(self, text: str, correlation_id: str) -> Optional[Dict[str, Any]]:
        """Extract JSON from anywhere in the response"""
        
        # Look for JSON patterns
        json_patterns = [
            r'\{[\s\S]*?"success"[\s\S]*?\}',
            r'\{[\s\S]*?"analysis_type"[\s\S]*?\}',
        ]
        
        for pattern in json_patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            for match in matches:
                parsed = self._parse_json_from_text(match, correlation_id)
                if parsed and self._is_valid_analysis(parsed):
                    logger.info(f"[{correlation_id}] Found valid JSON in response")
                    return parsed
        
        return None

    def _parse_json_from_text(self, text: str, correlation_id: str) -> Optional[Dict[str, Any]]:
        """Parse JSON from text with cleaning"""
        
        try:
            # Clean up the text
            cleaned = text.strip()
            
            # Remove markdown code blocks
            if cleaned.startswith('```json'):
                cleaned = cleaned.replace('```json', '').replace('```', '').strip()
            elif cleaned.startswith('```'):
                cleaned = cleaned.replace('```', '').strip()
            
            # Try to parse
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                return parsed
                
        except json.JSONDecodeError:
            # Try to find JSON within the text
            json_start = text.find('{')
            json_end = text.rfind('}')
            if json_start != -1 and json_end != -1 and json_end > json_start:
                try:
                    json_part = text[json_start:json_end + 1]
                    return json.loads(json_part)
                except:
                    pass
        
        return None

    def _is_valid_analysis(self, data: Dict[str, Any]) -> bool:
        """Check if data looks like a valid analysis"""
        return (
            data.get("success") is not None or 
            data.get("analysis_type") == "ansible_upgrade_assessment" or
            "current_state" in data
        )

    def _enhance_with_react_context(self, json_data: Dict[str, Any], raw_response: str, correlation_id: str) -> Dict[str, Any]:
        """Enhance JSON analysis with ReAct reasoning context"""
        
        # Extract ReAct sections for context
        thought_match = re.search(r'THOUGHT:\s*(.*?)(?=ACTION|$)', raw_response, re.DOTALL | re.IGNORECASE)
        action_match = re.search(r'ACTION:\s*(.*?)(?=OBSERVATION|$)', raw_response, re.DOTALL | re.IGNORECASE)
        
        # Add clean ReAct reasoning (user-friendly)
        if thought_match or action_match:
            thought = thought_match.group(1).strip() if thought_match else ""
            action = action_match.group(1).strip() if action_match else ""
            
            # Only add if not already present
            if "react_reasoning" not in json_data:
                json_data["reasoning_summary"] = {
                    "analysis_approach": thought[:200] + "..." if len(thought) > 200 else thought,
                    "assessment_method": action[:200] + "..." if len(action) > 200 else action
                }
        
        # Ensure basic structure
        json_data["success"] = json_data.get("success", True)
        json_data["analysis_type"] = json_data.get("analysis_type", "ansible_upgrade_assessment")
        
        return json_data

    def _extract_agent_analysis_from_react(self, react_text: str, correlation_id: str) -> Dict[str, Any]:
        """Extract agent's analysis from ReAct format when no JSON found"""
        
        logger.info(f"[{correlation_id}] Extracting analysis from ReAct format")
        
        # Extract sections
        thought_match = re.search(r'THOUGHT:\s*(.*?)(?=ACTION|$)', react_text, re.DOTALL | re.IGNORECASE)
        action_match = re.search(r'ACTION:\s*(.*?)(?=OBSERVATION|$)', react_text, re.DOTALL | re.IGNORECASE)
        observation_match = re.search(r'OBSERVATION:\s*(.*?)$', react_text, re.DOTALL | re.IGNORECASE)
        
        thought = thought_match.group(1).strip() if thought_match else ""
        action = action_match.group(1).strip() if action_match else ""
        observation = observation_match.group(1).strip() if observation_match else ""
        
        # CRITICAL FIX: Check if observation contains complete JSON analysis
        if observation:
            json_in_observation = self._parse_json_from_text(observation, correlation_id)
            if json_in_observation and self._is_valid_analysis(json_in_observation):
                logger.info(f"[{correlation_id}] Found complete JSON analysis in observation!")
                # Clean up and return the agent's analysis
                return self._clean_agent_json_analysis(json_in_observation, correlation_id)
        
        # Use agent's actual analysis - extract key insights
        all_analysis = f"{thought} {action} {observation}"
        
        # Fallback: create analysis from extracted content if no JSON found
        return {
            "success": True,
            "analysis_type": "ansible_upgrade_assessment",
            "agent_analysis": {
                "thinking": thought,
                "assessment": action,
                "findings": observation
            },
            "current_state": self._extract_current_state_from_agent(all_analysis),
            "upgrade_requirements": self._extract_upgrade_requirements_from_agent(all_analysis),
            "complexity_assessment": self._extract_complexity_from_agent(all_analysis),
            "recommendations": self._extract_recommendations_from_agent(all_analysis),
            "detailed_analysis": self._extract_detailed_analysis_from_agent(thought, action, observation),
            "transformation_plan": self._extract_transformation_plan_from_agent(all_analysis),
            "session_info": {
                "correlation_id": correlation_id,
                "timestamp": datetime.utcnow().isoformat(),
                "source": "agent_react_analysis"
            }
        }

    def _clean_agent_json_analysis(self, json_data: Dict[str, Any], correlation_id: str) -> Dict[str, Any]:
        """Clean up the agent's JSON analysis for UI presentation"""
        
        # Ensure basic structure
        json_data["success"] = json_data.get("success", True)
        json_data["analysis_type"] = json_data.get("analysis_type", "ansible_upgrade_assessment")
        
        # Remove any internal ReAct terminology from fields
        if "react_reasoning" in json_data:
            # Keep it but clean it up for UI
            reasoning = json_data["react_reasoning"]
            if isinstance(reasoning, dict):
                # Clean up the reasoning text
                for key in reasoning:
                    if isinstance(reasoning[key], str):
                        reasoning[key] = reasoning[key].replace("ReAct", "").strip()
        
        # Ensure session info
        json_data["session_info"] = {
            "correlation_id": correlation_id,
            "timestamp": datetime.utcnow().isoformat(),
            "source": "agent_complete_analysis"
        }
        
        logger.info(f"[{correlation_id}] Using agent's complete JSON analysis")
        return json_data

    def _extract_current_state_from_agent(self, analysis: str) -> Dict[str, Any]:
        """Extract current state based on what agent actually found"""
        
        analysis_lower = analysis.lower()
        
        # Version estimation from agent's analysis
        version = "unknown"
        if "1.x" in analysis_lower:
            version = "1.x"
        elif "2.x" in analysis_lower:
            version = "2.x" 
        elif "2.9" in analysis_lower:
            version = "2.9"
        elif "older" in analysis_lower or "legacy" in analysis_lower:
            version = "2.9 or older"
        
        # Extract what agent actually identified
        deprecated_modules = []
        deprecated_syntax = []
        
        # Look for specific mentions in agent's analysis
        common_modules = ["yum", "apt", "service", "copy", "template", "file", "user", "group"]
        for module in common_modules:
            if module in analysis_lower:
                deprecated_modules.append(module)
        
        common_syntax = ["sudo", "with_items", "include", "action:"]
        for syntax in common_syntax:
            if syntax in analysis_lower:
                deprecated_syntax.append(syntax)
        
        return {
            "estimated_version": version,
            "deprecated_modules": deprecated_modules,
            "deprecated_syntax": deprecated_syntax,
            "has_collections_block": "collections" in analysis_lower,
            "complexity_indicators": self._extract_complexity_indicators_from_agent(analysis)
        }

    def _extract_complexity_indicators_from_agent(self, analysis: str) -> list:
        """Extract complexity indicators based on agent's assessment"""
        
        indicators = []
        analysis_lower = analysis.lower()
        
        if "simple" in analysis_lower or "minimal" in analysis_lower:
            indicators.append("low_complexity")
        elif "complex" in analysis_lower or "multiple" in analysis_lower:
            indicators.append("high_complexity")
        else:
            indicators.append("moderate_complexity")
        
        if "legacy" in analysis_lower:
            indicators.append("legacy_patterns")
        if "deprecated" in analysis_lower:
            indicators.append("deprecated_elements")
        
        return indicators

    def _extract_upgrade_requirements_from_agent(self, analysis: str) -> Dict[str, Any]:
        """Extract upgrade requirements from agent's analysis"""
        
        analysis_lower = analysis.lower()
        
        fqcn_needed = []
        syntax_needed = []
        collections_needed = ["ansible.builtin"]
        structural_needed = []
        
        # Extract based on agent's findings
        if "fqcn" in analysis_lower:
            fqcn_needed.append("convert_to_fqcn")
        if "collections" in analysis_lower and "add" in analysis_lower:
            structural_needed.append("add_collections_block")
        if "sudo" in analysis_lower:
            syntax_needed.append("replace_sudo_with_become")
        
        return {
            "fqcn_conversions_needed": fqcn_needed,
            "syntax_modernizations_needed": syntax_needed,
            "collections_to_add": collections_needed,
            "structural_changes_needed": structural_needed
        }

    def _extract_complexity_from_agent(self, analysis: str) -> Dict[str, Any]:
        """Extract complexity assessment from agent's analysis"""
        
        analysis_lower = analysis.lower()
        
        # Determine level based on agent's language
        if "simple" in analysis_lower or "minimal" in analysis_lower or "low" in analysis_lower:
            level = "LOW"
            effort = 2.0
            risk = "LOW"
        elif "complex" in analysis_lower or "difficult" in analysis_lower or "high" in analysis_lower:
            level = "HIGH" 
            effort = 12.0
            risk = "HIGH"
        else:
            level = "MEDIUM"
            effort = 6.0
            risk = "MEDIUM"
        
        factors = []
        if "legacy" in analysis_lower:
            factors.append("legacy_codebase")
        if "multiple" in analysis_lower:
            factors.append("multiple_changes_needed")
        if "minimal" in analysis_lower:
            factors.append("straightforward_upgrade")
        
        return {
            "level": level,
            "factors": factors,
            "estimated_effort_hours": effort,
            "risk_level": risk
        }

    def _extract_recommendations_from_agent(self, analysis: str) -> Dict[str, Any]:
        """Extract recommendations from agent's analysis"""
        
        analysis_lower = analysis.lower()
        
        # Priority based on agent's assessment
        if "urgent" in analysis_lower or "critical" in analysis_lower:
            priority = "CRITICAL"
        elif "high" in analysis_lower or "important" in analysis_lower:
            priority = "HIGH"
        elif "low" in analysis_lower or "minimal" in analysis_lower:
            priority = "LOW"
        else:
            priority = "MEDIUM"
        
        return {
            "upgrade_priority": priority,
            "upgrade_approach": "INCREMENTAL",
            "key_considerations": ["Follow agent's analysis recommendations"],
            "ansible_equivalent_approach": "Modern Ansible with FQCN and collections"
        }

    def _extract_detailed_analysis_from_agent(self, thought: str, action: str, observation: str) -> str:
        """Create detailed analysis from agent's reasoning"""
        
        # Use agent's actual analysis
        summary_parts = []
        
        if thought:
            summary_parts.append(f"Analysis: {thought[:100]}...")
        if action:
            summary_parts.append(f"Approach: {action[:100]}...")
        if observation:
            summary_parts.append(f"Findings: {observation[:100]}...")
        
        if not summary_parts:
            return "Agent completed analysis of Ansible content for upgrade assessment."
        
        return " ".join(summary_parts)

    def _extract_transformation_plan_from_agent(self, analysis: str) -> Dict[str, Any]:
        """Extract transformation plan from agent's analysis"""
        
        # Default plan based on common upgrade patterns
        return {
            "step_1": "Review agent analysis findings",
            "step_2": "Apply recommended modernizations",
            "step_3": "Test updated playbook",
            "step_4": "Validate functionality"
        }

    def _minimal_fallback(self, raw_response: str, correlation_id: str) -> Dict[str, Any]:
        """Minimal fallback when agent analysis completely fails"""
        
        logger.warning(f"[{correlation_id}] Using minimal fallback - agent analysis failed")
        
        return {
            "success": False,
            "error": "Agent analysis parsing failed",
            "analysis_type": "ansible_upgrade_assessment",
            "current_state": {
                "estimated_version": "unknown",
                "deprecated_modules": [],
                "deprecated_syntax": [],
                "has_collections_block": False,
                "complexity_indicators": ["analysis_failed"]
            },
            "upgrade_requirements": {
                "fqcn_conversions_needed": [],
                "syntax_modernizations_needed": [],
                "collections_to_add": ["ansible.builtin"],
                "structural_changes_needed": []
            },
            "complexity_assessment": {
                "level": "UNKNOWN",
                "factors": ["analysis_incomplete"],
                "estimated_effort_hours": 0,
                "risk_level": "UNKNOWN"
            },
            "recommendations": {
                "upgrade_priority": "UNKNOWN",
                "upgrade_approach": "MANUAL_REVIEW",
                "key_considerations": ["Manual analysis required"],
                "ansible_equivalent_approach": "Modern Ansible with FQCN and collections"
            },
            "detailed_analysis": "Automated analysis failed. Manual review of Ansible content required.",
            "transformation_plan": {
                "step_1": "Manual analysis required",
                "step_2": "Identify patterns manually", 
                "step_3": "Plan upgrades manually",
                "step_4": "Implement and test"
            },
            "session_info": {
                "correlation_id": correlation_id,
                "timestamp": datetime.utcnow().isoformat(),
                "fallback_reason": "Agent analysis extraction failed"
            }
        }

def extract_and_validate_analysis(raw_response: str, correlation_id: str, ansible_content: str = "") -> Dict[str, Any]:
    """
    Main entry point - relies on agent intelligence, minimal processing
    """
    
    if correlation_id is None:
        correlation_id = f"analysis_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    
    processor = AnsibleUpgradeAnalysisPostprocessor()
    
    # Let the agent do the work - just extract and clean up
    analysis_result = processor.extract_analysis_from_response(raw_response, correlation_id)
    
    # Add metadata and content reference
    if ansible_content:
        analysis_result["original_content_length"] = len(ansible_content)
        analysis_result["original_content_preview"] = ansible_content[:200] + "..." if len(ansible_content) > 200 else ansible_content
    
    logger.info(f"[{correlation_id}] Agent-driven analysis extraction completed")
    return analysis_result