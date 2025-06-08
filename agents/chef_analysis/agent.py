# agents/chef_analysis/agent.py
"""
Production-grade ChefAnalysisAgent with prompt chaining support.
Maintains backward compatibility while adding advanced prompt chaining capabilities.
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
    Supports prompt chaining (multi-step) and standard (single-prompt) analysis.
    """

    def __init__(
        self, 
        client: LlamaStackClient, 
        agent_id: str, 
        session_id: str, 
        timeout: int = 120, 
        enable_prompt_chaining: bool = True
    ):
        self.client = client
        self.agent_id = agent_id
        self.session_id = session_id
        self.timeout = timeout
        self.enable_prompt_chaining = enable_prompt_chaining
        self.logger = create_chef_logger("init")

        method = "prompt chaining" if enable_prompt_chaining else "standard"
        self.logger.info(f"🍳 ChefAnalysisAgent initialized with {method} - agent_id: {agent_id}, session_id: {session_id}")

    def create_new_session(self, correlation_id: str) -> str:
        """Create a new agent session for this specific analysis."""
        try:
            session_name = f"chef-{'chaining' if self.enable_prompt_chaining else 'standard'}-{correlation_id}-{uuid.uuid4()}"
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
        correlation_id: Optional[str] = None,
        method: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main analysis method with automatic method selection (prompt chaining or standard).
        """
        correlation_id = correlation_id or create_correlation_id()
        logger = create_chef_logger(correlation_id)
        start_time = time.time()

        cookbook_name = cookbook_data.get("name", "unknown")
        files = cookbook_data.get("files", {})

        use_chaining = self._should_use_chaining(method, files)
        method_name = "prompt_chaining" if use_chaining else "standard"
        logger.log_cookbook_analysis_start(cookbook_name, len(files))
        logger.info(f"🔗 Using analysis method: {method_name}")

        try:
            if not files:
                raise ValueError("Cookbook must contain at least one file")

            cookbook_content = self._format_cookbook_content(cookbook_name, files)
            logger.info(f"📄 Formatted cookbook: {len(cookbook_content)} chars")

            # Create dedicated session for this analysis
            analysis_session_id = self.create_new_session(correlation_id)

            # Execute analysis using selected method
            if use_chaining:
                analysis_result = await self._analyze_with_prompt_chaining(
                    cookbook_content, cookbook_name, correlation_id, logger, analysis_session_id
                )
            else:
                analysis_result = await self._analyze_with_standard_method(
                    cookbook_content, correlation_id, logger, analysis_session_id
                )

            total_time = time.time() - start_time
            logger.log_analysis_completion(analysis_result, total_time)

            if isinstance(analysis_result, dict):
                analysis_result["cookbook_name"] = cookbook_name
                analysis_result["analysis_method"] = method_name
                analysis_result["session_info"] = {
                    "agent_id": self.agent_id,
                    "session_id": analysis_session_id,
                    "correlation_id": correlation_id,
                    "method_used": method_name
                }
            return analysis_result

        except Exception as e:
            total_time = time.time() - start_time
            logger.error(f"Analysis failed after {total_time:.3f}s: {str(e)}")
            raise CookbookAnalysisError(f"Analysis failed: {str(e)}")

    def _should_use_chaining(self, method: Optional[str], files: Dict[str, str]) -> bool:
        """
        Determine whether to use prompt chaining based on method preference and complexity.
        """
        if method == "standard":
            return False
        elif method == "chaining":
            return True
        elif method is None:
            # Use chaining by default for multi-file or complex cookbooks
            complexity_indicators = [
                len(files) > 2,
                any("attributes" in filename for filename in files.keys()),
                any("recipes" in filename for filename in files.keys()),
                any(len(content) > 500 for content in files.values())
            ]
            return any(complexity_indicators) or self.enable_prompt_chaining
        else:
            return self.enable_prompt_chaining

    async def _analyze_with_prompt_chaining(
        self, 
        cookbook_content: str, 
        cookbook_name: str,
        correlation_id: str, 
        logger: ChefAnalysisLogger, 
        session_id: str
    ) -> Dict[str, Any]:
        """
        Execute prompt chaining analysis (multi-step).
        """
        try:
            logger.info("🔗 Starting prompt chaining analysis")
            # Step 1: Structure Analysis
            logger.info("🔍 Step 1: Analyzing cookbook structure")
            structure_result = await self._step1_structure_analysis(
                cookbook_content, session_id, logger
            )
            # Step 2: Version Requirements Analysis
            logger.info("📋 Step 2: Analyzing version requirements")
            version_result = await self._step2_version_analysis(
                cookbook_content, structure_result, session_id, logger
            )
            # Step 3: Dependency Analysis
            logger.info("🔗 Step 3: Analyzing dependencies")
            dependency_result = await self._step3_dependency_analysis(
                cookbook_content, structure_result, version_result, session_id, logger
            )
            # Step 4: Functionality Analysis
            logger.info("⚙️ Step 4: Analyzing functionality")
            functionality_result = await self._step4_functionality_analysis(
                cookbook_content, structure_result, version_result, dependency_result, session_id, logger
            )
            # Step 5: Final Recommendations
            logger.info("💡 Step 5: Generating recommendations")
            recommendations_result = await self._step5_recommendations(
                structure_result, version_result, dependency_result, functionality_result, session_id, logger
            )
            # Combine all results
            final_result = self._combine_chain_results(
                structure_result, version_result, dependency_result,
                functionality_result, recommendations_result, correlation_id
            )
            logger.info("Prompt chaining analysis completed successfully")
            return final_result

        except Exception as e:
            logger.error(f"Prompt chaining failed: {e}")
            logger.warning("⚠️ Falling back to standard analysis")
            return await self._analyze_with_standard_method(
                cookbook_content, correlation_id, logger, session_id
            )

    async def _analyze_with_standard_method(
        self, 
        cookbook_content: str, 
        correlation_id: str, 
        logger: ChefAnalysisLogger, 
        session_id: str
    ) -> Dict[str, Any]:
        """
        Execute standard single-step analysis (backward compatibility).
        """
        logger.info("🔄 Using standard analysis method")
        try:
            result = await self._analyze_with_retries(
                cookbook_content, correlation_id, logger, session_id
            )
            result["analysis_method"] = "standard"
            return result
        except Exception as e:
            logger.error(f"Standard analysis failed: {e}")
            return extract_and_validate_analysis("{}", correlation_id, cookbook_content)

    # ---- Prompt Chaining Steps ----

    async def _step1_structure_analysis(self, cookbook_content: str, session_id: str, logger: ChefAnalysisLogger) -> Dict[str, Any]:
        """Step 1: Analyze cookbook structure and basic metadata."""
        prompt = f"""Analyze this Chef cookbook's structure and metadata. Focus ONLY on structure analysis.

