import time
import uuid
from typing import Dict, Any, Optional, AsyncGenerator
import logging
from llama_stack_client import LlamaStackClient
from llama_stack_client.types import UserMessage

from agents.chef_analysis.utils import create_correlation_id
from agents.chef_analysis.processor import extract_and_validate_analysis
from shared.exceptions import ConfigurationError, CookbookAnalysisError
from shared.log_utils import create_chef_logger, ChefAnalysisLogger, step_printer

logger = logging.getLogger(__name__)

class ChefAnalysisAgent:
    """
    ChefAnalysisAgent - Fixed version that works with single agent instance
    """
    def __init__(self, client: LlamaStackClient, agent_id: str, session_id: str, timeout: int = 120):
        self.client = client
        self.agent_id = agent_id
        self.session_id = session_id  # Default session
        self.timeout = timeout
        self.logger = create_chef_logger("init")
        self.logger.info(f"🍳 ChefAnalysisAgent initialized with agent_id: {agent_id}, session_id: {session_id}")

    def create_new_session(self, correlation_id: str) -> str:
        """
        Create a new session for this specific analysis
        """
        try:
            response = self.client.agents.session.create(
                agent_id=self.agent_id,
                session_name=f"chef-analysis-{correlation_id}-{uuid.uuid4()}",
            )
            session_id = response.session_id
            self.logger.info(f" Created new session: {session_id} for correlation: {correlation_id}")
            return session_id
        except Exception as e:
            self.logger.error(f" Failed to create session: {e}")
            # Fallback to default session
            self.logger.info(f"↩️  Falling back to default session: {self.session_id}")
            return self.session_id

    async def analyze_cookbook(
        self,
        cookbook_data: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        correlation_id = correlation_id or create_correlation_id()
        logger = create_chef_logger(correlation_id)
        start_time = time.time()

        cookbook_name = cookbook_data.get("name", "unknown")
        files = cookbook_data.get("files", {})

        logger.log_cookbook_analysis_start(cookbook_name, len(files))

        try:
            if not files:
                raise ValueError("Cookbook must contain at least one file")

            cookbook_content = self._format_cookbook_content(cookbook_name, files)
            logger.info(f"📄 Formatted cookbook: {len(cookbook_content)} chars")

            # Create dedicated session for this analysis
            analysis_session_id = self.create_new_session(correlation_id)

            analysis_result = await self._analyze_with_retries(
                cookbook_content, correlation_id, logger, analysis_session_id
            )

            total_time = time.time() - start_time
            logger.log_analysis_completion(analysis_result, total_time)

            if isinstance(analysis_result, dict):
                analysis_result["cookbook_name"] = cookbook_name
                analysis_result["session_info"] = {
                    "agent_id": self.agent_id,
                    "session_id": analysis_session_id,
                    "correlation_id": correlation_id
                }
            return analysis_result

        except Exception as e:
            total_time = time.time() - start_time
            logger.error(f" Analysis failed after {total_time:.3f}s: {str(e)}")
            raise CookbookAnalysisError(f"Analysis failed: {str(e)}")

    def _format_cookbook_content(self, cookbook_name: str, files: Dict[str, str]) -> str:
        content_parts = [f"Cookbook: {cookbook_name}"]
        for filename, content in files.items():
            content_parts.append(f"\n=== {filename} ===")
            content_parts.append(content.strip())
        return "\n".join(content_parts)

    async def _analyze_with_retries(self, cookbook_content: str, correlation_id: str, logger: ChefAnalysisLogger, session_id: str) -> Dict[str, Any]:
        try:
            logger.info("🔄 Attempt 1: Direct JSON analysis")
            result = await self._analyze_direct(cookbook_content, correlation_id, logger, session_id, "direct")
            if result and result.get("success") and not result.get("postprocess_error"):
                logger.info(" Direct analysis succeeded")
                return result
            else:
                logger.warning(f"⚠️ Direct analysis failed: {result}")
        except Exception as e:
            logger.warning(f"⚠️ Attempt 1 failed with exception: {e}")

        try:
            logger.info("🔄 Attempt 2: Simple analysis")
            result = await self._analyze_direct(cookbook_content, correlation_id, logger, session_id, "simple")
            if result and result.get("success") and not result.get("postprocess_error"):
                logger.info(" Simple analysis succeeded")
                return result
            else:
                logger.warning(f"⚠️ Simple analysis failed: {result}")
        except Exception as e:
            logger.warning(f"⚠️ Attempt 2 failed with exception: {e}")

        logger.warning("⚠️ LLM analysis failed - processor will handle intelligent fallback")
        return extract_and_validate_analysis("{}", correlation_id, cookbook_content)

    async def _analyze_direct(self, cookbook_content: str, correlation_id: str, logger: ChefAnalysisLogger, session_id: str, analysis_type: str) -> Optional[Dict[str, Any]]:
        """
        Direct analysis using correct LlamaStack API - NO attachments parameter
        """
        if analysis_type == "direct":
            prompt = f"""Analyze this Chef cookbook and return ONLY valid JSON.
<COOKBOOK>
{cookbook_content}
</COOKBOOK>
CRITICAL: Return ONLY the JSON object with your actual analysis values."""
        else:
            prompt = f"""Analyze this Chef cookbook:
{cookbook_content}
CRITICAL: Replace ALL instruction text with your actual analysis values."""

        try:
            messages = [UserMessage(role="user", content=prompt)]
            
            # FIXED: Use correct API without attachments parameter
            generator = self.client.agents.turn.create(
                agent_id=self.agent_id,
                session_id=session_id,
                messages=messages,
                stream=True,
            )
            
            # Process streaming response
            turn = None
            for chunk in generator:
                event = chunk.event
                event_type = event.payload.event_type
                if event_type == "turn_complete":
                    turn = event.payload.turn
                    break
            
            if not turn:
                logger.error(" No turn completed in response")
                return None
            
            # Log steps for debugging
            logger.info(f" Turn completed with {len(turn.steps)} steps")
            for i, step in enumerate(turn.steps):
                logger.info(f"📋 Step {i+1}: {step.step_type}")
            
            raw_response = turn.output_message.content
            logger.info(f"📥 Received {analysis_type} response: {len(raw_response)} chars")
            
            result = extract_and_validate_analysis(raw_response, correlation_id, cookbook_content)
            logger.info(f"🔍 Processor returned: success={result.get('success')}")
            return result
            
        except Exception as e:
            logger.error(f" {analysis_type.capitalize()} analysis failed: {e}")
            return None

    async def analyze_cookbook_stream(
        self,
        cookbook_data: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        correlation_id = correlation_id or create_correlation_id()
        cookbook_name = cookbook_data.get("name", "unknown")
        
        try:
            yield {
                "type": "progress",
                "status": "processing",
                "message": "🍳 Chef cookbook analysis started",
                "agent_info": {
                    "agent_id": self.agent_id,
                    "correlation_id": correlation_id
                }
            }

            result = await self.analyze_cookbook(cookbook_data, correlation_id)
            if isinstance(result, dict):
                result["cookbook_name"] = cookbook_name

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
        """
        Get current status of the agent
        """
        return {
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "client_base_url": self.client.base_url,
            "timeout": self.timeout,
            "status": "ready"
        }

    async def health_check(self) -> bool:
        """
        Perform a health check on the agent
        """
        try:
            # Simple health check by creating a minimal turn
            messages = [UserMessage(role="user", content="Health check")]
            generator = self.client.agents.turn.create(
                agent_id=self.agent_id,
                session_id=self.session_id,
                messages=messages,
                stream=True,
            )
            
            # Just check if we can create a turn without errors
            for chunk in generator:
                # Just need first chunk to verify connection works
                break
            
            self.logger.info(" Health check passed")
            return True
        except Exception as e:
            self.logger.error(f" Health check failed: {e}")
            return False