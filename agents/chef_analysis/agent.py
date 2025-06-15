"""
Enhanced ChefAnalysisAgent with Tree-sitter Integration
Logs all files received before analysis for full observability.
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

from shared.tree_sitter_analyzer import TreeSitterAnalyzer

logger = logging.getLogger(__name__)

class ChefAnalysisAgent:
    """
    Enhanced ChefAnalysisAgent with Tree-sitter integration and input logging.
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

        try:
            self.tree_sitter = TreeSitterAnalyzer()
            self.tree_sitter_enabled = self.tree_sitter.is_enabled()
            if self.tree_sitter_enabled:
                self.logger.info("🌳 Tree-sitter integration enabled - providing verified structural facts")
            else:
                self.logger.warning("⚠️ Tree-sitter disabled - using LLM-only analysis")
        except Exception as e:
            self.tree_sitter = None
            self.tree_sitter_enabled = False
            self.logger.warning(f"⚠️ Tree-sitter initialization failed: {e}")
            self.logger.info("📝 Continuing with standard LLM-only analysis")

        self.logger.info(f"🍳 ChefAnalysisAgent initialized - agent_id: {agent_id}, session_id: {session_id}")

    def create_new_session(self, correlation_id: str) -> str:
        try:
            session_name = f"chef-analysis-{correlation_id}-{uuid.uuid4()}"
            response = self.client.agents.session.create(
                agent_id=self.agent_id,
                session_name=session_name,
            )
            session_id = response.session_id
            self.logger.info(f"📱 Created session: {session_id} for correlation: {correlation_id}")
            return session_id
        except Exception as e:
            self.logger.error(f" Failed to create session: {e}")
            self.logger.info(f"↩️ Falling back to default session: {self.session_id}")
            return self.session_id

    async def analyze_cookbook(
        self,
        cookbook_data: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        correlation_id = correlation_id or create_correlation_id()
        step_logger = create_chef_logger(correlation_id)
        start_time = time.time()

        cookbook_name = cookbook_data.get("name", "unknown")
        files = cookbook_data.get("files", {})

        # --- LOG ALL FILES RECEIVED ---
        step_logger.info(f"📂 Files received for analysis ({len(files)}): {list(files.keys())}")
        for fname, content in files.items():
            preview = content[:120].replace("\n", " ") + ("..." if len(content) > 120 else "")
            step_logger.info(f"  └── {fname} ({len(content)} chars): {preview}")

        step_logger.log_cookbook_analysis_start(cookbook_name, len(files))
        step_logger.info(f"🔄 Starting {'Tree-sitter + LLM' if self.tree_sitter_enabled else 'LLM-only'} analysis")

        try:
            if not files:
                raise ValueError("Cookbook must contain at least one file")

            analysis_session_id = self.create_new_session(correlation_id)

            if self.tree_sitter_enabled:
                step_logger.info("🌳 STEP 2: Extracting verified structural facts with Tree-sitter")
                tree_sitter_facts = self._extract_verified_facts(files, step_logger, correlation_id)
                step_logger.info(" Tree-sitter analysis completed - facts verified")
            else:
                step_logger.info("⚠️ STEP 2: Tree-sitter disabled - skipping structural analysis")
                tree_sitter_facts = self._create_empty_facts_structure()

            step_logger.info("🧠 STEP 3: LlamaStack agent intelligent analysis")
            cookbook_content = self._format_cookbook_content(cookbook_name, files)
            
            llm_analysis = await self._analyze_with_enhanced_prompt(
                cookbook_content, tree_sitter_facts, correlation_id, step_logger, analysis_session_id
            )

            step_logger.info("🔄 STEP 4: Merging verified facts with LLM analysis")
            final_result = self._merge_analysis_results(
                tree_sitter_facts, llm_analysis, cookbook_name, correlation_id, step_logger
            )

            total_time = time.time() - start_time
            step_logger.log_analysis_completion(final_result, total_time)

            final_result["session_info"] = {
                "agent_id": self.agent_id,
                "session_id": analysis_session_id,
                "correlation_id": correlation_id,
                "method_used": "tree_sitter_llm" if self.tree_sitter_enabled else "llm_only",
                "tree_sitter_enabled": self.tree_sitter_enabled,
                "analysis_time_seconds": round(total_time, 3)
            }
            
            step_logger.info(f" Analysis completed successfully in {total_time:.3f}s")
            return final_result

        except Exception as e:
            total_time = time.time() - start_time
            step_logger.error(f" Analysis failed after {total_time:.3f}s: {str(e)}")
            step_logger.warning("🔄 Attempting fallback to standard LLM-only analysis")
            try:
                return await self._fallback_to_standard_analysis(cookbook_data, correlation_id)
            except Exception as fallback_error:
                step_logger.error(f" Fallback analysis also failed: {fallback_error}")
                raise CookbookAnalysisError(f"Analysis failed: {str(e)}")

    def _extract_verified_facts(
        self, 
        files: Dict[str, str], 
        step_logger: ChefAnalysisLogger, 
        correlation_id: str
    ) -> Dict[str, Any]:
        step_logger.info(f"[{correlation_id}] 🌳 Tree-sitter analyzing {len(files)} cookbook files")
        try:
            chef_facts = self.tree_sitter.extract_chef_facts(files)
            total_resources = sum(len(resources) for resources in chef_facts['resources'].values())
            valid_files = sum(1 for v in chef_facts['syntax_validation'].values() if v.get('valid', False))
            total_files = len(chef_facts['syntax_validation'])
            chef_facts['summary'] = {
                'total_files': total_files,
                'valid_files': valid_files,
                'syntax_success_rate': round((valid_files / total_files) * 100, 1) if total_files > 0 else 0,
                'total_resources': total_resources,
                'has_metadata': bool(chef_facts['metadata']),
                'is_wrapper': len(chef_facts['dependencies']['include_recipes']) > 0,
                'complexity_score': self._calculate_complexity_score(chef_facts)
            }
            step_logger.info(f"[{correlation_id}]  Tree-sitter extraction complete:")
            step_logger.info(f"[{correlation_id}]   📦 {len(chef_facts['resources']['packages'])} packages")
            step_logger.info(f"[{correlation_id}]   🔧 {len(chef_facts['resources']['services'])} services")
            step_logger.info(f"[{correlation_id}]   📁 {len(chef_facts['resources']['files'])} files")
            step_logger.info(f"[{correlation_id}]   📋 {len(chef_facts['resources']['templates'])} templates")
            step_logger.info(f"[{correlation_id}]   🔗 {len(chef_facts['dependencies']['include_recipes'])} recipe deps")
            step_logger.info(f"[{correlation_id}]   📊 Wrapper cookbook: {chef_facts['summary']['is_wrapper']}")
            step_logger.info(f"[{correlation_id}]   🎯 Complexity score: {chef_facts['summary']['complexity_score']}")
            return chef_facts
        except Exception as e:
            step_logger.warning(f"[{correlation_id}] ⚠️ Tree-sitter extraction failed: {e}")
            step_logger.info(f"[{correlation_id}] 🔄 Returning empty facts structure for fallback")
            return self._create_empty_facts_structure()

    def _calculate_complexity_score(self, chef_facts: Dict[str, Any]) -> int:
        score = 0
        score += len(chef_facts['resources']['packages']) * 1
        score += len(chef_facts['resources']['services']) * 2
        score += len(chef_facts['resources']['files']) * 1
        score += len(chef_facts['resources']['templates']) * 2
        score += len(chef_facts['resources']['directories']) * 1
        cookbook_deps = chef_facts['dependencies'].get('cookbook_deps', [])
        include_recipes = chef_facts['dependencies'].get('include_recipes', [])
        score += len(cookbook_deps) * 3
        score += len(include_recipes) * 2
        total_files = len(chef_facts.get('syntax_validation', {}))
        score += total_files * 1
        return score

    def _create_empty_facts_structure(self) -> Dict[str, Any]:
        return {
            'metadata': {},
            'resources': {
                'packages': [],
                'services': [],
                'files': [],
                'templates': [],
                'directories': []
            },
            'dependencies': {
                'cookbook_deps': [],
                'include_recipes': []
            },
            'syntax_validation': {},
            'file_analysis': {},
            'summary': {
                'total_files': 0,
                'valid_files': 0,
                'syntax_success_rate': 0,
                'total_resources': 0,
                'has_metadata': False,
                'is_wrapper': False,
                'complexity_score': 0
            },
            'tree_sitter_enabled': False
        }

    async def _analyze_with_enhanced_prompt(
        self, 
        cookbook_content: str,
        tree_sitter_facts: Dict[str, Any],
        correlation_id: str, 
        step_logger: ChefAnalysisLogger, 
        session_id: str
    ) -> Dict[str, Any]:
        try:
            step_logger.info(f"[{correlation_id}] 🧠 Creating enhanced prompt with verified facts")
            if tree_sitter_facts.get('tree_sitter_enabled', False):
                enhanced_prompt = self._create_enhanced_analysis_prompt(cookbook_content, tree_sitter_facts)
                step_logger.info(f"[{correlation_id}] 📝 Using Tree-sitter enhanced prompt")
            else:
                enhanced_prompt = self._create_analysis_prompt(cookbook_content)
                step_logger.info(f"[{correlation_id}] 📝 Using standard prompt (Tree-sitter unavailable)")
            result = await self._analyze_direct(enhanced_prompt, correlation_id, step_logger, session_id)
            if result and result.get("success") and not result.get("postprocess_error"):
                step_logger.info(f"[{correlation_id}]  LlamaStack agent analysis succeeded")
                return result
            else:
                step_logger.warning(f"[{correlation_id}] ⚠️ LlamaStack agent analysis had issues: {result}")
        except Exception as e:
            step_logger.warning(f"[{correlation_id}] ⚠️ LlamaStack agent analysis failed: {e}")
        step_logger.warning(f"[{correlation_id}] 🔄 Creating intelligent fallback from verified facts")
        return self._create_intelligent_fallback_from_facts(tree_sitter_facts, correlation_id, cookbook_content)

    def _create_enhanced_analysis_prompt(self, cookbook_content: str, tree_sitter_facts: Dict[str, Any]) -> str:
        resources = tree_sitter_facts['resources']
        deps = tree_sitter_facts['dependencies']
        metadata = tree_sitter_facts['metadata']
        summary = tree_sitter_facts['summary']
        return f"""You are analyzing a Chef cookbook.

Verified facts (from Tree-sitter):
- Cookbook: {metadata.get('name', 'unknown')} v{metadata.get('version', 'unknown')}
- Packages: {resources['packages']}
- Services: {resources['services']}
- Files: {resources['files']}
- Templates: {resources['templates']}
- Direct Deps: {deps['cookbook_deps']}
- Wrapper Cookbooks: {deps['include_recipes']}
- Complexity Score: {summary['complexity_score']}
- Total Resources: {summary['total_resources']}

Now, return only this JSON structure filled in with accurate values based on the above:

{{
"success": true,
"version_requirements": {{
    "min_chef_version": "string",
    "min_ruby_version": "string",
    "migration_effort": "LOW|MEDIUM|HIGH",
    "estimated_hours": number
}},
"dependencies": {{
    "is_wrapper": boolean,
    "direct_deps": {json.dumps(deps['cookbook_deps'])},
    "runtime_deps": [],
    "circular_risk": "none|low|high"
}},
"functionality": {{
    "primary_purpose": "string",
    "services": {json.dumps(resources['services'])},
    "packages": {json.dumps(resources['packages'])},
    "files_managed": {json.dumps(resources['files'])}
}},
"recommendations": {{
    "consolidation_action": "REUSE|EXTEND|REWRITE",
    "rationale": "string",
    "migration_priority": "LOW|MEDIUM|HIGH"
}},
"complexity_level": "Low|Medium|High",
"detailed_analysis": "string",
"key_operations": ["string"],
"configuration_details": "string",
"conversion_notes": "string"
}}

DO NOT return Markdown, explanations, or prose. Respond ONLY with this JSON object."""

    def _merge_analysis_results(
        self,
        tree_sitter_facts: Dict[str, Any],
        llm_analysis: Dict[str, Any],
        cookbook_name: str,
        correlation_id: str,
        step_logger: ChefAnalysisLogger
    ) -> Dict[str, Any]:
        step_logger.info(f"[{correlation_id}] 🔄 Merging verified facts with LLM analysis")
        merged_result = llm_analysis.copy() if llm_analysis else {}
        merged_result["success"] = True
        merged_result["cookbook_name"] = cookbook_name
        merged_result["analysis_method"] = "tree_sitter_llm" if tree_sitter_facts.get('tree_sitter_enabled', False) else "llm_only"
        if tree_sitter_facts.get('tree_sitter_enabled', False):
            step_logger.info(f"[{correlation_id}] 🌳 Applying verified Tree-sitter facts (take precedence)")
            if "functionality" not in merged_result:
                merged_result["functionality"] = {}
            merged_result["functionality"]["services"] = tree_sitter_facts["resources"]["services"]
            merged_result["functionality"]["packages"] = tree_sitter_facts["resources"]["packages"]
            merged_result["functionality"]["files_managed"] = tree_sitter_facts["resources"]["files"][:10]
            if "dependencies" not in merged_result:
                merged_result["dependencies"] = {}
            merged_result["dependencies"]["is_wrapper"] = tree_sitter_facts["summary"]["is_wrapper"]
            merged_result["dependencies"]["direct_deps"] = tree_sitter_facts["dependencies"]["cookbook_deps"]
            merged_result["dependencies"]["wrapped_cookbooks"] = tree_sitter_facts["dependencies"]["include_recipes"]
            merged_result["tree_sitter_facts"] = {
                "complexity_score": tree_sitter_facts["summary"]["complexity_score"],
                "syntax_success_rate": tree_sitter_facts["summary"]["syntax_success_rate"],
                "total_resources": tree_sitter_facts["summary"]["total_resources"],
                "verified_cookbook_name": tree_sitter_facts["metadata"].get("name", "unknown"),
                "verified_version": tree_sitter_facts["metadata"].get("version", "unknown"),
                "has_metadata": tree_sitter_facts["summary"]["has_metadata"]
            }
            step_logger.info(f"[{correlation_id}]  Merged {tree_sitter_facts['summary']['total_resources']} verified resources")
        else:
            step_logger.warning(f"[{correlation_id}] ⚠️ Tree-sitter facts unavailable, using LLM analysis only")
            merged_result["tree_sitter_facts"] = {"enabled": False, "reason": "Tree-sitter analysis failed"}
        step_logger.info(f"[{correlation_id}]  Analysis merge completed successfully")
        return merged_result

    def _create_intelligent_fallback_from_facts(
        self,
        tree_sitter_facts: Dict[str, Any],
        correlation_id: str,
        cookbook_content: str
    ) -> Dict[str, Any]:
        self.logger.info(f"[{correlation_id}] 🔄 Creating intelligent fallback analysis")
        if not tree_sitter_facts.get('tree_sitter_enabled', False):
            self.logger.warning(f"[{correlation_id}] ⚠️ No Tree-sitter facts available - using standard fallback")
            return extract_and_validate_analysis("{}", correlation_id, cookbook_content)
        summary = tree_sitter_facts['summary']
        resources = tree_sitter_facts['resources']
        deps = tree_sitter_facts['dependencies']
        metadata = tree_sitter_facts['metadata']
        self.logger.info(f"[{correlation_id}] 🌳 Creating fallback from {summary['total_resources']} verified resources")
        complexity_score = summary['complexity_score']
        if complexity_score <= 10:
            migration_effort = "LOW"
            estimated_hours = 4.0
        elif complexity_score <= 25:
            migration_effort = "MEDIUM"
            estimated_hours = 12.0
        else:
            migration_effort = "HIGH"
            estimated_hours = 24.0
        if resources['services']:
            primary_purpose = f"Service management and configuration for {', '.join(resources['services'][:3])}"
            if len(resources['services']) > 3:
                primary_purpose += f" and {len(resources['services']) - 3} more services"
        elif resources['packages']:
            primary_purpose = f"Package installation and management for {', '.join(resources['packages'][:3])}"
            if len(resources['packages']) > 3:
                primary_purpose += f" and {len(resources['packages']) - 3} more packages"
        else:
            primary_purpose = "System configuration and infrastructure management"
        fallback_analysis = {
            "success": True,
            "cookbook_name": metadata.get('name', 'unknown'),
            "analysis_method": "tree_sitter_fallback",
            "version_requirements": {
                "min_chef_version": "14.0",
                "min_ruby_version": "2.5",
                "migration_effort": migration_effort,
                "estimated_hours": estimated_hours,
                "deprecated_features": []
            },
            "dependencies": {
                "is_wrapper": summary['is_wrapper'],
                "wrapped_cookbooks": deps['include_recipes'],
                "direct_deps": deps['cookbook_deps'],
                "runtime_deps": [],
                "circular_risk": "low" if len(deps['include_recipes']) <= 2 else "medium"
            },
            "functionality": {
                "primary_purpose": primary_purpose,
                "services": resources['services'],
                "packages": resources['packages'],
                "files_managed": resources['files'][:10],
                "reusability": "HIGH" if not summary['is_wrapper'] else "MEDIUM",
                "customization_points": ["configuration files", "service parameters"] + ([f"{len(resources['templates'])} template files"] if resources['templates'] else [])
            },
            "recommendations": {
                "consolidation_action": "EXTEND" if summary['is_wrapper'] else "REUSE",
                "rationale": f"Tree-sitter analysis shows {summary['total_resources']} verified resources with {migration_effort.lower()} complexity",
                "migration_priority": "HIGH" if complexity_score > 25 else "MEDIUM" if complexity_score > 10 else "LOW",
                "risk_factors": (["Wrapper cookbook dependencies"] if summary['is_wrapper'] else []) +
                              (["High resource complexity"] if complexity_score > 25 else []),
                "migration_steps": [
                    f"Analyze {len(resources['packages'])} package dependencies" if resources['packages'] else "",
                    f"Convert {len(resources['services'])} service configurations" if resources['services'] else "",
                    f"Migrate {len(resources['templates'])} template files" if resources['templates'] else "",
                    "Test and validate converted infrastructure"
                ]
            },
            "tree_sitter_facts": {
                "complexity_score": complexity_score,
                "syntax_success_rate": summary['syntax_success_rate'],
                "total_resources": summary['total_resources'],
                "fallback_reason": "LLM analysis failed, using Tree-sitter facts"
            }
        }
        fallback_analysis["recommendations"]["migration_steps"] = [
            step for step in fallback_analysis["recommendations"]["migration_steps"] if step
        ]
        self.logger.info(f"[{correlation_id}]  Intelligent fallback created from verified Tree-sitter facts")
        return fallback_analysis

    async def _fallback_to_standard_analysis(
        self,
        cookbook_data: Dict[str, Any],
        correlation_id: str
    ) -> Dict[str, Any]:
        self.logger.warning(f"[{correlation_id}] 🔄 Executing standard LLM-only fallback")
        cookbook_name = cookbook_data.get("name", "unknown")
        files = cookbook_data.get("files", {})
        cookbook_content = self._format_cookbook_content(cookbook_name, files)
        try:
            result = await self._analyze_with_retries(
                cookbook_content, correlation_id, create_chef_logger(correlation_id), self.session_id
            )
            if isinstance(result, dict):
                result["analysis_method"] = "standard_fallback"
                result["tree_sitter_facts"] = {"enabled": False, "reason": "Complete fallback to LLM-only"}
            return result
        except Exception as e:
            self.logger.error(f"[{correlation_id}]  Standard fallback also failed: {e}")
            return extract_and_validate_analysis("{}", correlation_id, cookbook_content)

    async def _analyze_with_retries(
        self, 
        cookbook_content: str, 
        correlation_id: str, 
        logger: ChefAnalysisLogger, 
        session_id: str
    ) -> Dict[str, Any]:
        try:
            logger.info("🔄 Starting standard LLM analysis")
            result = await self._analyze_direct(cookbook_content, correlation_id, logger, session_id)
            if result and result.get("success") and not result.get("postprocess_error"):
                logger.info(" Standard analysis succeeded")
                return result
            else:
                logger.warning(f"⚠️ Standard analysis failed: {result}")
        except Exception as e:
            logger.warning(f"⚠️ Standard analysis failed with exception: {e}")
        logger.warning("⚠️ LLM analysis failed - processor will handle intelligent fallback")
        return extract_and_validate_analysis("{}", correlation_id, cookbook_content)

    async def _analyze_direct(
        self, 
        prompt: str, 
        correlation_id: str, 
        step_logger: ChefAnalysisLogger, 
        session_id: str
    ) -> Optional[Dict[str, Any]]:
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
                step_logger.error("No turn completed in LlamaStack response")
                return None
            raw_response = turn.output_message.content
            step_logger.info(f"📥 Received LlamaStack response: {len(raw_response)} chars")
            result = extract_and_validate_analysis(raw_response, correlation_id, prompt[:500])
            step_logger.info(f"🔍 Processor result: success={result.get('success')}")
            return result
        except Exception as e:
            step_logger.error(f" LlamaStack analysis failed: {e}")
            return None

    def _create_analysis_prompt(self, cookbook_content: str) -> str:
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
        correlation_id = correlation_id or create_correlation_id()
        cookbook_name = cookbook_data.get("name", "unknown")
        try:
            yield {
                "type": "progress",
                "status": "starting",
                "message": "🍳 Chef cookbook analysis started",
                "correlation_id": correlation_id
            }
            if self.tree_sitter_enabled:
                yield {
                    "type": "progress",
                    "status": "extracting",
                    "message": "🌳 Extracting verified structural facts",
                    "progress": 0.3,
                    "correlation_id": correlation_id
                }
            yield {
                "type": "progress", 
                "status": "processing",
                "message": "🧠 LlamaStack agent analyzing cookbook",
                "progress": 0.7,
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
        tree_sitter_status = {}
        if self.tree_sitter:
            tree_sitter_status = self.tree_sitter.get_status()
        return {
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "client_base_url": self.client.base_url,
            "timeout": self.timeout,
            "status": "ready",
            "approach": "tree_sitter_llm" if self.tree_sitter_enabled else "llm_only",
            "tree_sitter_enabled": self.tree_sitter_enabled,
            "tree_sitter_status": tree_sitter_status,
            "methods_available": ["tree_sitter_llm", "llm_only", "fallback"],
            "capabilities": [
                "verified_resource_extraction" if self.tree_sitter_enabled else "llm_resource_detection",
                "syntax_validation" if self.tree_sitter_enabled else "content_analysis",
                "dependency_analysis",
                "migration_assessment",
                "streaming_analysis"
            ]
        }

    async def health_check(self) -> bool:
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
            self.logger.info(" Health check passed")
            return True
        except Exception as e:
            self.logger.error(f" Health check failed: {e}")
            return False

    def get_tree_sitter_status(self) -> Dict[str, Any]:
        if not self.tree_sitter:
            return {
                "enabled": False,
                "reason": "Not initialized",
                "supported_formats": []
            }
        return {
            "enabled": self.tree_sitter_enabled,
            "status": self.tree_sitter.get_status(),
            "supported_formats": self.tree_sitter.get_supported_formats(),
            "capabilities": [
                "language_detection",
                "syntax_validation", 
                "chef_resource_extraction",
                "dependency_analysis",
                "metadata_parsing"
            ]
        }
