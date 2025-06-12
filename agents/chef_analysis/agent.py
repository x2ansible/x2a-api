# agents/chef_analysis/agent.py
"""
ChefAnalysisAgent 
"""

import time
import uuid
import json
import logging
from typing import Dict, Any, Optional, AsyncGenerator

from llama_stack_client import LlamaStackClient
from llama_stack_client.types import UserMessage

from agents.chef_analysis.utils import create_correlation_id
from agents.chef_analysis.processor import extract_and_validate_analysis
from shared.exceptions import CookbookAnalysisError
from shared.log_utils import create_chef_logger, ChefAnalysisLogger

logger = logging.getLogger(__name__)

class ChefAnalysisAgent:
    """
    ChefAnalysisAgent for analyzing Chef cookbooks using LlamaStack.

    """

    def __init__(
        self, 
        client: LlamaStackClient, 
        agent_id: str, 
        session_id: str, 
        timeout: int = 120
    ):
        self.client = client
        self.agent_id = agent_id
        self.session_id = session_id
        self.timeout = timeout
        self.logger = create_chef_logger("init")

        self.logger.info(f"🍳 ChefAnalysisAgent initialized - agent_id: {agent_id}, session_id: {session_id}")

    def create_new_session(self, correlation_id: str) -> str:
        """Create a new agent session for this specific analysis."""
        try:
            session_name = f"chef-analysis-{correlation_id}-{uuid.uuid4()}"
            response = self.client.agents.session.create(
                agent_id=self.agent_id,
                session_name=session_name,
            )
            session_id = response.session_id
            self.logger.info(f"Created new session: {session_id} for correlation: {correlation_id}")
            return session_id
        except Exception as e:
            self.logger.error(f"Failed to create session: {e}")
            self.logger.info(f"↩️ Falling back to default session: {self.session_id}")
            return self.session_id

    async def analyze_cookbook(
        self,
        cookbook_data: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main analysis method using standard single-prompt approach.
        """
        correlation_id = correlation_id or create_correlation_id()
        logger = create_chef_logger(correlation_id)
        start_time = time.time()

        cookbook_name = cookbook_data.get("name", "unknown")
        files = cookbook_data.get("files", {})

        logger.log_cookbook_analysis_start(cookbook_name, len(files))
        logger.info("🔄 Using standard analysis method")

        try:
            if not files:
                raise ValueError("Cookbook must contain at least one file")

            cookbook_content = self._format_cookbook_content(cookbook_name, files)
            logger.info(f"📄 Formatted cookbook: {len(cookbook_content)} chars")

            # Create dedicated session for this analysis
            analysis_session_id = self.create_new_session(correlation_id)

            # Execute standard analysis
            analysis_result = await self._analyze_with_retries(
                cookbook_content, correlation_id, logger, analysis_session_id
            )

            total_time = time.time() - start_time
            logger.log_analysis_completion(analysis_result, total_time)

            if isinstance(analysis_result, dict):
                analysis_result["cookbook_name"] = cookbook_name
                analysis_result["analysis_method"] = "standard"
                analysis_result["session_info"] = {
                    "agent_id": self.agent_id,
                    "session_id": analysis_session_id,
                    "correlation_id": correlation_id,
                    "method_used": "standard"
                }
            return analysis_result

        except Exception as e:
            total_time = time.time() - start_time
            logger.error(f"Analysis failed after {total_time:.3f}s: {str(e)}")
            raise CookbookAnalysisError(f"Analysis failed: {str(e)}")

    async def _analyze_with_retries(
        self, 
        cookbook_content: str, 
        correlation_id: str, 
        logger: ChefAnalysisLogger, 
        session_id: str
    ) -> Dict[str, Any]:
        """
        Standard analysis with retry logic.
        """
        try:
            logger.info("🔄 Starting standard analysis")
            result = await self._analyze_direct(cookbook_content, correlation_id, logger, session_id)
            if result and result.get("success") and not result.get("postprocess_error"):
                logger.info("Standard analysis succeeded")
                return result
            else:
                logger.warning(f"⚠️ Standard analysis failed: {result}")
        except Exception as e:
            logger.warning(f"⚠️ Standard analysis failed with exception: {e}")
        
        logger.warning("⚠️ LLM analysis failed - processor will handle intelligent fallback")
        return extract_and_validate_analysis("{}", correlation_id, cookbook_content)

    async def _analyze_direct(
        self, 
        cookbook_content: str, 
        correlation_id: str, 
        logger: ChefAnalysisLogger, 
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Direct analysis using LlamaStack API.
        """
        prompt = self._create_analysis_prompt(cookbook_content)
        
        try:
            messages = [UserMessage(role="user", content=prompt)]
            generator = self.client.agents.turn.create(
                agent_id=self.agent_id,
                session_id=session_id,
                messages=messages,
                stream=True,
            )
            
            turn = None
            for chunk in generator:
                event = chunk.event
                event_type = event.payload.event_type
                if event_type == "turn_complete":
                    turn = event.payload.turn
                    break
            
            if not turn:
                logger.error("No turn completed in response")
                return None
            
            raw_response = turn.output_message.content
            logger.info(f"📥 Received response: {len(raw_response)} chars")
            
            result = extract_and_validate_analysis(raw_response, correlation_id, cookbook_content)
            logger.info(f"🔍 Processor returned: success={result.get('success')}")
            return result
            
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            return None

    def _create_analysis_prompt(self, cookbook_content: str) -> str:
        """
        Create comprehensive analysis prompt for Chef cookbook analysis.
        """
        return f"""Analyze this Chef cookbook and provide a comprehensive analysis. Return ONLY valid JSON with your analysis.

<COOKBOOK>
{cookbook_content}
</COOKBOOK>

Please analyze the cookbook and provide the following information in JSON format:

1. VERSION REQUIREMENTS:
   - Minimum Chef version required (if determinable)
   - Minimum Ruby version required (if determinable)
   - Migration effort estimate (LOW/MEDIUM/HIGH)
   - Estimated migration hours
   - Any deprecated features found

2. DEPENDENCIES:
   - Whether this is a wrapper cookbook
   - List of wrapped cookbooks (from include_recipe calls)
   - Direct dependencies (from metadata.rb)
   - Runtime dependencies
   - Circular dependency risk assessment

3. FUNCTIONALITY:
   - Primary purpose of the cookbook
   - Services managed
   - Packages installed
   - Key files/directories managed
   - Reusability level (LOW/MEDIUM/HIGH)
   - Customization points

4. RECOMMENDATIONS:
   - Consolidation action (REUSE/EXTEND/RECREATE)
   - Detailed rationale
   - Migration priority (LOW/MEDIUM/HIGH/CRITICAL)
   - Risk factors to consider
   - Recommended migration steps

Return the analysis in this JSON structure:
{{
    "success": true,
    "version_requirements": {{
        "min_chef_version": "version or null",
        "min_ruby_version": "version or null", 
        "migration_effort": "LOW|MEDIUM|HIGH",
        "estimated_hours": number_or_null,
        "deprecated_features": ["list of deprecated features"]
    }},
    "dependencies": {{
        "is_wrapper": true_or_false,
        "wrapped_cookbooks": ["list of cookbooks"],
        "direct_deps": ["dependencies from metadata"],
        "runtime_deps": ["runtime dependencies"],
        "circular_risk": "none|low|medium|high"
    }},
    "functionality": {{
        "primary_purpose": "description",
        "services": ["list of services"],
        "packages": ["list of packages"],
        "files_managed": ["key files/directories"],
        "reusability": "LOW|MEDIUM|HIGH",
        "customization_points": ["customization areas"]
    }},
    "recommendations": {{
        "consolidation_action": "REUSE|EXTEND|RECREATE",
        "rationale": "detailed explanation",
        "migration_priority": "LOW|MEDIUM|HIGH|CRITICAL",
        "risk_factors": ["list of risks"],
        "migration_steps": ["recommended steps"]
    }}
}}

CRITICAL: Return ONLY the JSON object with your actual analysis values."""

    def _format_cookbook_content(self, cookbook_name: str, files: Dict[str, str]) -> str:
        """Format cookbook content for analysis."""
        content_parts = [f"Cookbook Name: {cookbook_name}"]
        for filename, content in files.items():
            content_parts.append(f"\n=== File: {filename} ===")
            content_parts.append(content.strip())
        return "\n".join(content_parts)

    async def analyze_cookbook_stream(
        self,
        cookbook_data: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Streaming version with progress reporting.
        """
        correlation_id = correlation_id or create_correlation_id()
        cookbook_name = cookbook_data.get("name", "unknown")
        
        try:
            yield {
                "type": "progress",
                "status": "starting",
                "message": "🍳 Chef cookbook analysis started",
                "correlation_id": correlation_id
            }
            
            yield {
                "type": "progress", 
                "status": "processing",
                "message": "🔍 Analyzing cookbook structure and dependencies",
                "progress": 0.5,
                "correlation_id": correlation_id
            }
            
            result = await self.analyze_cookbook(cookbook_data, correlation_id)
            
            yield {
                "type": "final_analysis",
                "data": result,
                "correlation_id": correlation_id
            }
            
        except Exception as e:
            yield {
                "type": "error",
                "error": str(e),
                "correlation_id": correlation_id
            }

    def get_status(self) -> Dict[str, Any]:
        """Get current status of the agent."""
        return {
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "client_base_url": self.client.base_url,
            "timeout": self.timeout,
            "status": "ready",
            "approach": "standard",
            "methods_available": ["standard"]
        }

    async def health_check(self) -> bool:
        """Perform a health check on the agent."""
        try:
            messages = [UserMessage(role="user", content="Health check - please respond with 'OK'")]
            generator = self.client.agents.turn.create(
                agent_id=self.agent_id,
                session_id=self.session_id,
                messages=messages,  
                stream=True,
            )
            for chunk in generator:
                break
            self.logger.info("Health check passed")
            return True
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return False