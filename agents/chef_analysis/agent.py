import time
from typing import Dict, Any, Optional, AsyncGenerator
import logging

from agents.agent import AgentManager
from config.config import ConfigLoader
from llama_stack_client import Agent, LlamaStackClient
from llama_stack_client.types import UserMessage

# Utility modules
from agents.chef_analysis.utils import create_correlation_id
from agents.chef_analysis.processor import extract_and_validate_analysis
from shared.exceptions import (
    LLMServiceError,
    TimeoutError,
    ConfigurationError,
    JSONParseError,
    CookbookAnalysisError
)
from shared.log_utils import create_chef_logger, ChefAnalysisLogger, step_printer

logger = logging.getLogger(__name__)

class ChefAnalysisAgent:
    def __init__(self, client: Any, model: str, instructions: str, timeout: int = 120):
        self.timeout = timeout
        self.client = client
        self.model = model
        self.instructions = instructions
        self.logger = create_chef_logger("init")
        self._initialize_agent()
        self.logger.info(f"Chef Analysis Agent initialized successfully | Model: {self.model}")

    def _initialize_agent(self):
        try:
            self.agent = Agent(
                client=self.client,
                model=self.model,
                instructions=self.instructions
            )
            self.logger.info("Chef Analysis Agent initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize agent: {e}")
            raise ConfigurationError(f"Agent initialization failed: {e}")

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

            analysis_result = await self._analyze_with_retries(
                cookbook_content, correlation_id, logger
            )

            total_time = time.time() - start_time
            logger.log_analysis_completion(analysis_result, total_time)

            # --- FIX: Attach actual cookbook_name always in the result ---
            if isinstance(analysis_result, dict):
                analysis_result["cookbook_name"] = cookbook_name
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

    async def _analyze_with_retries(self, cookbook_content: str, correlation_id: str, logger: ChefAnalysisLogger) -> Dict[str, Any]:
        # Attempt 1: Direct JSON request
        try:
            logger.info("🔄 Attempt 1: Direct JSON analysis")
            result = await self._analyze_like_classifier(cookbook_content, correlation_id, logger)
            if result and result.get("success") and not result.get("postprocess_error"):
                logger.info(" Direct analysis succeeded")
                return result
            else:
                logger.warning(f" Direct analysis failed: {result}")
        except Exception as e:
            logger.warning(f" Attempt 1 failed with exception: {e}")

        # Attempt 2: Simple prompt
        try:
            logger.info("🔄 Attempt 2: Simple analysis")
            result = await self._try_simple_analysis(cookbook_content, correlation_id, logger)
            if result and result.get("success") and not result.get("postprocess_error"):
                logger.info(" Simple analysis succeeded")
                return result
            else:
                logger.warning(f" Simple analysis failed: {result}")
        except Exception as e:
            logger.warning(f" Attempt 2 failed with exception: {e}")

        logger.warning("⚠️ LLM analysis failed - processor will handle intelligent fallback")
        return extract_and_validate_analysis("{}", correlation_id, cookbook_content)

    async def _analyze_like_classifier(self, cookbook_content: str, correlation_id: str, logger: ChefAnalysisLogger) -> Optional[Dict[str, Any]]:
        prompt = f"""Analyze this Chef cookbook and return ONLY valid JSON.
<COOKBOOK>
{cookbook_content}
</COOKBOOK>
CRITICAL: Return ONLY the JSON object with your actual analysis values."""
        try:
            session_id = self.agent.create_session(f"chef_analysis_{correlation_id}")
            logger.info(f" Created session: {session_id}")
            turn = self.agent.create_turn(
                session_id=session_id,
                messages=[UserMessage(role="user", content=prompt)],
                stream=False
            )
            step_printer(turn.steps)
            raw_response = turn.output_message.content
            logger.info(f" Received response: {len(raw_response)} chars")
            result = extract_and_validate_analysis(raw_response, correlation_id, cookbook_content)
            logger.info(f" Processor returned: success={result.get('success')}")
            return result
        except Exception as e:
            logger.error(f" ClassifierAgent-style analysis failed: {e}")
            return None

    async def _try_simple_analysis(self, cookbook_content: str, correlation_id: str, logger: ChefAnalysisLogger) -> Optional[Dict[str, Any]]:
        prompt = f"""Analyze this Chef cookbook:
{cookbook_content}
CRITICAL: Replace ALL instruction text with your actual analysis values."""
        try:
            session_id = self.agent.create_session(f"simple_{correlation_id}")
            turn = self.agent.create_turn(
                session_id=session_id,
                messages=[UserMessage(role="user", content=prompt)],
                stream=False
            )
            raw_response = turn.output_message.content
            logger.info(f"📥 Simple response: {len(raw_response)} chars")
            result = extract_and_validate_analysis(raw_response, correlation_id, cookbook_content)
            return result
        except Exception as e:
            logger.error(f" Simple analysis failed: {e}")
            return None

    async def analyze_cookbook_stream(
        self,
        cookbook_data: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Streaming analysis, yields events. 
        """
        correlation_id = correlation_id or create_correlation_id()
        cookbook_name = cookbook_data.get("name", "unknown")
        try:
            yield {
                "type": "progress",
                "status": "processing", 
                "message": "Chef cookbook analysis started"
            }

            result = await self.analyze_cookbook(cookbook_data, correlation_id)
            # --- FIX: Always attach cookbook_name in streaming result too ---
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

def create_chef_analysis_agent(config_loader: ConfigLoader) -> ChefAnalysisAgent:
    # Get config values
    base_url = config_loader.get_llamastack_base_url()
    model = config_loader.get_llamastack_model()
    instructions = None
    # Get instructions for this agent
    for agent in config_loader.get_agents_config():
        if agent["name"] == "chef_analysis":
            instructions = agent["instructions"]
    timeout = 120  # Use more robust value or config if needed

    if not base_url or not model or not instructions:
        raise ConfigurationError("Missing configuration for ChefAnalysisAgent")

    client = LlamaStackClient(base_url=base_url.rstrip('/'))
    return ChefAnalysisAgent(client=client, model=model, instructions=instructions, timeout=timeout)