COOKBOOK CONTENT:
{cookbook_content}

ANALYSIS FOCUS:
1. What type of cookbook is this? (wrapper, library, application, custom)
2. What files are present and their purposes?
3. Basic metadata extraction (name, version, description)
4. Is this a simple or complex cookbook?

Return ONLY valid JSON with this structure:
{{
    "cookbook_type": "wrapper|library|application|custom",
    "complexity": "simple|moderate|complex",
    "files_present": ["list of filenames"],
    "metadata": {{
        "name": "cookbook name",
        "version": "version if found",
        "description": "description if found"
    }},
    "primary_files": ["key files like metadata.rb, default.rb"]
}}

Return only the JSON, nothing else."""
        return await self._execute_chain_step(prompt, session_id, logger, "structure")

    async def _step2_version_analysis(self, cookbook_content: str, structure_result: Dict, session_id: str, logger: ChefAnalysisLogger) -> Dict[str, Any]:
        """Step 2: Analyze version requirements based on structure context."""
        cookbook_type = structure_result.get("cookbook_type", "unknown")
        complexity = structure_result.get("complexity", "unknown")
        prompt = f"""Based on the structure analysis, this is a {cookbook_type} cookbook with {complexity} complexity.

COOKBOOK CONTENT:
{cookbook_content}

STRUCTURE CONTEXT:
{json.dumps(structure_result, indent=2)}

ANALYSIS FOCUS - Version Requirements:
1. Scan for Chef API patterns that indicate minimum Chef version
2. Look for Ruby syntax that requires specific Ruby versions
3. Identify any deprecated features or patterns
4. Estimate migration effort based on version gaps

