import json
import re
from datetime import datetime
import logging
from typing import Dict, Any, Optional

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
    Postprocesses and validates the output of the Chef Analysis LLM agent.
    Ensures that the response strictly conforms to expected schema, even if LLM output is imperfect.
    """

    def __init__(self):
        self.required_sections = [
            "version_requirements",
            "dependencies",
            "functionality",
            "recommendations"
        ]

    def extract_and_validate_analysis(self, raw_response: str, correlation_id: str) -> Dict[str, Any]:
        """
        Takes the raw LLM output (possibly with markdown, code blocks, or imperfect JSON),
        extracts the JSON, validates it, and returns a dictionary ready for API output.
        Always returns a valid `CookbookAnalysisResponse` dict, with success False if postprocessing fails.
        """
        # 1. Try direct JSON parse
        if isinstance(raw_response, dict):
            parsed = raw_response
        else:
            parsed = self._extract_json_from_text(raw_response, correlation_id)
        
        cookbook_name = parsed.get("cookbook_name", "unknown")
        # 2. Add metadata
        parsed["metadata"] = {
            "analyzed_at": datetime.utcnow().isoformat(),
            "agent_version": None,
            "correlation_id": correlation_id
        }
        parsed["success"] = True
        parsed["cookbook_name"] = cookbook_name

        # 3. Validate and coerce using Pydantic
        try:
            response = CookbookAnalysisResponse(**parsed)
            logger.info(f"[{correlation_id}]  Analysis response validated and structured.")
            return response.dict()
        except Exception as e:
            logger.error(f"[{correlation_id}]  Validation failed: {e}")
            # Try to build with as much as possible, fill in defaults where missing
            return self._make_default_response(parsed, correlation_id, cookbook_name, error=str(e))

    def _extract_json_from_text(self, text: str, correlation_id: str) -> Dict[str, Any]:
        """
        Attempts to robustly extract JSON from the LLM output,
        which might be surrounded by text, markdown, or code blocks.
        """
        # Remove code blocks if present
        code_block_match = re.search(r"```json\s*(\{.*\})\s*```", text, re.DOTALL | re.IGNORECASE)
        if code_block_match:
            text = code_block_match.group(1)
        else:
            # Try generic triple-backtick
            code_block_match = re.search(r"```\s*(\{.*\})\s*```", text, re.DOTALL)
            if code_block_match:
                text = code_block_match.group(1)
        # Try to parse JSON
        try:
            return json.loads(text)
        except Exception:
            # Fallback: Find first curly-brace block (naive but robust)
            brace_match = re.search(r"(\{.*\})", text, re.DOTALL)
            if brace_match:
                try:
                    return json.loads(brace_match.group(1))
                except Exception:
                    pass
        # As a last resort, return minimal default structure with error
        logger.error(f"[{correlation_id}]  Could not extract JSON from LLM output.")
        return {}

    def _make_default_response(
        self, 
        parsed: Dict[str, Any], 
        correlation_id: str, 
        cookbook_name: str,
        error: str = "Postprocessing failed"
    ) -> Dict[str, Any]:
        """
        Builds a valid API response using as much valid info as available, filling missing fields with safe defaults.
        Always returns success: False.
        """
        now = datetime.utcnow().isoformat()
        # Provide defaults for each section
        version_requirements = parsed.get("version_requirements") or {}
        dependencies = parsed.get("dependencies") or {}
        functionality = parsed.get("functionality") or {}
        recommendations = parsed.get("recommendations") or {}

        try:
            response = CookbookAnalysisResponse(
                success=False,  # Explicitly mark as failed
                cookbook_name=cookbook_name or "unknown",
                version_requirements=VersionRequirements(**version_requirements),
                dependencies=Dependencies(**dependencies),
                functionality=Functionality(**functionality),
                recommendations=Recommendations(**recommendations),
                metadata=AnalysisMetadata(
                    analyzed_at=now,
                    agent_version=None,
                    correlation_id=correlation_id
                ),
                detailed_analysis=parsed.get("detailed_analysis"),
                key_operations=parsed.get("key_operations", []),
                configuration_details=parsed.get("configuration_details"),
                complexity_level=parsed.get("complexity_level"),
                convertible=parsed.get("convertible"),
                conversion_notes=parsed.get("conversion_notes"),
                confidence_source=parsed.get("confidence_source", "ai_semantic")
            )
            resp = response.dict()
            resp["postprocess_error"] = error
            return resp
        except Exception as e:
            # If all else fails, fully fallback
            logger.error(f"[{correlation_id}]  Complete fallback: {e}")
            return {
                "success": False,
                "cookbook_name": cookbook_name or "unknown",
                "version_requirements": {},
                "dependencies": {},
                "functionality": {},
                "recommendations": {},
                "metadata": {
                    "analyzed_at": now,
                    "agent_version": None,
                    "correlation_id": correlation_id,
                    "postprocess_error": f"Total fallback: {error}; {e}"
                }
            }

# For module-level convenience:
def extract_and_validate_analysis(raw_response: str, correlation_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Entry point for routes/handlers.
    """
    if correlation_id is None:
        correlation_id = f"corr_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    return ChefAnalysisPostprocessor().extract_and_validate_analysis(raw_response, correlation_id)
