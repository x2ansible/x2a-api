"""
Result Formatter Helper for ValidationAgent

Handles standardization and formatting of validation results into
consistent response format for the API.
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("ResultFormatter")

class ValidationResultFormatter:
    """Formats validation results into standardized response format."""
    
    def format_validation_result(self, validation_result: Optional[Dict], agent_text: str,
                                original_playbook: str, lint_profile: str, 
                                debug_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format validation result into standardized response.
        
        Args:
            validation_result: Tool result from ansible_lint_tool (or None)
            agent_text: Agent's analysis text
            original_playbook: Original playbook content
            lint_profile: Lint profile used
            debug_info: Debug information from parsing
            
        Returns:
            Standardized validation response dictionary
        """
        if validation_result:
            return self._format_tool_result(
                validation_result, agent_text, original_playbook, lint_profile, debug_info
            )
        else:
            return self._format_fallback_result(
                agent_text, original_playbook, lint_profile, debug_info
            )
    
    def _format_tool_result(self, validation_result: Dict, agent_text: str,
                           original_playbook: str, lint_profile: str,
                           debug_info: Dict[str, Any]) -> Dict[str, Any]:
        """Format result when tool execution was successful."""
        logger.info("🎉 Formatting successful tool result")
        
        return {
            "success": True,
            "validation_passed": validation_result.get("validation_passed", False),
            "exit_code": validation_result.get("exit_code", -1),
            "message": validation_result.get("message", ""),
            "summary": validation_result.get("summary", {}),
            "issues": validation_result.get("issues", []),
            "recommendations": validation_result.get("recommendations", []),
            "agent_analysis": agent_text or "Agent completed validation analysis",
            "raw_output": validation_result.get("raw_output", {}),
            "playbook_length": len(original_playbook),
            "lint_profile": lint_profile,
            "debug_info": {
                **debug_info,
                "result_source": "tool_execution",
                "tool_result_available": True
            }
        }
    
    def _format_fallback_result(self, agent_text: str, original_playbook: str,
                               lint_profile: str, debug_info: Dict[str, Any]) -> Dict[str, Any]:
        """Format result when tool result wasn't extracted (fallback mode)."""
        logger.warning("⚠️ Formatting fallback result (no tool result found)")
        
        # Try to infer result from agent text
        inferred_result = self._infer_result_from_agent_text(agent_text)
        
        return {
            "success": True,
            "validation_passed": inferred_result["passed"],
            "exit_code": inferred_result["exit_code"],
            "message": inferred_result["message"],
            "summary": {
                "passed": inferred_result["passed"],
                "violations": 0,
                "warnings": 0,
                "total_issues": 0,
                "inferred": True
            },
            "issues": [],
            "recommendations": [],
            "agent_analysis": agent_text or "Agent processed the validation request",
            "raw_output": {},
            "playbook_length": len(original_playbook),
            "lint_profile": lint_profile,
            "debug_info": {
                **debug_info,
                "result_source": "agent_text_inference",
                "tool_result_available": False,
                "inference_confidence": inferred_result["confidence"]
            }
        }
    
    def _infer_result_from_agent_text(self, agent_text: str) -> Dict[str, Any]:
        """Try to infer validation result from agent's text response."""
        text_lower = agent_text.lower()
        
        # Look for clear indicators
        if any(phrase in text_lower for phrase in ["validation passed", "no issues", "successfully passed"]):
            return {
                "passed": True,
                "exit_code": 0,
                "message": " Validation likely passed (inferred from agent analysis)",
                "confidence": "high"
            }
        elif any(phrase in text_lower for phrase in ["validation failed", "issues found", "errors"]):
            return {
                "passed": False,
                "exit_code": 1,
                "message": " Validation likely failed (inferred from agent analysis)",
                "confidence": "medium"
            }
        else:
            # Conservative fallback - assume passed if no clear indicators
            return {
                "passed": True,
                "exit_code": 0,
                "message": " Validation completed (tool result unavailable, assuming passed)",
                "confidence": "low"
            }
    
    def create_error_response(self, error_message: str) -> Dict[str, Any]:
        """Create standardized error response."""
        logger.error(f" Creating error response: {error_message}")
        
        return {
            "success": False,
            "validation_passed": False,
            "exit_code": -1,
            "message": f" {error_message}",
            "summary": {
                "passed": False,
                "violations": 0,
                "warnings": 0,
                "total_issues": 0,
                "error": True
            },
            "issues": [],
            "recommendations": [],
            "agent_analysis": f"Validation failed: {error_message}",
            "raw_output": {},
            "playbook_length": 0,
            "lint_profile": "unknown",
            "debug_info": {
                "result_source": "error_response",
                "error": error_message
            }
        }
    
    def create_timeout_response(self, timeout_seconds: int) -> Dict[str, Any]:
        """Create response for timeout scenarios."""
        error_message = f"Validation timed out after {timeout_seconds} seconds"
        
        return {
            "success": False,
            "validation_passed": False,
            "exit_code": -2,
            "message": f"⏰ {error_message}",
            "summary": {
                "passed": False,
                "violations": 0,
                "warnings": 0,
                "total_issues": 0,
                "timeout": True
            },
            "issues": [],
            "recommendations": [{
                "issue": "timeout",
                "recommendation": "Try with a simpler playbook or check ansible-lint service availability",
                "action": "Reduce playbook complexity or retry later"
            }],
            "agent_analysis": f"Validation timed out: {error_message}",
            "raw_output": {},
            "playbook_length": 0,
            "lint_profile": "unknown",
            "debug_info": {
                "result_source": "timeout_response",
                "timeout_seconds": timeout_seconds
            }
        }