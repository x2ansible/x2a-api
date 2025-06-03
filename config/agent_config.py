"""
Agent configuration and instruction management.
Loads agent instructions from configuration files.
"""
import logging
from typing import Dict, Any
from pathlib import Path
import yaml

logger = logging.getLogger(__name__)


class AgentInstructionLoader:
    """Loads and manages agent instructions from configuration."""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = Path(config_path)
        self._instructions_cache: Dict[str, str] = {}
    
    def get_agent_instructions(self, agent_name: str) -> str:
        """
        Get instructions for specified agent.
        Caches instructions for performance.
        """
        if agent_name in self._instructions_cache:
            return self._instructions_cache[agent_name]
        
        try:
            with self.config_path.open('r') as f:
                config = yaml.safe_load(f)
            
            instructions = (
                config.get("agent_instructions", {})
                .get(agent_name, "")
            )
            
            if not instructions:
                logger.warning(f"No instructions found for agent: {agent_name}")
                return self._get_default_instructions(agent_name)
            
            self._instructions_cache[agent_name] = instructions
            return instructions
            
        except Exception as e:
            logger.error(f"Failed to load instructions for {agent_name}: {e}")
            return self._get_default_instructions(agent_name)
    
    def _get_default_instructions(self, agent_name: str) -> str:
        """Fallback instructions if config loading fails."""
        if agent_name == "chef_analysis":
            return """You are a Chef cookbook analyzer. Analyze the provided Chef cookbook and return JSON analysis.

Task: Analyze Chef cookbook code and return structured analysis.

Steps:
1. Identify Chef and Ruby version requirements
2. Map dependencies and wrapper patterns  
3. Assess functionality for reuse decisions

Output Format:
Return only valid JSON with this exact structure:
{
  "version_requirements": {
    "min_chef_version": "version or null",
    "min_ruby_version": "version or null", 
    "migration_effort": "LOW|MEDIUM|HIGH",
    "deprecated_features": ["list of deprecated features used"]
  },
  "dependencies": {
    "is_wrapper": true/false,
    "wrapped_cookbooks": ["list of cookbooks this wraps"],
    "direct_deps": ["list of direct dependencies"],
    "circular_risk": "none|low|medium|high"
  },
  "functionality": {
    "primary_purpose": "brief description",
    "services": ["list of services managed"],
    "packages": ["list of packages installed"],
    "reusability": "LOW|MEDIUM|HIGH"
  },
  "recommendations": {
    "consolidation_action": "REUSE|EXTEND|RECREATE",
    "rationale": "explanation of recommendation"
  }
}

Rules:
- Return only valid JSON, no other text
- Use null for unknown values
- Be specific about version requirements
- Identify wrapper patterns through include_recipe analysis"""
        
        return f"You are a {agent_name} agent. Analyze the provided input and return structured results."
    
    def reload_instructions(self) -> None:
        """Clear instruction cache to force reload on next access."""
        self._instructions_cache.clear()
        logger.info("Agent instruction cache cleared")


# Global instance for easy access
_instruction_loader = AgentInstructionLoader()


def get_agent_instructions(agent_name: str) -> str:
    """Get instructions for the specified agent."""
    return _instruction_loader.get_agent_instructions(agent_name)


def reload_agent_instructions() -> None:
    """Reload all agent instructions from config."""
    _instruction_loader.reload_instructions()