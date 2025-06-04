import asyncio
import json
import time
from typing import Dict, Any, Optional, AsyncGenerator
import logging

from config.config_loader import ConfigLoader
from config.agent_config import get_agent_instructions
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

from llama_stack_client import Agent
from llama_stack_client.types import UserMessage

logger = logging.getLogger(__name__)


class ChefAnalysisAgent:
    """
    Chef Analysis Agent - Simplified to focus on LLM interaction only
    All intelligent defaults and analysis logic moved to processor
    """
    def __init__(self, client: Any, model: str, timeout: int = 120):
        """Initialize exactly like ClassifierAgent - with pre-initialized client"""
        self.timeout = timeout
        self.client = client  # Use passed client (like ClassifierAgent)
        self.model = model
        
        # Get instructions from config (like ClassifierAgent)
        self.instructions = self._get_current_instructions()
        
        self.logger = create_chef_logger("init")
        
        # Initialize agent with instructions (exactly like ClassifierAgent)
        self._initialize_agent()
        
        self.logger.info(f"Chef Analysis Agent initialized successfully")
        self.logger.info(f"Model: {self.model}")

    def _get_current_instructions(self) -> str:
        """Get current instructions from config system (like ClassifierAgent)"""
        instructions = get_agent_instructions('chef_analysis')
        if not instructions:
            self.logger.warning("No instructions found in config, using working fallback")
            return self._get_working_instructions()
        return instructions

    def _get_working_instructions(self) -> str:
        """Working instructions that force JSON output - NO hardcoded values"""
        return """You are a Chef cookbook analyzer. You MUST return ONLY valid JSON.

CRITICAL: Your response must be ONLY a JSON object. No explanations, no markdown, no text before or after.

Analyze Chef cookbooks and return this EXACT JSON structure:
{
  "version_requirements": {
    "min_chef_version": "analyze APIs used and determine minimum version required",
    "min_ruby_version": "analyze syntax patterns and determine minimum version required", 
    "migration_effort": "LOW|MEDIUM|HIGH based on complexity analysis",
    "estimated_hours": "estimate based on cookbook complexity (as number)",
    "deprecated_features": ["list deprecated features found"]
  },
  "dependencies": {
    "is_wrapper": "true/false based on include_recipe analysis",
    "wrapped_cookbooks": ["list cookbooks wrapped via include_recipe"],
    "direct_deps": ["dependencies from metadata.rb"],
    "runtime_deps": ["dependencies from recipe analysis"],
    "circular_risk": "none|low|medium|high"
  },
  "functionality": {
    "primary_purpose": "describe what this cookbook does",
    "services": ["services managed by this cookbook"],
    "packages": ["packages installed by this cookbook"],
    "files_managed": ["key files/directories managed"],
    "reusability": "LOW|MEDIUM|HIGH based on configurability",
    "customization_points": ["areas where cookbook can be customized"]
  },
  "recommendations": {
    "consolidation_action": "REUSE|EXTEND|RECREATE based on analysis",
    "rationale": "explain recommendation with specific reasoning",
    "migration_priority": "LOW|MEDIUM|HIGH|CRITICAL based on complexity",
    "risk_factors": ["specific migration risks identified"]
  }
}

RESPONSE FORMAT: Return ONLY the JSON object above with actual analysis values."""

    def _initialize_agent(self):
        """Initialize agent with Chef analysis instructions (exactly like ClassifierAgent)"""
        try:
            self.agent = Agent(
                client=self.client,
                model=self.model,
                instructions=self.instructions
            )
            self.logger.info("Chef Analysis Agent initialized")
        except Exception as e:
            self.logger.error(f" Failed to initialize agent: {e}")
            raise ConfigurationError(f"Agent initialization failed: {e}")

    async def analyze_cookbook(
        self,
        cookbook_data: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze Chef cookbook using ClassifierAgent pattern"""
        correlation_id = correlation_id or create_correlation_id()
        logger = create_chef_logger(correlation_id)
        start_time = time.time()

        cookbook_name = cookbook_data.get("name", "unknown")
        files = cookbook_data.get("files", {})

        logger.log_cookbook_analysis_start(cookbook_name, len(files))

        try:
            if not files:
                raise ValueError("Cookbook must contain at least one file")

            # Format cookbook content
            cookbook_content = self._format_cookbook_content(cookbook_name, files)
            logger.info(f"📄 Formatted cookbook: {len(cookbook_content)} chars")

            # Use EXACT ClassifierAgent pattern
            analysis_result = await self._analyze_with_retries(cookbook_content, correlation_id, logger)

            total_time = time.time() - start_time
            logger.log_analysis_completion(analysis_result, total_time)
            return analysis_result

        except Exception as e:
            total_time = time.time() - start_time
            logger.error(f" Analysis failed after {total_time:.3f}s: {str(e)}")
            raise CookbookAnalysisError(f"Analysis failed: {str(e)}")

    def _format_cookbook_content(self, cookbook_name: str, files: Dict[str, str]) -> str:
        """Format cookbook for analysis"""
        content_parts = [f"Cookbook: {cookbook_name}"]
        
        for filename, content in files.items():
            content_parts.append(f"\n=== {filename} ===")
            content_parts.append(content.strip())
        
        return "\n".join(content_parts)

    async def _analyze_with_retries(self, cookbook_content: str, correlation_id: str, logger: ChefAnalysisLogger) -> Dict[str, Any]:
        """Try multiple approaches to get valid JSON - Processor handles all defaults"""
        
        # Attempt 1: Direct JSON request (like ClassifierAgent)
        try:
            logger.info("🔄 Attempt 1: Direct JSON analysis")
            result = await self._analyze_like_classifier(cookbook_content, correlation_id, logger)
            if result and result.get("success") and not result.get("postprocess_error"):
                logger.info(" Direct analysis succeeded")
                return result
            else:
                logger.warning(f" Direct analysis failed: success={result.get('success') if result else None}, error={result.get('postprocess_error') if result else None}")
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
                logger.warning(f" Simple analysis failed: success={result.get('success') if result else None}, error={result.get('postprocess_error') if result else None}")
        except Exception as e:
            logger.warning(f" Attempt 2 failed with exception: {e}")

        # Attempt 3: Let processor handle complete fallback
        logger.warning("⚠️ LLM analysis failed - processor will handle intelligent fallback")
        # Pass empty response to processor - it will create intelligent defaults
        return extract_and_validate_analysis("{}", correlation_id, cookbook_content)

    async def _analyze_like_classifier(self, cookbook_content: str, correlation_id: str, logger: ChefAnalysisLogger) -> Optional[Dict[str, Any]]:
        """Use EXACT ClassifierAgent pattern - NO hardcoded example values"""
        
        # Create prompt without biasing example values
        prompt = f"""Analyze this Chef cookbook and return ONLY valid JSON.

<COOKBOOK>
{cookbook_content}
</COOKBOOK>

Analyze the cookbook content above and return this JSON structure with your actual analysis:

{{
  "version_requirements": {{
    "min_chef_version": "determine minimum Chef version required based on APIs and features used",
    "min_ruby_version": "determine minimum Ruby version based on syntax patterns", 
    "migration_effort": "LOW, MEDIUM, or HIGH based on complexity and deprecated features",
    "estimated_hours": "estimate hours based on cookbook size and complexity (as number)",
    "deprecated_features": ["list any deprecated Chef features found in the code"]
  }},
  "dependencies": {{
    "is_wrapper": "true if this cookbook wraps others via include_recipe, false otherwise",
    "wrapped_cookbooks": ["list cookbooks included via include_recipe calls"],
    "direct_deps": ["list dependencies from metadata.rb depends statements"],
    "runtime_deps": ["list runtime dependencies discovered from recipe analysis"],
    "circular_risk": "none, low, medium, or high based on dependency analysis"
  }},
  "functionality": {{
    "primary_purpose": "describe what this cookbook actually does based on analysis",
    "services": ["list services this cookbook manages based on service resources"],
    "packages": ["list packages this cookbook installs based on package resources"],
    "files_managed": ["list key files/directories managed based on file/template resources"],
    "reusability": "LOW, MEDIUM, or HIGH based on configurability and modularity",
    "customization_points": ["list key areas where this cookbook can be customized"]
  }},
  "recommendations": {{
    "consolidation_action": "REUSE, EXTEND, or RECREATE based on analysis",
    "rationale": "explain your recommendation with specific reasoning based on the cookbook",
    "migration_priority": "LOW, MEDIUM, HIGH, or CRITICAL based on complexity and risk",
    "risk_factors": ["list specific migration risks identified from analysis"]
  }},
  "detailed_analysis": "provide comprehensive analysis of cookbook functionality, structure, and characteristics",
  "key_operations": ["list main operations performed by this cookbook based on resources used"],
  "configuration_details": "describe the configuration approach, complexity, and patterns used",
  "complexity_level": "Low, Medium, or High based on actual analysis of cookbook structure",
  "convertible": true_or_false_based_on_convertibility_assessment,
  "conversion_notes": "specific notes about converting this cookbook to other automation tools",
  "confidence_source": "chef_semantic_analysis"
}}

CRITICAL: Return ONLY the JSON object with your actual analysis values. Replace all instruction text with real analysis results. No other text."""

        # Use EXACT ClassifierAgent execution pattern
        try:
            session_id = self.agent.create_session(f"chef_analysis_{correlation_id}")
            logger.info(f" Created session: {session_id}")
            
            turn = self.agent.create_turn(
                session_id=session_id,
                messages=[UserMessage(role="user", content=prompt)],
                stream=False  # Same as ClassifierAgent
            )
            
            # Print steps like ClassifierAgent
            step_printer(turn.steps)
            
            # Get response like ClassifierAgent
            raw_response = turn.output_message.content
            logger.info(f" Received response: {len(raw_response)} chars")
            logger.debug(f"🔍 Response preview: {raw_response[:200]}...")
            
            # Let processor handle ALL analysis and defaults
            result = extract_and_validate_analysis(raw_response, correlation_id, cookbook_content)
            logger.info(f"🔍 Processor returned: success={result.get('success')}")
            
            return result
            
        except Exception as e:
            logger.error(f" ClassifierAgent-style analysis failed: {e}")
            return None

    async def _try_simple_analysis(self, cookbook_content: str, correlation_id: str, logger: ChefAnalysisLogger) -> Optional[Dict[str, Any]]:
        """Simple fallback analysis - NO hardcoded example values"""
        prompt = f"""Analyze this Chef cookbook:

{cookbook_content}

Return only this JSON structure with your analysis (replace all instruction text with actual values):
{{
  "version_requirements": {{
    "min_chef_version": "analyze_cookbook_and_determine_minimum_chef_version", 
    "migration_effort": "analyze_complexity_and_determine_LOW_MEDIUM_or_HIGH", 
    "estimated_hours": "estimate_based_on_cookbook_complexity_as_number"
  }},
  "dependencies": {{
    "is_wrapper": "analyze_for_include_recipe_patterns_true_or_false", 
    "direct_deps": ["analyze_metadata_dependencies"]
  }},
  "functionality": {{
    "primary_purpose": "analyze_and_describe_what_this_cookbook_does", 
    "reusability": "analyze_and_rate_LOW_MEDIUM_or_HIGH"
  }},
  "recommendations": {{
    "consolidation_action": "analyze_and_recommend_REUSE_EXTEND_or_RECREATE", 
    "rationale": "provide_specific_reasoning_based_on_analysis"
  }},
  "detailed_analysis": "analyze_cookbook_and_provide_comprehensive_description_of_functionality",
  "key_operations": ["analyze_and_list_main_operations_performed"],
  "configuration_details": "analyze_configuration_approach_and_complexity_used",
  "complexity_level": "analyze_and_determine_Low_Medium_or_High",
  "convertible": true,
  "conversion_notes": "analyze_convertibility_and_provide_specific_conversion_notes"
}}

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
            
            # Let processor handle ALL analysis and defaults
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
        """Stream analysis"""
        correlation_id = correlation_id or create_correlation_id()

        try:
            yield {
                "type": "progress",
                "status": "processing", 
                "message": "Chef cookbook analysis started"
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


def create_chef_analysis_agent(config_loader: ConfigLoader) -> ChefAnalysisAgent:
    """
    Factory function - uses SAME pattern as working ClassifierAgent
    """
    from llama_stack_client import LlamaStackClient
    
    # Get configuration
    base_url = config_loader.get_llamastack_base_url()
    model = config_loader.get_llamastack_model()
    timeout = config_loader.get_value("agents", "chef_analysis", "timeout", default=120)
    
    if not base_url:
        raise ConfigurationError("LlamaStack base_url not configured")
    if not model:
        raise ConfigurationError("LlamaStack model not configured")
    
    # Create client (same as ClassifierAgent expects)
    try:
        client = LlamaStackClient(base_url=base_url.rstrip('/'))
        logger.info(f" Created LlamaStack client for {base_url}")
    except Exception as e:
        raise ConfigurationError(f"Failed to create LlamaStack client: {e}")
    
    # Create agent (same pattern as ClassifierAgent)
    return ChefAnalysisAgent(client=client, model=model, timeout=timeout)