Return ONLY valid JSON:
{{
    "min_chef_version": "version or null",
    "min_ruby_version": "version or null",
    "migration_effort": "LOW|MEDIUM|HIGH",
    "estimated_hours": number_or_null,
    "deprecated_features": ["list of deprecated features found"],
    "version_indicators": ["specific patterns that determined versions"]
}}

Return only the JSON, nothing else."""
        return await self._execute_chain_step(prompt, session_id, logger, "version")

    async def _step3_dependency_analysis(self, cookbook_content: str, structure_result: Dict, version_result: Dict, session_id: str, logger: ChefAnalysisLogger) -> Dict[str, Any]:
        """Step 3: Analyze dependencies with full context."""
        cookbook_type = structure_result.get("cookbook_type", "unknown")
        migration_effort = version_result.get("migration_effort", "unknown")
        prompt = f"""This {cookbook_type} cookbook has {migration_effort} migration effort based on version requirements.

COOKBOOK CONTENT:
{cookbook_content}

PREVIOUS ANALYSIS:
Structure: {json.dumps(structure_result, indent=2)}
Versions: {json.dumps(version_result, indent=2)}

ANALYSIS FOCUS - Dependencies:
1. Parse metadata.rb dependencies (depends directive)
2. Find include_recipe calls in recipes
3. Determine if this is a wrapper cookbook (high ratio of include_recipe vs custom code)
4. Assess circular dependency risks
5. Map runtime dependencies vs declared dependencies

Return ONLY valid JSON:
{{
    "is_wrapper": true_or_false,
    "wrapped_cookbooks": ["cookbooks this wraps via include_recipe"],
    "direct_deps": ["dependencies from metadata.rb"],
    "runtime_deps": ["cookbooks from include_recipe calls"],
    "circular_risk": "none|low|medium|high",
    "dependency_complexity": "simple|moderate|complex"
}}

Return only the JSON, nothing else."""
        return await self._execute_chain_step(prompt, session_id, logger, "dependency")

    async def _step4_functionality_analysis(self, cookbook_content: str, structure_result: Dict, version_result: Dict, dependency_result: Dict, session_id: str, logger: ChefAnalysisLogger) -> Dict[str, Any]:
        """Step 4: Analyze functionality with accumulated context."""
        cookbook_type = structure_result.get("cookbook_type", "unknown")
        is_wrapper = dependency_result.get("is_wrapper", False)
        prompt = f"""This {cookbook_type} cookbook {'is a wrapper' if is_wrapper else 'contains custom logic'}.

COOKBOOK CONTENT:
{cookbook_content}

ACCUMULATED CONTEXT:
Structure: {json.dumps(structure_result, indent=2)}
Versions: {json.dumps(version_result, indent=2)}
Dependencies: {json.dumps(dependency_result, indent=2)}

ANALYSIS FOCUS - Functionality:
1. What does this cookbook actually do? (primary purpose)
2. What services does it manage?
3. What packages does it install?
4. What files/directories does it manage?
5. How reusable and configurable is it?
6. What are the key customization points?

Return ONLY valid JSON:
{{
    "primary_purpose": "brief description of what cookbook does",
    "services": ["list of services managed"],
    "packages": ["list of packages installed"],
    "files_managed": ["key files/directories managed"],
    "reusability": "LOW|MEDIUM|HIGH",
    "customization_points": ["key areas for customization"],
    "functional_complexity": "simple|moderate|complex"
}}

Return only the JSON, nothing else."""
        return await self._execute_chain_step(prompt, session_id, logger, "functionality")

    async def _step5_recommendations(self, structure_result: Dict, version_result: Dict, dependency_result: Dict, functionality_result: Dict, session_id: str, logger: ChefAnalysisLogger) -> Dict[str, Any]:
        """Step 5: Generate strategic recommendations based on complete analysis."""
        prompt = f"""Based on the complete analysis of this Chef cookbook, provide strategic recommendations.

COMPLETE ANALYSIS CONTEXT:
Structure Analysis: {json.dumps(structure_result, indent=2)}
Version Analysis: {json.dumps(version_result, indent=2)}
Dependency Analysis: {json.dumps(dependency_result, indent=2)}
Functionality Analysis: {json.dumps(functionality_result, indent=2)}

