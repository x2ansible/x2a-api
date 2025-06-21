"""
BladeLogic Analysis Agent
Enterprise-grade agent for analyzing BladeLogic automation content including:
- RSCD Agent deployment scripts
- Compliance templates (HIPAA, SOX, PCI-DSS)
- Patch management workflows  
- NSH scripts and BlPackages
- Job flows and automation templates
"""

import time
import uuid
import json
import logging
from typing import Dict, Any, Optional, AsyncGenerator, List

from llama_stack_client import LlamaStackClient
from llama_stack_client.types import UserMessage

from agents.bladelogic_analysis.utils import create_correlation_id, BladeLogicExtractor
from agents.bladelogic_analysis.processor import extract_and_validate_analysis

# Handle shared modules gracefully
try:
    from shared.exceptions import CookbookAnalysisError
except ImportError:
    class CookbookAnalysisError(Exception):
        """Cookbook analysis error"""
        pass

try:
    from shared.log_utils import create_chef_logger, ChefAnalysisLogger
except ImportError:
    # Fallback logger implementation
    def create_chef_logger(name: str):
        return logging.getLogger(f"bladelogic_{name}")
    
    class ChefAnalysisLogger:
        def __init__(self, logger):
            self.logger = logger
        
        def info(self, msg):
            self.logger.info(msg)
        
        def warning(self, msg):
            self.logger.warning(msg)
        
        def error(self, msg):
            self.logger.error(msg)

logger = logging.getLogger(__name__)

