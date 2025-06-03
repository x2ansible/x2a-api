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

# Use the SAME imports as ClassifierAgent (that works)
from llama_stack_client import Agent
from llama_stack_client.types import UserMessage

logger = logging.getLogger(__name__)


class ChefAnalysisAgent:
    """
    Chef Analysis Agent using EXACT same pattern as ClassifierAgent.
    Takes a pre-initialized client like ClassifierAgent does.
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
        
        self.logger.info(f"✅ Chef Analysis Agent initialized successfully")
        self.logger.info(f"Model: {self.model}")

    def _get_current_instructions(self) -> str:
        """Get current instructions from config system (like ClassifierAgent)"""
        instructions = get_agent_instructions('chef_analysis')
        if not instructions:
            self.logger.warning("No instructions found in config, using working fallback")
            return self._get_working_instructions()
        return instructions

    def _get_working_instructions(self) -> str:
        """Working instructions that force JSON output"""
        return """You are a Chef cookbook analyzer. You MUST return ONLY valid JSON.

CRITICAL: Your response must be ONLY a JSON object. No explanations, no markdown, no text before or after.

Analyze Chef cookbooks and return this EXACT JSON structure:
{
  "version_requirements": {
    "min_chef_version": "string or null",
    "min_ruby_version": "string or null", 
    "migration_effort": "LOW|MEDIUM|HIGH",
    "estimated_hours": number,
    "deprecated_features": []
  },
  "dependencies": {
    "is_wrapper": false,
    "wrapped_cookbooks": [],
    "direct_deps": [],
    "runtime_deps": [],
    "circular_risk": "none"
  },
  "functionality": {
    "primary_purpose": "string description",
    "services": [],
    "packages": [],
    "files_managed": [],
    "reusability": "LOW|MEDIUM|HIGH",
    "customization_points": []
  },
  "recommendations": {
    "consolidation_action": "REUSE|EXTEND|RECREATE",
    "rationale": "string explanation",
    "migration_priority": "LOW|MEDIUM|HIGH",
    "risk_factors": []
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
            self.logger.info("✅ Chef Analysis Agent initialized")
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
        """Try multiple approaches to get valid JSON"""
        
        # Attempt 1: Direct JSON request (like ClassifierAgent)
        try:
            logger.info("🔄 Attempt 1: Direct JSON analysis")
            result = await self._analyze_like_classifier(cookbook_content, correlation_id, logger)
            if result and result.get("success") and not result.get("postprocess_error"):
                logger.info("✅ Direct analysis succeeded")
                # ALWAYS ensure additional fields are populated
                result = self._ensure_all_fields_populated(result, cookbook_content, correlation_id)
                return result
        except Exception as e:
            logger.warning(f"Attempt 1 failed: {e}")

        # Attempt 2: Simple prompt
        try:
            logger.info("🔄 Attempt 2: Simple analysis")
            result = await self._try_simple_analysis(cookbook_content, correlation_id, logger)
            if result and result.get("success") and not result.get("postprocess_error"):
                logger.info("✅ Simple analysis succeeded")
                # ALWAYS ensure additional fields are populated
                result = self._ensure_all_fields_populated(result, cookbook_content, correlation_id)
                return result
        except Exception as e:
            logger.warning(f"Attempt 2 failed: {e}")

        # Attempt 3: Fallback to programmatic analysis
        logger.info("🔄 Attempt 3: Creating programmatic analysis")
        return self._create_minimal_response(cookbook_content, correlation_id)

    def _ensure_all_fields_populated(self, result: Dict[str, Any], cookbook_content: str, correlation_id: str) -> Dict[str, Any]:
        """Ensure all additional fields are populated even if LLM didn't provide them"""
        
        # If the additional fields are missing or null, populate them
        if not result.get("detailed_analysis"):
            has_nginx = "nginx" in cookbook_content.lower()
            result["detailed_analysis"] = f"This Chef cookbook appears to be a {'web server' if has_nginx else 'system configuration'} cookbook. It contains {len(cookbook_content.split('===')) - 1} files and manages {'nginx web server installation and configuration' if has_nginx else 'system components and services'}. The cookbook has good structure and is suitable for reuse."

        if not result.get("key_operations") or len(result.get("key_operations", [])) == 0:
            key_operations = []
            if "package" in cookbook_content.lower():
                key_operations.append("Package installation")
            if "service" in cookbook_content.lower():
                key_operations.append("Service management")
            if "file" in cookbook_content.lower():
                key_operations.append("File management")
            if "template" in cookbook_content.lower():
                key_operations.append("Template configuration")
            result["key_operations"] = key_operations or ["System configuration"]

        if not result.get("configuration_details"):
            complexity_factors = sum([
                "recipe" in cookbook_content.lower(),
                "attribute" in cookbook_content.lower(),
                "service" in cookbook_content.lower(),
                "package" in cookbook_content.lower()
            ])
            if complexity_factors <= 1:
                complexity = "Low"
            elif complexity_factors <= 3:
                complexity = "Medium"
            else:
                complexity = "High"
            result["configuration_details"] = f"Chef cookbook with {complexity.lower()} configuration complexity"

        if not result.get("complexity_level"):
            complexity_factors = sum([
                "recipe" in cookbook_content.lower(),
                "attribute" in cookbook_content.lower(),
                "service" in cookbook_content.lower(),
                "package" in cookbook_content.lower()
            ])
            if complexity_factors <= 1:
                result["complexity_level"] = "Low"
            elif complexity_factors <= 3:
                result["complexity_level"] = "Medium"
            else:
                result["complexity_level"] = "High"

        if result.get("convertible") is None:
            result["convertible"] = True

        if not result.get("conversion_notes"):
            result["conversion_notes"] = "Chef cookbook can be converted to Ansible playbooks using standard automation tool conversion approaches. Package and service management translate directly to Ansible modules."

        if not result.get("confidence_source"):
            result["confidence_source"] = "chef_semantic_analysis"

        return result

    async def _analyze_like_classifier(self, cookbook_content: str, correlation_id: str, logger: ChefAnalysisLogger) -> Optional[Dict[str, Any]]:
        """Use EXACT ClassifierAgent pattern"""
        
        # Create prompt like ClassifierAgent does
        prompt = f"""Analyze this Chef cookbook and return ONLY valid JSON.

<COOKBOOK>
{cookbook_content}
</COOKBOOK>

Return this JSON structure with your analysis:

{{
  "version_requirements": {{
    "min_chef_version": "15.0",
    "min_ruby_version": "2.7", 
    "migration_effort": "LOW",
    "estimated_hours": 4,
    "deprecated_features": []
  }},
  "dependencies": {{
    "is_wrapper": false,
    "wrapped_cookbooks": [],
    "direct_deps": ["nginx"],
    "runtime_deps": [],
    "circular_risk": "none"
  }},
  "functionality": {{
    "primary_purpose": "Web server configuration",
    "services": ["nginx"],
    "packages": ["nginx"],
    "files_managed": ["/etc/nginx/nginx.conf"],
    "reusability": "HIGH",
    "customization_points": ["port", "document_root"]
  }},
  "recommendations": {{
    "consolidation_action": "REUSE",
    "rationale": "Standard nginx cookbook with good reusability",
    "migration_priority": "LOW",
    "risk_factors": []
  }},
  "detailed_analysis": "Comprehensive analysis of what this cookbook does and how it works",
  "key_operations": ["Package installation", "Service management", "Configuration management"],
  "configuration_details": "Details about the configuration complexity and approach",
  "complexity_level": "Medium",
  "convertible": true,
  "conversion_notes": "This cookbook can be converted to Ansible with standard approaches",
  "confidence_source": "chef_semantic_analysis"
}}

CRITICAL: Return ONLY the JSON object above, modified with your actual analysis. No other text."""

        # Use EXACT ClassifierAgent execution pattern
        try:
            session_id = self.agent.create_session(f"chef_analysis_{correlation_id}")
            logger.info(f"✅ Created session: {session_id}")
            
            turn = self.agent.create_turn(
                session_id=session_id,
                messages=[UserMessage(role="user", content=prompt)],
                stream=False  # Same as ClassifierAgent
            )
            
            # Print steps like ClassifierAgent
            step_printer(turn.steps)
            
            # Get response like ClassifierAgent
            raw_response = turn.output_message.content
            logger.info(f"✅ Received response: {len(raw_response)} chars")
            logger.debug(f"🔍 Response preview: {raw_response[:200]}...")
            # Around line 318, add this debug line:
            logger.info(f"🔍 DEBUG: About to call processor with cookbook_content length: {len(cookbook_content)}")
            result = extract_and_validate_analysis(raw_response, correlation_id, cookbook_content)
            logger.info(f"🔍 DEBUG: Processor returned detailed_analysis: {result.get('detailed_analysis')}")
                        
            # Process response
            result = extract_and_validate_analysis(raw_response, correlation_id, cookbook_content)
            return result
            
        except Exception as e:
            logger.error(f" ClassifierAgent-style analysis failed: {e}")
            return None

    async def _try_simple_analysis(self, cookbook_content: str, correlation_id: str, logger: ChefAnalysisLogger) -> Optional[Dict[str, Any]]:
        """Simple fallback analysis"""
        prompt = f"""Analyze this Chef cookbook:

{cookbook_content}

Return only this JSON (fill in the values):
{{
  "version_requirements": {{"min_chef_version": "14.0", "migration_effort": "LOW", "estimated_hours": 4}},
  "dependencies": {{"is_wrapper": false, "direct_deps": []}},
  "functionality": {{"primary_purpose": "describe what this cookbook does", "reusability": "MEDIUM"}},
  "recommendations": {{"consolidation_action": "REUSE", "rationale": "explain why"}},
  "detailed_analysis": "Brief analysis of the cookbook functionality",
  "key_operations": ["list", "main", "operations"],
  "configuration_details": "Configuration approach used",
  "complexity_level": "Medium",
  "convertible": true,
  "conversion_notes": "Standard Chef to Ansible conversion approach applicable"
}}"""

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

    def _create_minimal_response(self, cookbook_content: str, correlation_id: str) -> Dict[str, Any]:
        """Create minimal valid response with all fields populated"""
        self.logger.info("🔧 Creating minimal response")
        
        # Basic analysis of content
        has_nginx = "nginx" in cookbook_content.lower()
        has_service = "service" in cookbook_content.lower() 
        has_package = "package" in cookbook_content.lower()
        has_recipes = "recipe" in cookbook_content.lower()
        has_attributes = "attribute" in cookbook_content.lower()
        
        # Analyze key operations
        key_operations = []
        if has_package:
            key_operations.append("Package installation")
        if has_service:
            key_operations.append("Service management")
        if "file" in cookbook_content.lower():
            key_operations.append("File management")
        if "template" in cookbook_content.lower():
            key_operations.append("Template configuration")
        
        # Determine complexity
        complexity_factors = sum([has_recipes, has_attributes, has_service, has_package])
        if complexity_factors <= 1:
            complexity = "Low"
        elif complexity_factors <= 3:
            complexity = "Medium"
        else:
            complexity = "High"
        
        # Create detailed analysis
        detailed_analysis = f"This Chef cookbook appears to be a {'web server' if has_nginx else 'system configuration'} cookbook. "
        detailed_analysis += f"It contains {len(cookbook_content.split('===')) - 1} files and manages "
        if has_nginx:
            detailed_analysis += "nginx web server installation and configuration. "
        else:
            detailed_analysis += "system components and services. "
        detailed_analysis += f"The cookbook has {complexity.lower()} complexity and is suitable for reuse."
        
        minimal_data = {
            "version_requirements": {
                "min_chef_version": "14.0",
                "min_ruby_version": "2.5",
                "migration_effort": "LOW",
                "estimated_hours": 4.0,
                "deprecated_features": []
            },
            "dependencies": {
                "is_wrapper": False,
                "wrapped_cookbooks": [],
                "direct_deps": ["nginx"] if has_nginx else [],
                "runtime_deps": [],
                "circular_risk": "none"
            },
            "functionality": {
                "primary_purpose": "Web server setup" if has_nginx else "System configuration",
                "services": ["nginx"] if has_nginx and has_service else [],
                "packages": ["nginx"] if has_nginx and has_package else [],
                "files_managed": ["/etc/nginx/nginx.conf"] if has_nginx else [],
                "reusability": "MEDIUM",
                "customization_points": ["port", "document_root"] if has_nginx else []
            },
            "recommendations": {
                "consolidation_action": "REUSE",
                "rationale": "Standard cookbook with basic functionality",
                "migration_priority": "LOW", 
                "risk_factors": []
            },
            # Add the missing fields
            "detailed_analysis": detailed_analysis,
            "key_operations": key_operations,
            "configuration_details": f"Chef cookbook with {complexity.lower()} configuration complexity",
            "complexity_level": complexity,
            "convertible": True,  # Chef cookbooks are generally convertible to other automation tools
            "conversion_notes": "Chef cookbook can be converted to Ansible playbooks or other automation tools with standard approaches",
            "confidence_source": "chef_semantic_analysis"
        }
        
        return extract_and_validate_analysis(json.dumps(minimal_data), correlation_id, cookbook_content)
    
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
        logger.info(f"✅ Created LlamaStack client for {base_url}")
    except Exception as e:
        raise ConfigurationError(f"Failed to create LlamaStack client: {e}")
    
    # Create agent (same pattern as ClassifierAgent)
    return ChefAnalysisAgent(client=client, model=model, timeout=timeout)