ANALYSIS FOCUS - Strategic Recommendations:
1. Should this cookbook be REUSED, EXTENDED, or RECREATED?
2. What is the rationale for this recommendation?
3. What is the migration priority (LOW|MEDIUM|HIGH|CRITICAL)?
4. What are the key risk factors to consider?
5. What specific migration steps should be taken?

Return ONLY valid JSON:
{{
    "consolidation_action": "REUSE|EXTEND|RECREATE",
    "rationale": "detailed explanation with specific reasoning based on analysis",
    "migration_priority": "LOW|MEDIUM|HIGH|CRITICAL",
    "risk_factors": ["specific risks to consider during migration"],
    "migration_steps": ["recommended steps for migration"],
    "confidence_level": "LOW|MEDIUM|HIGH"
}}

Return only the JSON, nothing else."""
        return await self._execute_chain_step(prompt, session_id, logger, "recommendations")

    async def _execute_chain_step(self, prompt: str, session_id: str, logger: ChefAnalysisLogger, step_name: str) -> Dict[str, Any]:
        """Execute a single step in the prompt chain using the same pattern as ContextAgent."""
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
                if event.payload.event_type == "turn_complete":
                    turn = event.payload.turn
                    break
            if not turn:
                raise Exception(f"No response received for {step_name} step")
            response_content = turn.output_message.content
            logger.info(f"📥 {step_name.capitalize()} step response: {len(response_content)} chars")
            try:
                result = json.loads(response_content.strip())
                logger.info(f"{step_name.capitalize()} step JSON parsed successfully")
                return result
            except json.JSONDecodeError as e:
                logger.warning(f"⚠️ {step_name.capitalize()} step JSON parse failed: {e}")
                return self._extract_json_from_response(response_content, step_name)
        except Exception as e:
            logger.error(f"{step_name.capitalize()} step execution failed: {e}")
            return self._create_step_fallback(step_name)

    def _extract_json_from_response(self, response: str, step_name: str) -> Dict[str, Any]:
        """Extract JSON from potentially malformed response."""
        try:
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                return self._create_step_fallback(step_name)
        except:
            return self._create_step_fallback(step_name)

    def _create_step_fallback(self, step_name: str) -> Dict[str, Any]:
        """Create fallback result for failed step."""
        fallbacks = {
            "structure": {"cookbook_type": "unknown", "complexity": "unknown", "files_present": [], "metadata": {}, "primary_files": []},
            "version": {"min_chef_version": None, "min_ruby_version": None, "migration_effort": "UNKNOWN", "estimated_hours": None, "deprecated_features": [], "version_indicators": []},
            "dependency": {"is_wrapper": None, "wrapped_cookbooks": [], "direct_deps": [], "runtime_deps": [], "circular_risk": "unknown", "dependency_complexity": "unknown"},
            "functionality": {"primary_purpose": "Analysis failed", "services": [], "packages": [], "files_managed": [], "reusability": "UNKNOWN", "customization_points": [], "functional_complexity": "unknown"},
            "recommendations": {"consolidation_action": "REVIEW_MANUALLY", "rationale": "Automated analysis failed - requires manual review", "migration_priority": "MEDIUM", "risk_factors": ["Analysis incomplete"], "migration_steps": ["Manual analysis required"], "confidence_level": "LOW"}
        }
        return fallbacks.get(step_name, {})

    def _combine_chain_results(self, structure_result: Dict, version_result: Dict, dependency_result: Dict, functionality_result: Dict, recommendations_result: Dict, correlation_id: str) -> Dict[str, Any]:
        """Combine all chain step results into final analysis."""
        return {
            "success": True,
            "analysis_method": "prompt_chaining",
            "version_requirements": {
                "min_chef_version": version_result.get("min_chef_version"),
                "min_ruby_version": version_result.get("min_ruby_version"),
                "migration_effort": version_result.get("migration_effort"),
                "estimated_hours": version_result.get("estimated_hours"),
                "deprecated_features": version_result.get("deprecated_features", [])
            },
            "dependencies": {
                "is_wrapper": dependency_result.get("is_wrapper"),
                "wrapped_cookbooks": dependency_result.get("wrapped_cookbooks", []),
                "direct_deps": dependency_result.get("direct_deps", []),
                "runtime_deps": dependency_result.get("runtime_deps", []),
                "circular_risk": dependency_result.get("circular_risk")
            },
            "functionality": {
                "primary_purpose": functionality_result.get("primary_purpose"),
                "services": functionality_result.get("services", []),
                "packages": functionality_result.get("packages", []),
                "files_managed": functionality_result.get("files_managed", []),
                "reusability": functionality_result.get("reusability"),
                "customization_points": functionality_result.get("customization_points", [])
            },
            "recommendations": {
                "consolidation_action": recommendations_result.get("consolidation_action"),
                "rationale": recommendations_result.get("rationale"),
                "migration_priority": recommendations_result.get("migration_priority"),
                "risk_factors": recommendations_result.get("risk_factors", [])
            },
            "chain_details": {
                "structure_analysis": structure_result,
                "version_analysis": version_result,
                "dependency_analysis": dependency_result,
                "functionality_analysis": functionality_result,
                "recommendations_analysis": recommendations_result
            },
            "metadata": {
                "analyzed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "correlation_id": correlation_id,
                "agent_version": "prompt_chaining_v1"
            }
        }

    async def _analyze_with_retries(self, cookbook_content: str, correlation_id: str, logger: ChefAnalysisLogger, session_id: str) -> Dict[str, Any]:
        """Legacy method for backward compatibility (single prompt)."""
        try:
            logger.info("🔄 Attempt 1: Standard analysis")
            result = await self._analyze_direct(cookbook_content, correlation_id, logger, session_id, "standard")
            if result and result.get("success") and not result.get("postprocess_error"):
                logger.info("Standard analysis succeeded")
                return result
            else:
                logger.warning(f"⚠️ Standard analysis failed: {result}")
        except Exception as e:
            logger.warning(f"⚠️ Standard analysis failed with exception: {e}")
        logger.warning("⚠️ LLM analysis failed - processor will handle intelligent fallback")
        return extract_and_validate_analysis("{}", correlation_id, cookbook_content)

    async def _analyze_direct(self, cookbook_content: str, correlation_id: str, logger: ChefAnalysisLogger, session_id: str, analysis_type: str) -> Optional[Dict[str, Any]]:
        """Direct analysis using correct LlamaStack API (single prompt)."""
        prompt = f"""Analyze this Chef cookbook and return ONLY valid JSON.
