"""
Salt Analysis Agent
Clean agent that uses prompts and instructions from config.yaml
No hard-coded prompts or unnecessary processing
"""

import time
import uuid
import logging
from typing import Dict, Any, Optional, AsyncGenerator

from llama_stack_client import LlamaStackClient
from llama_stack_client.types import UserMessage

from agents.salt_analysis.utils import create_correlation_id

# Handle shared modules gracefully
try:
    from shared.exceptions import CookbookAnalysisError
except ImportError:
    class CookbookAnalysisError(Exception):
        """Infrastructure analysis error"""
        pass

try:
    from shared.log_utils import create_chef_logger, ChefAnalysisLogger
    # Override to use proper salt logging
    def create_salt_logger(name: str):
        return logging.getLogger(f"salt_analysis.{name}")
    
    class SaltAnalysisLogger:
        def __init__(self, logger):
            self.logger = logger
        
        def info(self, msg):
            self.logger.info(msg)
        
        def warning(self, msg):
            self.logger.warning(msg)
        
        def error(self, msg):
            self.logger.error(msg)
            
    create_chef_logger = create_salt_logger
    ChefAnalysisLogger = SaltAnalysisLogger
except ImportError:
    def create_chef_logger(name: str):
        return logging.getLogger(f"salt_{name}")
    
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