class BladeLogicAnalysisAgent:
    """
    Expert BladeLogic Analysis Agent for enterprise automation analysis.
    Handles all major BladeLogic object types and automation patterns.
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
        self.logger = create_chef_logger("bladelogic_init")
        self.extractor = BladeLogicExtractor()

        self.logger.info(f"🔧 BladeLogicAnalysisAgent initialized - agent_id: {agent_id}, session_id: {session_id}")

    def create_new_session(self, correlation_id: str) -> str:
        """Create new session for BladeLogic analysis"""
        try:
            session_name = f"bladelogic-analysis-{correlation_id}-{uuid.uuid4()}"
            response = self.client.agents.session.create(
                agent_id=self.agent_id,
                session_name=session_name,
            )
            session_id = response.session_id
            self.logger.info(f"📱 Created BladeLogic session: {session_id} for correlation: {correlation_id}")
            return session_id
        except Exception as e:
            self.logger.error(f" Failed to create session: {e}")
            self.logger.info(f"↩️ Falling back to default session: {self.session_id}")
            return self.session_id

    async def analyze_bladelogic(
        self,
        bladelogic_data: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze BladeLogic automation content"""
        correlation_id = correlation_id or create_correlation_id()
        step_logger = create_chef_logger(correlation_id)
        start_time = time.time()

        object_name = bladelogic_data.get("name", "unknown")
        files = bladelogic_data.get("files", {})

        # Log all files received
        step_logger.info(f"🔧 BladeLogic files received for analysis ({len(files)}): {list(files.keys())}")
        for fname, content in files.items():
            preview = content[:120].replace("\\n", " ") + ("..." if len(content) > 120 else "")
            step_logger.info(f"  └── {fname} ({len(content)} chars): {preview}")

        step_logger.info(f"🔄 Starting BladeLogic automation analysis")

        try:
            if not files:
                raise ValueError("BladeLogic object must contain at least one file")

            analysis_session_id = self.create_new_session(correlation_id)

            # STEP 1: Detect BladeLogic object type and extract metadata
            step_logger.info("🔍 STEP 1: Detecting BladeLogic object type and extracting metadata")
            primary_file = self._get_primary_file(files)
            primary_content = files[primary_file]
            
            object_type = self.extractor.detect_bladelogic_type(primary_content, primary_file)
            metadata = self.extractor.extract_bladelogic_metadata(primary_content, object_type)
            
            step_logger.info(f"  ✓ Detected type: {object_type}")
            step_logger.info(f"  ✓ Extracted metadata: {metadata}")

            # STEP 2: Extract BladeLogic operations and patterns
            step_logger.info("⚙️ STEP 2: Extracting BladeLogic operations and automation patterns")
            operations = self.extractor.extract_bladelogic_operations(primary_content, object_type)
            step_logger.info(f"  ✓ Found operations: {sum(len(ops) for ops in operations.values())} total")

            # STEP 3: LLM Analysis with BladeLogic-specific prompt
            step_logger.info("🧠 STEP 3: LlamaStack agent BladeLogic analysis")
            bladelogic_content = self._format_bladelogic_content(object_name, files, object_type, metadata)
            
            llm_analysis = await self._analyze_with_bladelogic_prompt(
                bladelogic_content, object_type, metadata, operations, correlation_id, step_logger, analysis_session_id
            )

            # STEP 4: Merge extracted facts with LLM analysis
            step_logger.info("🔄 STEP 4: Merging BladeLogic facts with LLM analysis")
            final_result = self._merge_bladelogic_results(
                metadata, operations, llm_analysis, object_name, object_type, correlation_id, step_logger
            )

            total_time = time.time() - start_time
            step_logger.info(f" BladeLogic analysis completed successfully in {total_time:.3f}s")

            final_result["session_info"] = {
                "agent_id": self.agent_id,
                "session_id": analysis_session_id,
                "correlation_id": correlation_id,
                "method_used": "bladelogic_expert_analysis",
                "analysis_time_seconds": round(total_time, 3),
                "object_type": object_type
            }
            
            return final_result

        except Exception as e:
            total_time = time.time() - start_time
            step_logger.error(f" BladeLogic analysis failed after {total_time:.3f}s: {str(e)}")
            step_logger.warning("🔄 Attempting fallback analysis")
            try:
                return await self._fallback_bladelogic_analysis(bladelogic_data, correlation_id)
            except Exception as fallback_error:
                step_logger.error(f" Fallback analysis also failed: {fallback_error}")
                raise CookbookAnalysisError(f"BladeLogic analysis failed: {str(e)}")

    def _get_primary_file(self, files: Dict[str, str]) -> str:
        """Determine the primary file for analysis"""
        # Priority order for BladeLogic files
        priority_patterns = [
            r'.*\\.nsh$',           # NSH scripts
            r'.*job.*\\.(txt|sh)$', # Job files
            r'.*patch.*\\.(sh|txt)$', # Patch scripts
            r'.*compliance.*\\.(yaml|yml|txt)$', # Compliance templates
            r'.*\\.sh$',            # Shell scripts
            r'.*\\.yaml$',          # YAML templates
            r'.*\\.yml$',           # YAML templates
        ]
        
        import re
        for pattern in priority_patterns:
            for filename in files.keys():
                if re.match(pattern, filename.lower()):
                    return filename
        
        # Default to first file
        return list(files.keys())[0]

    async def _analyze_with_bladelogic_prompt(
        self, 
        bladelogic_content: str,
        object_type: str,
        metadata: Dict[str, Any],
        operations: Dict[str, List[str]],
        correlation_id: str, 
        step_logger: ChefAnalysisLogger, 
        session_id: str
    ) -> Dict[str, Any]:
        """Analyze with BladeLogic-specific enhanced prompt"""
        try:
            step_logger.info(f"[{correlation_id}] 🧠 Creating BladeLogic expert analysis prompt")
            enhanced_prompt = self._create_bladelogic_analysis_prompt(
                bladelogic_content, object_type, metadata, operations
            )
            step_logger.info(f"[{correlation_id}] 📝 Using BladeLogic expert prompt for {object_type}")
            
            result = await self._analyze_direct(enhanced_prompt, correlation_id, step_logger, session_id)
            if result and result.get("success") and not result.get("postprocess_error"):
                step_logger.info(f"[{correlation_id}]  LlamaStack BladeLogic analysis succeeded")
                return result
            else:
                step_logger.warning(f"[{correlation_id}] ⚠️ LlamaStack analysis had issues: {result}")
        except Exception as e:
            step_logger.warning(f"[{correlation_id}] ⚠️ LlamaStack BladeLogic analysis failed: {e}")
        
        step_logger.warning(f"[{correlation_id}] 🔄 Creating intelligent BladeLogic fallback")
        return self._create_bladelogic_fallback(object_type, metadata, operations, correlation_id, bladelogic_content)

    def _create_bladelogic_analysis_prompt(
        self, 
        bladelogic_content: str, 
        object_type: str, 
        metadata: Dict[str, Any],
        operations: Dict[str, List[str]]
    ) -> str:
        """Create expert BladeLogic analysis prompt"""
        
        extracted_info = f"""
Object Type: {object_type}
Extracted Metadata: {metadata}
Extracted Operations:
- Services: {operations.get('services', [])}
- Packages: {operations.get('packages', [])}
- Files: {operations.get('files', [])}
- Commands: {operations.get('commands', [])}
- Policies: {operations.get('policies', [])}
- Target Servers: {operations.get('targets', [])}
"""

        return f"""You are analyzing a BladeLogic automation object. BladeLogic is an enterprise datacenter automation platform used for:
- Server provisioning and configuration management
- Patch management and compliance scanning  
- Application deployment and release automation
- Security compliance enforcement (HIPAA, SOX, PCI-DSS)

EXTRACTED FACTS:
{extracted_info}

CONTENT TO ANALYZE:
{bladelogic_content}

Analyze this BladeLogic automation and provide a comprehensive assessment. Return ONLY valid JSON with your analysis:

{{
"success": true,
"object_name": "detected name",
"object_type": "{object_type}",
"version_requirements": {{
    "min_bladelogic_version": "version string",
    "min_nsh_version": "NSH version if applicable", 
    "migration_effort": "LOW|MEDIUM|HIGH",
    "estimated_hours": number,
    "deprecated_features": ["list of deprecated BladeLogic features"]
}},
"dependencies": {{
    "is_composite": boolean,
    "composite_jobs": ["list of referenced jobs"],
    "package_dependencies": ["BlPackages or software dependencies"],
    "policy_dependencies": ["compliance policies"],
    "external_scripts": ["external scripts referenced"],
    "circular_risk": "none|low|medium|high"
}},
"functionality": {{
    "primary_purpose": "description of what this automation does",
    "automation_type": "COMPLIANCE|PATCHING|DEPLOYMENT|CONFIGURATION|MONITORING",
    "target_platforms": ["Windows", "Linux", "AIX", "Solaris"],
    "managed_services": ["services managed"],
    "managed_packages": ["packages installed/managed"],
    "managed_files": ["key files/directories managed"],
    "compliance_policies": ["compliance standards enforced"],
    "reusability": "LOW|MEDIUM|HIGH",
    "customization_points": ["areas that can be customized"]
}},
"recommendations": {{
    "consolidation_action": "REUSE|EXTEND|RECREATE|MODERNIZE",
    "rationale": "detailed explanation of recommendation",
    "migration_priority": "LOW|MEDIUM|HIGH|CRITICAL",
    "risk_factors": ["migration risks to consider"],
    "ansible_equivalent": "suggested Ansible approach for conversion"
}},
"detailed_analysis": "comprehensive analysis of the BladeLogic automation",
"key_operations": ["primary operations performed"],
"automation_details": "details about automation workflow",
"complexity_level": "Low|Medium|High",
"convertible": boolean,
"conversion_notes": "notes about converting to modern automation"
}}

Focus on:
1. **BladeLogic Expertise**: Understand RSCD agents, BlPackages, NSH scripts, Compliance Jobs
2. **Enterprise Context**: Consider compliance requirements, patching workflows, multi-platform support
3. **Migration Assessment**: Evaluate conversion to Ansible/modern automation platforms
4. **Risk Analysis**: Identify dependencies, complexity factors, business impact

Return ONLY the JSON object with your expert BladeLogic analysis."""

    def _merge_bladelogic_results(
        self,
        metadata: Dict[str, Any],
        operations: Dict[str, List[str]],
        llm_analysis: Dict[str, Any],
        object_name: str,
        object_type: str,
        correlation_id: str,
        step_logger: ChefAnalysisLogger
    ) -> Dict[str, Any]:
        """Merge extracted BladeLogic facts with LLM analysis"""
        step_logger.info(f"[{correlation_id}] 🔄 Merging BladeLogic facts with LLM analysis")
        
        merged_result = llm_analysis.copy() if llm_analysis else {}
        merged_result["success"] = True
        merged_result["object_name"] = object_name
        merged_result["object_type"] = object_type
        merged_result["analysis_method"] = "bladelogic_expert_analysis"
        
        # Apply extracted facts (take precedence over LLM for factual data)
        step_logger.info(f"[{correlation_id}] 🔧 Applying extracted BladeLogic facts")
        
        if "functionality" not in merged_result:
            merged_result["functionality"] = {}
        
        # Use extracted operations
        merged_result["functionality"]["managed_services"] = operations["services"]
        merged_result["functionality"]["managed_packages"] = operations["packages"] 
        merged_result["functionality"]["managed_files"] = operations["files"][:10]
        
        if "dependencies" not in merged_result:
            merged_result["dependencies"] = {}
        
        # Use extracted metadata for dependencies
        merged_result["dependencies"]["external_scripts"] = operations.get("commands", [])
        
        # Add BladeLogic-specific extracted facts
        merged_result["bladelogic_facts"] = {
            "extracted_metadata": metadata,
            "operation_counts": {k: len(v) for k, v in operations.items()},
            "total_operations": sum(len(v) for v in operations.values()),
            "object_type_detected": object_type,
            "has_compliance_elements": bool(operations.get("policies")),
            "multi_platform": len(set(operations.get("targets", []))) > 1
        }
        
        step_logger.info(f"[{correlation_id}]  Merged {sum(len(v) for v in operations.values())} BladeLogic operations")
        return merged_result

    def _create_bladelogic_fallback(
        self,
        object_type: str,
        metadata: Dict[str, Any],
        operations: Dict[str, List[str]],
        correlation_id: str,
        bladelogic_content: str
    ) -> Dict[str, Any]:
        """Create intelligent BladeLogic fallback analysis"""
        self.logger.info(f"[{correlation_id}] 🔄 Creating BladeLogic intelligent fallback")
        
        total_operations = sum(len(ops) for ops in operations.values())
        
        # Determine automation type from operations
        if operations.get("policies"):
            automation_type = "COMPLIANCE"
            migration_effort = "HIGH"
            estimated_hours = 20.0
        elif "patch" in bladelogic_content.lower() or "update" in bladelogic_content.lower():
            automation_type = "PATCHING" 
            migration_effort = "MEDIUM"
            estimated_hours = 12.0
        elif operations.get("packages"):
            automation_type = "DEPLOYMENT"
            migration_effort = "MEDIUM"
            estimated_hours = 10.0
        else:
            automation_type = "CONFIGURATION"
            migration_effort = "LOW"
            estimated_hours = 6.0
        
        # Determine complexity
        if total_operations > 15 or automation_type == "COMPLIANCE":
            complexity = "High"
        elif total_operations > 8:
            complexity = "Medium"
        else:
            complexity = "Low"
        
        # Generate primary purpose
        if operations["services"] and operations["packages"]:
            primary_purpose = f"BladeLogic {automation_type.lower()} automation managing {len(operations['services'])} services and {len(operations['packages'])} packages"
        elif operations["services"]:
            primary_purpose = f"Service management automation for {', '.join(operations['services'][:3])}"
        elif operations["packages"]:
            primary_purpose = f"Package {automation_type.lower()} automation for {', '.join(operations['packages'][:3])}"
        else:
            primary_purpose = f"BladeLogic {automation_type.lower()} automation"
        
        return {
            "success": True,
            "object_name": metadata.get("name", "unknown"),
            "object_type": object_type,
            "analysis_method": "bladelogic_fallback",
            "version_requirements": {
                "min_bladelogic_version": "8.6",
                "min_nsh_version": "8.6",
                "migration_effort": migration_effort,
                "estimated_hours": estimated_hours,
                "deprecated_features": []
            },
            "dependencies": {
                "is_composite": len(operations.get("commands", [])) > 3,
                "composite_jobs": [],
                "package_dependencies": operations["packages"],
                "policy_dependencies": operations.get("policies", []),
                "external_scripts": operations.get("commands", []),
                "circular_risk": "low"
            },
            "functionality": {
                "primary_purpose": primary_purpose,
                "automation_type": automation_type,
                "target_platforms": ["Windows", "Linux"],
                "managed_services": operations["services"],
                "managed_packages": operations["packages"],
                "managed_files": operations["files"],
                "compliance_policies": operations.get("policies", []),
                "reusability": "HIGH" if automation_type != "COMPLIANCE" else "MEDIUM",
                "customization_points": ["target servers", "parameters", "schedules"]
            },
            "recommendations": {
                "consolidation_action": "MODERNIZE" if automation_type == "COMPLIANCE" else "REUSE",
                "rationale": f"BladeLogic {automation_type.lower()} automation with {complexity.lower()} complexity and {total_operations} operations",
                "migration_priority": "HIGH" if automation_type == "COMPLIANCE" else "MEDIUM",
                "risk_factors": ["BladeLogic platform dependency", "Enterprise automation complexity"],
                "ansible_equivalent": self._get_ansible_equivalent(automation_type)
            },
            "bladelogic_facts": {
                "extracted_metadata": metadata,
                "operation_counts": {k: len(v) for k, v in operations.items()},
                "fallback_reason": "LLM analysis failed, using extracted facts"
            }
        }

    def _get_ansible_equivalent(self, automation_type: str) -> str:
        """Get Ansible equivalent for BladeLogic automation type"""
        equivalents = {
            "COMPLIANCE": "ansible-hardening + custom compliance modules + SCAP content",
            "PATCHING": "ansible.posix.patch + yum/apt modules + reboot management",
            "DEPLOYMENT": "ansible.builtin package modules + application deployment playbooks",
            "CONFIGURATION": "ansible.builtin template + file modules + service management",
            "MONITORING": "ansible monitoring roles + notification modules"
        }
        return equivalents.get(automation_type, "Custom Ansible playbooks and modules")

    async def _fallback_bladelogic_analysis(
        self,
        bladelogic_data: Dict[str, Any],
        correlation_id: str
    ) -> Dict[str, Any]:
        """Fallback BladeLogic analysis"""
        self.logger.warning(f"[{correlation_id}] 🔄 Executing BladeLogic fallback analysis")
        
        object_name = bladelogic_data.get("name", "unknown")
        files = bladelogic_data.get("files", {})
        
        primary_file = self._get_primary_file(files)
        content = files[primary_file]
        
        try:
            object_type = self.extractor.detect_bladelogic_type(content, primary_file)
            result = await self._analyze_with_retries(content, object_type, correlation_id, create_chef_logger(correlation_id))
            if isinstance(result, dict):
                result["analysis_method"] = "bladelogic_fallback"
                result["object_name"] = object_name
                result["object_type"] = object_type
            return result
        except Exception as e:
            self.logger.error(f"[{correlation_id}]  BladeLogic fallback failed: {e}")
            return extract_and_validate_analysis("{}", correlation_id, content, object_type)

    async def _analyze_with_retries(
        self, 
        content: str,
        object_type: str, 
        correlation_id: str, 
        logger: ChefAnalysisLogger
    ) -> Dict[str, Any]:
        """Analyze BladeLogic content with retries"""
        try:
            logger.info("🔄 Starting BladeLogic LLM analysis")
            prompt = self._create_basic_bladelogic_prompt(content, object_type)
            result = await self._analyze_direct(prompt, correlation_id, logger, self.session_id)
            if result and result.get("success"):
                logger.info(" BladeLogic analysis succeeded")
                return result
            else:
                logger.warning(f"⚠️ BladeLogic analysis failed: {result}")
        except Exception as e:
            logger.warning(f"⚠️ BladeLogic analysis failed with exception: {e}")
        
        logger.warning("⚠️ LLM analysis failed - using processor fallback")
        return extract_and_validate_analysis("{}", correlation_id, content, object_type)

    async def _analyze_direct(
        self, 
        prompt: str, 
        correlation_id: str, 
        step_logger: ChefAnalysisLogger, 
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """Direct LLM analysis via LlamaStack"""
        try:
            messages = [UserMessage(role="user", content=prompt)]
            
            step_logger.info(f"[{correlation_id}] 🤖 Calling LlamaStack agent for BladeLogic analysis...")
            
            generator = self.client.agents.turn.create(
                agent_id=self.agent_id,
                session_id=session_id,
                messages=messages,
                stream=True,
            )
            
            turn = None
            step_logger.info(f"[{correlation_id}] 📡 Processing LlamaStack response stream...")
            
            for chunk in generator:
                if chunk and hasattr(chunk, 'event') and chunk.event:
                    event = chunk.event
                    if hasattr(event, 'payload') and event.payload:
                        event_type = getattr(event.payload, 'event_type', None)
                        if event_type == "turn_complete":
                            turn = getattr(event.payload, 'turn', None)
                            step_logger.info(f"[{correlation_id}]  LlamaStack turn completed")
                            break
                        elif event_type == "step_complete":
                            step_logger.info(f"[{correlation_id}] 🔄 LlamaStack step completed")
                    else:
                        step_logger.warning(f"[{correlation_id}] ⚠️ Received chunk without payload")
                else:
                    step_logger.warning(f"[{correlation_id}] ⚠️ Received empty or invalid chunk")
            
            if not turn:
                step_logger.error(f"[{correlation_id}]  No turn completed in LlamaStack response")
                return None
            
            if not hasattr(turn, 'output_message') or not turn.output_message:
                step_logger.error(f"[{correlation_id}]  No output message in turn")
                return None
            
            raw_response = turn.output_message.content
            step_logger.info(f"[{correlation_id}] 📥 Received LlamaStack response: {len(raw_response)} chars")
            
            # Extract object type from prompt or use default
            object_type = "JOB"  # Default
            if "object_type" in prompt:
                import re
                match = re.search(r'"object_type": "([^"]+)"', prompt)
                if match:
                    object_type = match.group(1)
            
            result = extract_and_validate_analysis(raw_response, correlation_id, prompt[:500], object_type)
            step_logger.info(f"[{correlation_id}] 🔍 Processor result: success={result.get('success')}")
            
            if result.get('success'):
                step_logger.info(f"[{correlation_id}]  LlamaStack BladeLogic analysis succeeded")
            else:
                step_logger.warning(f"[{correlation_id}] ⚠️ Analysis succeeded but with issues")
            
            return result
            
        except Exception as e:
            step_logger.error(f"[{correlation_id}]  LlamaStack analysis failed: {e}")
            import traceback
            step_logger.error(f"[{correlation_id}] 📋 Traceback: {traceback.format_exc()}")
            return None

    def _create_basic_bladelogic_prompt(self, content: str, object_type: str) -> str:
        """Create basic BladeLogic analysis prompt"""
        return f"""Analyze this BladeLogic {object_type} automation content:

{content}

Provide a JSON analysis focusing on:
1. Version requirements and migration effort
2. Dependencies and complexity 
3. Functionality and automation type
4. Recommendations for modernization

Return only valid JSON with the analysis."""

    def _format_bladelogic_content(
        self, 
        object_name: str, 
        files: Dict[str, str], 
        object_type: str,
        metadata: Dict[str, Any]
    ) -> str:
        """Format BladeLogic content for analysis"""
        content_parts = [
            f"BladeLogic Object: {object_name}",
            f"Object Type: {object_type}",
            f"Metadata: {metadata}",
            ""
        ]
        
        for filename, content in files.items():
            content_parts.append(f"\\n=== File: {filename} ===")
            content_parts.append(content.strip())
        
        return "\\n".join(content_parts)

    async def analyze_bladelogic_stream(
        self,
        bladelogic_data: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream BladeLogic analysis with detailed progress updates"""
        correlation_id = correlation_id or create_correlation_id()
        object_name = bladelogic_data.get("name", "unknown")
        files = bladelogic_data.get("files", {})
        
        try:
            # Step 1: Starting
            yield {
                "type": "progress",
                "status": "starting",
                "message": "🔧 BladeLogic automation analysis started",
                "progress": 0.1,
                "correlation_id": correlation_id,
                "details": f"Analyzing {len(files)} BladeLogic files"
            }
            
            # Step 2: Object Detection
            yield {
                "type": "progress",
                "status": "detecting",
                "message": "🔍 Detecting BladeLogic object type and extracting metadata",
                "progress": 0.2,
                "correlation_id": correlation_id
            }
            
            # Perform detection
            primary_file = self._get_primary_file(files)
            primary_content = files[primary_file]
            object_type = self.extractor.detect_bladelogic_type(primary_content, primary_file)
            
            yield {
                "type": "progress",
                "status": "detected",
                "message": f" Detected BladeLogic {object_type}",
                "progress": 0.3,
                "correlation_id": correlation_id,
                "details": f"Primary file: {primary_file}"
            }
            
            # Step 3: Operations Extraction
            yield {
                "type": "progress",
                "status": "extracting",
                "message": "⚙️ Extracting BladeLogic operations and automation patterns", 
                "progress": 0.4,
                "correlation_id": correlation_id
            }
            
            operations = self.extractor.extract_bladelogic_operations(primary_content, object_type)
            total_operations = sum(len(ops) for ops in operations.values())
            
            yield {
                "type": "progress",
                "status": "extracted",
                "message": f" Found {total_operations} BladeLogic operations",
                "progress": 0.5,
                "correlation_id": correlation_id,
                "details": f"Services: {len(operations.get('services', []))}, Packages: {len(operations.get('packages', []))}"
            }
            
            # Step 4: LLM Analysis
            yield {
                "type": "progress", 
                "status": "analyzing",
                "message": "🧠 LlamaStack agent performing expert BladeLogic analysis",
                "progress": 0.6,
                "correlation_id": correlation_id
            }
            
            # Create new session for streaming
            analysis_session_id = self.create_new_session(correlation_id)
            
            yield {
                "type": "progress",
                "status": "llm_processing",
                "message": "🤖 Processing with BladeLogic expertise",
                "progress": 0.8,
                "correlation_id": correlation_id,
                "details": f"Session: {analysis_session_id[:8]}"
            }
            
            # Perform full analysis
            result = await self.analyze_bladelogic(bladelogic_data, correlation_id)
            
            # Step 5: Complete
            yield {
                "type": "progress",
                "status": "completing",
                "message": "📋 Finalizing BladeLogic analysis results",
                "progress": 0.95,
                "correlation_id": correlation_id
            }
            
            # Final result
            yield {
                "type": "final_analysis",
                "data": result,
                "correlation_id": correlation_id,
                "summary": {
                    "object_type": result.get("object_type"),
                    "automation_type": result.get("functionality", {}).get("automation_type"),
                    "migration_effort": result.get("version_requirements", {}).get("migration_effort"),
                    "total_operations": total_operations
                }
            }
            
        except Exception as e:
            yield {
                "type": "error",
                "error": str(e),
                "correlation_id": correlation_id,
                "object_name": object_name,
                "details": "BladeLogic analysis failed"
            }

    def get_status(self) -> Dict[str, Any]:
        """Get BladeLogic agent status"""
        return {
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "client_base_url": self.client.base_url,
            "timeout": self.timeout,
            "status": "ready",
            "approach": "bladelogic_expert_analysis",
            "supported_types": ["JOB", "PACKAGE", "POLICY", "SCRIPT", "COMPLIANCE_TEMPLATE"],
            "automation_types": ["COMPLIANCE", "PATCHING", "DEPLOYMENT", "CONFIGURATION", "MONITORING"],
            "capabilities": [
                "rscd_agent_analysis",
                "compliance_template_analysis", 
                "patch_workflow_analysis",
                "nsh_script_analysis",
                "blpackage_analysis",
                "job_flow_analysis",
                "migration_assessment",
                "ansible_conversion_guidance"
            ]
        }

    async def health_check(self) -> bool:
        """Health check for BladeLogic agent"""
        try:
            messages = [UserMessage(role="user", content="Health check - respond with 'BladeLogic Ready'")]
            generator = self.client.agents.turn.create(
                agent_id=self.agent_id,
                session_id=self.session_id,
                messages=messages,  
                stream=True,
            )
            for chunk in generator:
                break
            self.logger.info(" BladeLogic health check passed")
            return True
        except Exception as e:
            self.logger.error(f" BladeLogic health check failed: {e}")
            return False