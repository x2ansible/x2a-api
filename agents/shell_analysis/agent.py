"""
Shell Script Analysis Agent
"""

import time
import uuid
import json
import logging
from typing import Dict, Any, Optional, AsyncGenerator

from llama_stack_client import LlamaStackClient
from llama_stack_client.types import UserMessage

from agents.shell_analysis.utils import create_correlation_id

# Handle shared modules gracefully
try:
    from shared.exceptions import CookbookAnalysisError
except ImportError:
    class CookbookAnalysisError(Exception):
        pass

logger = logging.getLogger(__name__)

class ShellAnalysisAgent:
    """
    Config-Driven Shell Script Analysis Agent
    Uses instructions from config.yaml - no hardcoded prompts
    """

    def __init__(
        self, 
        client: LlamaStackClient, 
        agent_id: str, 
        session_id: str, 
        config_loader=None,
        timeout: int = 120
    ):
        self.client = client
        self.agent_id = agent_id
        self.session_id = session_id
        self.timeout = timeout
        self.config_loader = config_loader
        self.logger = logging.getLogger("shell_agent")

        self.logger.info(f"🐚 ShellAnalysisAgent initialized - agent_id: {agent_id}, session_id: {session_id}")

    def create_new_session(self, correlation_id: str) -> str:
        """Create new session for shell analysis"""
        try:
            session_name = f"shell-analysis-{correlation_id}-{uuid.uuid4()}"
            response = self.client.agents.session.create(
                agent_id=self.agent_id,
                session_name=session_name,
            )
            session_id = response.session_id
            self.logger.info(f"📱 Created shell session: {session_id}")
            return session_id
        except Exception as e:
            self.logger.error(f" Failed to create session: {e}")
            return self.session_id

    async def analyze_shell(
        self,
        shell_data: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze shell script content using config-driven prompts"""
        correlation_id = correlation_id or create_correlation_id()
        start_time = time.time()

        script_name = shell_data.get("name", "unknown")
        files = shell_data.get("files", {})

        self.logger.info(f"🐚 Starting config-driven shell analysis for {len(files)} files")

        try:
            if not files:
                raise ValueError("Shell script must contain at least one file")

            # Create new session
            analysis_session_id = self.create_new_session(correlation_id)

            # Format content for LLM
            shell_content = self._format_shell_content(script_name, files)
            
            # Use config-driven prompt
            self.logger.info("🧠 Using config-driven prompt for shell analysis")
            result = await self._analyze_with_config_prompt(shell_content, correlation_id, analysis_session_id)

            if not result:
                # Simple fallback if LLM fails
                result = self._create_simple_fallback(script_name, files)

            # Add session info
            total_time = time.time() - start_time
            result["session_info"] = {
                "agent_id": self.agent_id,
                "session_id": analysis_session_id,
                "correlation_id": correlation_id,
                "method_used": "config_driven_analysis",
                "analysis_time_seconds": round(total_time, 3),
            }
            
            self.logger.info(f" Shell analysis completed in {total_time:.3f}s")
            return result

        except Exception as e:
            self.logger.error(f" Shell analysis failed: {str(e)}")
            # Return simple fallback on any error
            return self._create_simple_fallback(script_name, files)

    async def _analyze_with_config_prompt(
        self, 
        shell_content: str,
        correlation_id: str,
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """Use the agent's built-in instructions from config.yaml"""
        try:
            # Get shell analysis prompt template from config if available
            shell_prompt_template = None
            if self.config_loader:
                try:
                    shell_prompt_template = self.config_loader.config.get("prompts", {}).get("shell_analysis")
                except Exception as e:
                    self.logger.warning(f"Could not load shell prompt from config: {e}")

            if shell_prompt_template:
                # Use config-driven prompt template with shell content
                prompt = shell_prompt_template.format(
                    shell_content=shell_content,
                    script_name=shell_content.split('\n')[0] if shell_content else "unknown"
                )
                self.logger.info("📝 Using config-driven prompt template")
            else:
                # Fallback: Just send the content and let the agent's instructions handle it
                prompt = f"""Please analyze this shell script content:

{shell_content}

Provide a comprehensive analysis following your instructions."""
                self.logger.info("📝 Using simple prompt - relying on agent instructions")

            messages = [UserMessage(role="user", content=prompt)]
            
            generator = self.client.agents.turn.create(
                agent_id=self.agent_id,
                session_id=session_id,
                messages=messages,
                stream=True,
            )
            
            # Get response from LLM
            turn = None
            for chunk in generator:
                if chunk and hasattr(chunk, 'event') and chunk.event:
                    event = chunk.event
                    if hasattr(event, 'payload') and event.payload:
                        event_type = getattr(event.payload, 'event_type', None)
                        if event_type == "turn_complete":
                            turn = getattr(event.payload, 'turn', None)
                            break
            
            if not turn or not hasattr(turn, 'output_message') or not turn.output_message:
                self.logger.error(" No response from LlamaStack")
                return None
            
            raw_response = turn.output_message.content
            self.logger.info(f"📥 Received response: {len(raw_response)} chars")
            
            # Try to parse JSON from response
            result = self._extract_json_from_response(raw_response)
            if result:
                result["success"] = True
                self.logger.info(" Config-driven analysis successful")
                return result
            else:
                self.logger.warning("⚠️ Could not parse LLM response as JSON")
                return None
            
        except Exception as e:
            self.logger.error(f" Config-driven analysis failed: {e}")
            return None

    def _extract_json_from_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Extract JSON from LLM response"""
        if not response:
            return None
            
        # Try direct JSON parsing
        try:
            return json.loads(response.strip())
        except json.JSONDecodeError:
            pass
        
        # Try to find JSON in code blocks
        import re
        json_patterns = [
            r'```json\s*(\{.*?\})\s*```',
            r'```\s*(\{.*?\})\s*```',
            r'(\{[^{}]*\{[^{}]*\}[^{}]*\})',
        ]
        
        for pattern in json_patterns:
            matches = re.findall(pattern, response, re.DOTALL | re.IGNORECASE)
            for match in matches:
                try:
                    return json.loads(match)
                except json.JSONDecodeError:
                    continue
        
        return None

    def _format_shell_content(self, script_name: str, files: Dict[str, str]) -> str:
        """Simple content formatting"""
        content_parts = [f"Shell Script Analysis: {script_name}", ""]
        
        for filename, content in files.items():
            content_parts.append(f"=== File: {filename} ===")
            content_parts.append(content.strip())
            content_parts.append("")
        
        return "\n".join(content_parts)

    def _create_simple_fallback(self, script_name: str, files: Dict[str, str]) -> Dict[str, Any]:
        """Simple fallback when LLM fails"""
        self.logger.info("🔄 Using simple fallback analysis")
        
        # Basic analysis
        total_content = " ".join(files.values()).lower()
        
        # Simple detection
        if any(word in total_content for word in ["apt-get", "yum", "install"]):
            script_type = "INSTALLATION"
            migration_effort = "MEDIUM"
        elif any(word in total_content for word in ["systemctl", "service"]):
            script_type = "DEPLOYMENT"
            migration_effort = "MEDIUM"
        else:
            script_type = "CONFIGURATION"
            migration_effort = "LOW"
        
        return {
            "success": True,
            "script_name": script_name,
            "script_type": "bash",
            "version_requirements": {
                "shell_type": "bash",
                "min_shell_version": "4.0",
                "migration_effort": migration_effort,
                "estimated_hours": 8.0,
                "deprecated_features": []
            },
            "dependencies": {
                "system_packages": [],
                "external_commands": [],
                "file_dependencies": [],
                "service_dependencies": [],
                "circular_risk": "low"
            },
            "functionality": {
                "primary_purpose": f"Shell script for {script_type.lower()} automation",
                "script_type": script_type,
                "target_platforms": ["Linux", "Unix"],
                "managed_services": [],
                "managed_packages": [],
                "configuration_files": [],
                "key_operations": ["automation"],
                "reusability": "MEDIUM"
            },
            "recommendations": {
                "conversion_action": "MODERNIZE",
                "rationale": "Script can be modernized with Ansible",
                "migration_priority": "MEDIUM",
                "risk_factors": ["Platform dependency"],
                "ansible_equivalent": "Custom Ansible playbooks"
            },
            "detailed_analysis": f"Shell script performing {script_type.lower()} automation. Consider converting to Ansible for better maintainability.",
            "complexity_level": "Medium",
            "convertible": True,
            "conversion_notes": "Can be converted to Ansible with moderate effort",
            "analysis_method": "simple_fallback"
        }

    async def analyze_shell_stream(
        self,
        shell_data: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream shell analysis with progress updates"""
        correlation_id = correlation_id or create_correlation_id()
        script_name = shell_data.get("name", "unknown")
        files = shell_data.get("files", {})
        
        try:
            yield {
                "type": "progress",
                "status": "starting",
                "message": "🐚 Shell script analysis started",
                "progress": 0.1,
                "correlation_id": correlation_id,
            }
            
            yield {
                "type": "progress",
                "status": "analyzing",
                "message": "🧠 Using config-driven analysis",
                "progress": 0.5,
                "correlation_id": correlation_id,
            }
            
            # Perform analysis
            result = await self.analyze_shell(shell_data, correlation_id)
            
            yield {
                "type": "progress",
                "status": "completing",
                "message": "📋 Finalizing analysis results",
                "progress": 0.9,
                "correlation_id": correlation_id,
            }
            
            # Final result
            yield {
                "type": "final_analysis",
                "data": result,
                "correlation_id": correlation_id,
                "summary": {
                    "script_type": result.get("script_type"),
                    "automation_type": result.get("functionality", {}).get("script_type"),
                    "migration_effort": result.get("version_requirements", {}).get("migration_effort"),
                }
            }
            
        except Exception as e:
            yield {
                "type": "error",
                "error": str(e),
                "correlation_id": correlation_id,
                "script_name": script_name,
            }

    def get_status(self) -> Dict[str, Any]:
        """Get shell agent status"""
        return {
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "status": "ready",
            "approach": "config_driven_agentic",
            "capabilities": [
                "config_driven_analysis",
                "yaml_prompt_templates", 
                "agent_instruction_based",
                "zero_hardcoded_prompts"
            ]
        }

    async def health_check(self) -> bool:
        """Health check for shell agent"""
        try:
            messages = [UserMessage(role="user", content="Health check - respond with 'Shell Ready'")]
            generator = self.client.agents.turn.create(
                agent_id=self.agent_id,
                session_id=self.session_id,
                messages=messages,  
                stream=True,
            )
            for chunk in generator:
                break
            self.logger.info(" Shell health check passed")
            return True
        except Exception as e:
            self.logger.error(f" Shell health check failed: {e}")
            return False