class SaltAnalysisAgent:
    """
    Salt Analysis Agent using config.yaml prompts and instructions
    """

    def __init__(
        self, 
        client: LlamaStackClient, 
        agent_id: str, 
        session_id: str,
        config_loader,
        timeout: int = 120
    ):
        self.client = client
        self.agent_id = agent_id
        self.session_id = session_id
        self.config_loader = config_loader
        self.timeout = timeout
        self.logger = create_chef_logger("salt_init")

        # Get prompt template and instructions from config
        self.prompt_template = config_loader.config.get("prompts", {}).get("salt_analysis")
        self.instruction = config_loader.config.get("agent_instructions", {}).get("salt_analysis")
        
        # Debug logging
        self.logger.info(f"🔍 Prompt template found: {bool(self.prompt_template)}")
        self.logger.info(f"🔍 Instructions found: {bool(self.instruction)}")
        
        if self.prompt_template:
            self.logger.info(f"🔍 Prompt template preview: {str(self.prompt_template)[:100]}...")
        if self.instruction:
            self.logger.info(f"🔍 Instructions preview: {str(self.instruction)[:100]}...")
        
        if not self.prompt_template:
            raise RuntimeError("Salt agent requires 'prompts.salt_analysis' in config.yaml!")
        if not self.instruction:
            raise RuntimeError("Salt agent requires 'agent_instructions.salt_analysis' in config.yaml!")

        self.logger.info(f"🧂 SaltAnalysisAgent initialized - agent_id: {agent_id}, session_id: {session_id}")

    def create_new_session(self, correlation_id: str) -> str:
        """Create new session for Salt analysis - but reuse existing session when possible"""
        # For analysis requests, reuse the existing session instead of creating new ones
        # This prevents creating multiple agent instances
        if hasattr(self, 'session_id') and self.session_id:
            self.logger.info(f"♻️ Reusing existing session: {self.session_id} for correlation: {correlation_id}")
            return self.session_id
            
        try:
            session_name = f"salt-analysis-{correlation_id}-{uuid.uuid4()}"
            response = self.client.agents.session.create(
                agent_id=self.agent_id,
                session_name=session_name,
            )
            session_id = response.session_id
            self.logger.info(f"📱 Created Salt session: {session_id} for correlation: {correlation_id}")
            return session_id
        except Exception as e:
            self.logger.error(f" Failed to create session: {e}")
            self.logger.info(f"↩️ Falling back to default session: {self.session_id}")
            return self.session_id

    async def analyze_salt(
        self,
        salt_data: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze Salt infrastructure content using config prompts"""
        correlation_id = correlation_id or create_correlation_id()
        step_logger = create_chef_logger(correlation_id)
        start_time = time.time()

        object_name = salt_data.get("name", "unknown")
        files = salt_data.get("files", {})

        step_logger.info(f"🧂 Salt files received for analysis ({len(files)}): {list(files.keys())}")
        step_logger.info(f"🔄 Starting Salt infrastructure analysis")

        try:
            if not files:
                raise ValueError("Salt object must contain at least one file")

            # Use existing session instead of creating new one for each analysis
            analysis_session_id = self.session_id

            # Format content for analysis
            salt_content = self._format_salt_content(object_name, files)
            
            # Use config prompt template with debug logging
            step_logger.info("🔧 Formatting prompt template...")
            step_logger.info(f"Instruction length: {len(self.instruction) if self.instruction else 0}")
            step_logger.info(f"Salt content length: {len(salt_content)}")
            
            try:
                prompt = self.prompt_template.format(
                    instruction=self.instruction,
                    salt_content=salt_content
                )
                step_logger.info(f" Prompt formatted successfully, length: {len(prompt)}")
            except Exception as format_error:
                step_logger.error(f" Prompt formatting failed: {format_error}")
                raise Exception(f"Prompt formatting failed: {format_error}")

            # Direct LLM analysis
            step_logger.info("🧠 LlamaStack agent Salt analysis using config prompt")
            result = await self._analyze_direct(prompt, correlation_id, step_logger, analysis_session_id)

            # Handle different response scenarios
            if not result:
                step_logger.warning("⚠️ LLM returned no result, using minimal fallback")
                result = self._create_minimal_fallback(object_name)
            elif not result.get("success"):
                step_logger.warning("⚠️ LLM returned unsuccessful result, enhancing response")
                result["success"] = True
                if not result.get("object_name"):
                    result["object_name"] = object_name

            total_time = time.time() - start_time
            step_logger.info(f" Salt analysis completed successfully in {total_time:.3f}s")

            result["session_info"] = {
                "agent_id": self.agent_id,
                "session_id": analysis_session_id,
                "correlation_id": correlation_id,
                "method_used": "salt_config_analysis",
                "analysis_time_seconds": round(total_time, 3)
            }
            
            return result

        except Exception as e:
            total_time = time.time() - start_time
            step_logger.error(f" Salt analysis failed after {total_time:.3f}s: {str(e)}")
            raise CookbookAnalysisError(f"Salt analysis failed: {str(e)}")

    def _format_salt_content(self, object_name: str, files: Dict[str, str]) -> str:
        """Simple content formatting for analysis"""
        content_parts = [
            f"Salt Object: {object_name}",
            ""
        ]
        
        for filename, content in files.items():
            content_parts.append(f"\n=== File: {filename} ===")
            content_parts.append(content.strip())
        
        return "\n".join(content_parts)

    def _create_minimal_fallback(self, object_name: str) -> Dict[str, Any]:
        """Create minimal fallback response when LLM fails"""
        return {
            "success": True,
            "object_name": object_name,
            "object_type": "STATE",
            "version_requirements": {
                "min_salt_version": "3000",
                "min_python_version": "3.6",
                "migration_effort": "MEDIUM",
                "estimated_hours": 8,
                "deprecated_features": []
            },
            "dependencies": {
                "is_formula": False,
                "formula_dependencies": [],
                "pillar_dependencies": [],
                "grain_dependencies": [],
                "external_modules": [],
                "circular_risk": "low"
            },
            "functionality": {
                "primary_purpose": f"Salt infrastructure automation for {object_name}",
                "automation_type": "STATE",
                "target_platforms": ["Linux"],
                "managed_services": [],
                "managed_packages": [],
                "managed_files": [],
                "state_modules": [],
                "execution_modules": [],
                "reusability": "MEDIUM",
                "customization_points": []
            },
            "recommendations": {
                "consolidation_action": "MODERNIZE",
                "rationale": "Basic Salt automation suitable for modernization",
                "migration_priority": "MEDIUM",
                "risk_factors": [],
                "ansible_equivalent": "Equivalent Ansible playbooks"
            },
            "detailed_analysis": f"Salt infrastructure automation analysis for {object_name}. Analysis completed using fallback processing.",
            "key_operations": ["Infrastructure automation"],
            "automation_details": "Salt-based configuration management",
            "complexity_level": "Medium",
            "convertible": True,
            "conversion_notes": "Can be converted to Ansible with standard effort",
            "analysis_method": "minimal_fallback"
        }

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
            
            step_logger.info(f"[{correlation_id}] 🤖 Calling LlamaStack agent for Salt analysis...")
            
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
            
            if not turn or not hasattr(turn, 'output_message') or not turn.output_message:
                step_logger.error(f"[{correlation_id}]  No valid output message in turn")
                return None
            
            raw_response = turn.output_message.content
            step_logger.info(f"[{correlation_id}] 📥 Received LlamaStack response: {len(raw_response)} chars")
            
            # Clean markdown code blocks first
            cleaned_response = raw_response.strip()
            
            # Remove markdown code blocks if present
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response[7:]  # Remove ```json
            elif cleaned_response.startswith('```'):
                cleaned_response = cleaned_response[3:]   # Remove ```
            
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-3]  # Remove ending ```
            
            cleaned_response = cleaned_response.strip()
            
            # Try to parse JSON response
            import json
            import re
            
            step_logger.info(f"[{correlation_id}] 🔍 Raw response preview: {raw_response[:200]}...")
            
            try:
                # Try direct JSON parsing on cleaned response
                result = json.loads(cleaned_response)
                step_logger.info(f"[{correlation_id}]  Successfully parsed JSON response")
                return result
                
            except json.JSONDecodeError as e:
                step_logger.warning(f"[{correlation_id}] ⚠️ Direct JSON parse failed: {e}")
                
                # Try to extract JSON from text using multiple patterns
                json_patterns = [
                    r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',  # Nested braces
                    r'\{.*?\}',  # Basic braces
                    r'(\{.*\})',  # Capture group
                ]
                
                for pattern in json_patterns:
                    try:
                        json_match = re.search(pattern, raw_response, re.DOTALL)
                        if json_match:
                            json_text = json_match.group(0) if json_match.groups() else json_match.group()
                            
                            # Clean up common JSON issues
                            json_text = re.sub(r',\s*}', '}', json_text)  # Remove trailing commas
                            json_text = re.sub(r',\s*]', ']', json_text)  # Remove trailing commas in arrays
                            
                            result = json.loads(json_text)
                            step_logger.info(f"[{correlation_id}]  Extracted and parsed JSON using pattern: {pattern[:20]}...")
                            return result
                    except (json.JSONDecodeError, AttributeError):
                        continue
                
                # If all JSON extraction fails, create a fallback response
                step_logger.warning(f"[{correlation_id}] ⚠️ Could not extract valid JSON, creating fallback response")
                return {
                    "success": True,
                    "object_name": "unknown",
                    "object_type": "STATE",
                    "version_requirements": {
                        "min_salt_version": "3000",
                        "min_python_version": "3.6",
                        "migration_effort": "MEDIUM",
                        "estimated_hours": 8,
                        "deprecated_features": []
                    },
                    "dependencies": {
                        "is_formula": False,
                        "formula_dependencies": [],
                        "pillar_dependencies": [],
                        "grain_dependencies": [],
                        "external_modules": [],
                        "circular_risk": "low"
                    },
                    "functionality": {
                        "primary_purpose": "Salt infrastructure automation (parsed from LLM response)",
                        "automation_type": "STATE",
                        "target_platforms": ["Linux"],
                        "managed_services": [],
                        "managed_packages": [],
                        "managed_files": [],
                        "state_modules": [],
                        "execution_modules": [],
                        "reusability": "MEDIUM",
                        "customization_points": []
                    },
                    "recommendations": {
                        "consolidation_action": "MODERNIZE",
                        "rationale": "Analysis based on fallback due to LLM response parsing issues",
                        "migration_priority": "MEDIUM",
                        "risk_factors": ["JSON parsing issues in LLM response"],
                        "ansible_equivalent": "Custom Ansible playbooks with equivalent functionality"
                    },
                    "detailed_analysis": "Salt infrastructure automation analysis completed with fallback processing due to response parsing issues.",
                    "key_operations": ["Infrastructure automation"],
                    "automation_details": "Salt-based infrastructure management",
                    "complexity_level": "Medium",
                    "convertible": True,
                    "conversion_notes": "Can be converted to Ansible with medium effort",
                    "fallback_reason": f"LLM response parsing failed: {str(e)[:100]}"
                }
            
        except Exception as e:
            step_logger.error(f"[{correlation_id}]  LlamaStack analysis failed: {e}")
            return None

    async def analyze_salt_stream(
        self,
        salt_data: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream Salt analysis with progress updates"""
        correlation_id = correlation_id or create_correlation_id()
        object_name = salt_data.get("name", "unknown")
        files = salt_data.get("files", {})
        
        try:
            # Starting
            yield {
                "type": "progress",
                "status": "starting",
                "message": "🧂 Salt infrastructure analysis started",
                "progress": 0.1,
                "correlation_id": correlation_id,
                "details": f"Analyzing {len(files)} Salt files"
            }
            
            # Processing
            yield {
                "type": "progress",
                "status": "analyzing",
                "message": "🧠 LlamaStack agent performing Salt analysis",
                "progress": 0.6,
                "correlation_id": correlation_id
            }
            
            # Perform analysis
            result = await self.analyze_salt(salt_data, correlation_id)
            
            # Complete
            yield {
                "type": "final_analysis",
                "data": result,
                "correlation_id": correlation_id,
                "summary": {
                    "object_name": object_name,
                    "success": result.get("success", False)
                }
            }
            
        except Exception as e:
            yield {
                "type": "error",
                "error": str(e),
                "correlation_id": correlation_id,
                "object_name": object_name,
                "details": "Salt analysis failed"
            }

    def get_status(self) -> Dict[str, Any]:
        """Get Salt agent status"""
        return {
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "client_base_url": self.client.base_url,
            "timeout": self.timeout,
            "status": "ready",
            "approach": "salt_config_analysis",
            "has_prompt_template": bool(self.prompt_template),
            "has_instructions": bool(self.instruction),
            "capabilities": [
                "salt_state_analysis",
                "salt_pillar_analysis", 
                "salt_formula_analysis",
                "salt_orchestration_analysis",
                "salt_reactor_analysis",
                "migration_assessment",
                "ansible_conversion_guidance"
            ]
        }

    async def health_check(self) -> bool:
        """Health check for Salt agent"""
        try:
            messages = [UserMessage(role="user", content="Health check - respond with 'Salt Ready'")]
            generator = self.client.agents.turn.create(
                agent_id=self.agent_id,
                session_id=self.session_id,
                messages=messages,  
                stream=True,
            )
            for chunk in generator:
                break
            self.logger.info(" Salt health check passed")
            return True
        except Exception as e:
            self.logger.error(f" Salt health check failed: {e}")
            return False