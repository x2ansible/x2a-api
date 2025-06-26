# agents/ansible_upgrade/agent.py - CLEAN ReAct Agent (Config Driven)

import logging
import json
import uuid
from typing import Dict, Any, Optional, AsyncGenerator
from datetime import datetime

from llama_stack_client import LlamaStackClient
from llama_stack_client.lib.agents.react.agent import ReActAgent

# Import the processor for robust JSON handling
from .processor import extract_and_validate_analysis

logger = logging.getLogger(__name__)

class AnsibleUpgradeAnalysisAgent:
    def __init__(
        self,
        client: LlamaStackClient,
        config_loader,
        agent_name: str = "ansible_upgrade_analysis"
    ):
        self.client = client
        self.config_loader = config_loader
        self.agent_name = agent_name

        # Get agent config exactly like SyncAI
        self.agent_cfg = self._get_agent_config(agent_name)
        self.model = self.agent_cfg.get("model", "granite32-8b")
        self.instructions = self.agent_cfg.get("instructions", "")
        self.tools = self.agent_cfg.get("tools", [])
        self.sampling_params = self.agent_cfg.get("sampling_params", {
            "strategy": {"type": "greedy"},
            "max_tokens": 4096
        })
        self.max_infer_iters = self.agent_cfg.get("max_infer_iters", 1)

        # Initialize ReAct agent with config-driven approach
        self._init_react_agent()
        logger.info(f"🔄 Ansible ReAct agent initialized: {self.agent_name}")

    def _get_agent_config(self, agent_name: str) -> Dict[str, Any]:
        agents_config = self.config_loader.get_agents_config()
        for agent in agents_config:
            if agent.get("name") == agent_name:
                return agent
        raise ValueError(f"No agent configuration found for {agent_name}")

    def _init_react_agent(self):
        try:
            # Use instructions directly from config - no modifications
            self.react_agent = ReActAgent(
                client=self.client,
                model=self.model,
                tools=self.tools,
                instructions=self.instructions,  # Pure config instructions
                sampling_params=self.sampling_params,
                max_infer_iters=self.max_infer_iters
            )
            logger.info("🔄 ReAct agent initialized successfully")
        except Exception as e:
            logger.error(f" Failed to initialize ReAct agent: {e}")
            raise

    async def analyze_ansible_upgrade(
        self, 
        ansible_data: Dict[str, Any], 
        correlation_id: str
    ) -> Dict[str, Any]:
        try:
            content = ansible_data.get("content", "")
            filename = ansible_data.get("filename", "playbook.yml")
            
            if not content.strip():
                return self._create_error_response("No Ansible content provided", filename, correlation_id)
            
            # Get and format prompt exactly from config
            prompt_template = self.config_loader.config.get("prompts", {}).get("ansible_upgrade_analysis", "")
            
            # Format prompt using config template
            formatted_prompt = prompt_template.format(
                instruction=self.instructions,
                ansible_content=content
            )
            
            # Use ReAct agent exactly like SyncAI
            session_id = self.react_agent.create_session(f"{self.agent_name}-{correlation_id}")
            
            response = self.react_agent.create_turn(
                messages=[{"role": "user", "content": formatted_prompt}],
                session_id=session_id,
                stream=False
            )
            
            # Extract response content
            response_content = getattr(response.output_message, 'content', '') if hasattr(response, 'output_message') else ""
            logger.info(f"Raw response length: {len(response_content)}")
            logger.info(f"Raw response preview: {response_content[:300]}...")
            
            # Handle ReAct response - check if it's already proper JSON
            if isinstance(response_content, str):
                try:
                    # Try direct JSON parsing (in case agent returns pure JSON)
                    parsed_json = json.loads(response_content.strip())
                    if isinstance(parsed_json, dict) and parsed_json.get("success") is not None:
                        parsed_json["filename"] = filename
                        if "session_info" not in parsed_json:
                            parsed_json["session_info"] = {
                                "correlation_id": correlation_id, 
                                "timestamp": datetime.now().isoformat()
                            }
                        # --- PATCH: Add top-level upgrade block if needed ---
                        if parsed_json.get("analysis_type") == "ansible_upgrade_assessment":
                            upgrade_requirements = parsed_json.get("upgrade_requirements", {})
                            breaking_changes = (
                                upgrade_requirements.get("structural_changes_needed", [])
                                if isinstance(upgrade_requirements, dict)
                                else []
                            )
                            current_version = parsed_json.get("current_state", {}).get("estimated_version", "Unknown")
                            # --- NON-HARDCODED: get recommended version from model or fallback ---
                            recommended_version = (
                                parsed_json.get("recommended_ansible_version")
                                or parsed_json.get("recommendations", {}).get("recommended_ansible_version")
                                or "2.15"
                            )
                            parsed_json["upgrade"] = {
                                "breakingChangesCount": len(breaking_changes),
                                "currentVersion": current_version,
                                "recommendedVersion": recommended_version,
                            }
                        # --- END PATCH ---
                        logger.info(f" Direct JSON parsing successful")
                        return parsed_json
                except json.JSONDecodeError:
                    # Not pure JSON, continue to processor
                    pass
            
            # Process response using the robust processor
            processed_result = extract_and_validate_analysis(
                raw_response=response_content,
                correlation_id=correlation_id,
                ansible_content=content
            )
            
            # Ensure required fields are set
            processed_result["filename"] = filename
            if "session_info" not in processed_result:
                processed_result["session_info"] = {
                    "correlation_id": correlation_id, 
                    "timestamp": datetime.now().isoformat()
                }
            # --- PATCH: Add top-level upgrade block if needed ---
            if processed_result.get("analysis_type") == "ansible_upgrade_assessment":
                upgrade_requirements = processed_result.get("upgrade_requirements", {})
                breaking_changes = (
                    upgrade_requirements.get("structural_changes_needed", [])
                    if isinstance(upgrade_requirements, dict)
                    else []
                )
                current_version = processed_result.get("current_state", {}).get("estimated_version", "Unknown")
                # --- NON-HARDCODED: get recommended version from model or fallback ---
                recommended_version = (
                    processed_result.get("recommended_ansible_version")
                    or processed_result.get("recommendations", {}).get("recommended_ansible_version")
                    or "2.15"
                )
                processed_result["upgrade"] = {
                    "breakingChangesCount": len(breaking_changes),
                    "currentVersion": current_version,
                    "recommendedVersion": recommended_version,
                }
            # --- END PATCH ---

            logger.info(f"Processed result success: {processed_result.get('success')}")
            return processed_result
            
        except Exception as e:
            logger.error(f" Analysis failed: {e}")
            return self._create_error_response(str(e), ansible_data.get("filename", "unknown.yml"), correlation_id)

    def _create_error_response(self, error: str, filename: str, correlation_id: str) -> Dict[str, Any]:
        """Create standardized error response"""
        return {
            "success": False,
            "error": error,
            "filename": filename,
            "analysis_type": "ansible_upgrade_assessment",
            "current_state": {},
            "upgrade_requirements": {},
            "complexity_assessment": {},
            "recommendations": {},
            "session_info": {"correlation_id": correlation_id, "timestamp": datetime.now().isoformat()}
        }

    async def analyze_stream(self, ansible_data: Dict[str, Any], correlation_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        yield {"type": "start", "message": "Starting Ansible upgrade analysis", "correlation_id": correlation_id}
        
        try:
            result = await self.analyze_ansible_upgrade(ansible_data, correlation_id)
            yield {"type": "final_result", "data": result, "correlation_id": correlation_id}
        except Exception as e:
            yield {"type": "error", "error": str(e), "correlation_id": correlation_id}

    async def health_check(self) -> bool:
        try:
            session_id = self.react_agent.create_session(f"health-{uuid.uuid4().hex[:8]}")
            response = self.react_agent.create_turn(
                messages=[{"role": "user", "content": "Respond with JSON: {\"status\": \"healthy\"}"}],
                session_id=session_id,
                stream=False
            )
            content = getattr(response.output_message, 'content', '').lower() if hasattr(response, 'output_message') else ""
            return "healthy" in content
        except:
            return False

    def get_status(self) -> Dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "model": self.model,
            "tools": self.tools,
            "status": "ready",
            "pattern": "ReAct (Config Driven)",
            "timestamp": datetime.now().isoformat()
        }