<COOKBOOK>
{cookbook_content}
</COOKBOOK>
CRITICAL: Return ONLY the JSON object with your actual analysis values."""
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
            logger.info(f"📥 Received {analysis_type} response: {len(raw_response)} chars")
            result = extract_and_validate_analysis(raw_response, correlation_id, cookbook_content)
            logger.info(f"🔍 Processor returned: success={result.get('success')}")
            return result
        except Exception as e:
            logger.error(f"{analysis_type.capitalize()} analysis failed: {e}")
            return None

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
        correlation_id: Optional[str] = None,
        method: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Streaming version with method selection and progress reporting.
        """
        correlation_id = correlation_id or create_correlation_id()
        cookbook_name = cookbook_data.get("name", "unknown")
        files = cookbook_data.get("files", {})
        use_chaining = self._should_use_chaining(method, files)
        method_name = "prompt_chaining" if use_chaining else "standard"
        try:
            yield {
                "type": "progress",
                "status": "starting",
                "message": f"🍳 Chef cookbook analysis started using {method_name}",
                "method": method_name,
                "correlation_id": correlation_id
            }
            if use_chaining:
                steps = ["structure", "version", "dependency", "functionality", "recommendations"]
                for i, step in enumerate(steps, 1):
                    yield {
                        "type": "progress",
                        "status": "processing",
                        "message": f"🔍 Step {i}/5: Analyzing {step}",
                        "step": step,
                        "progress": i/5,
                        "method": method_name,
                        "correlation_id": correlation_id
                    }
                    import asyncio
                    await asyncio.sleep(0.1)
            result = await self.analyze_cookbook(cookbook_data, correlation_id, method)
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
            "prompt_chaining_enabled": self.enable_prompt_chaining,
            "approach": "hybrid_with_prompt_chaining" if self.enable_prompt_chaining else "standard",
            "methods_available": ["standard", "prompt_chaining"] if self.enable_prompt_chaining else ["standard"]
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
