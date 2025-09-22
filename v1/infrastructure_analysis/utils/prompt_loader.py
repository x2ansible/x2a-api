"""
Prompt Loading Utility

Centralized prompt management from configuration file.
Ensures all agent prompts are consistent and maintainable.
"""

import yaml
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional


class PromptLoader:
    """
    Centralized prompt loader for infrastructure analysis system.
    Loads prompts from YAML configuration file.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize prompt loader with configuration file.
        
        Args:
            config_path: Path to prompts configuration file
        """
        if config_path is None:
            # Default to config.yaml in v1 folder
            config_path = Path(__file__).parent.parent.parent / "config.yaml"
        
        self.config_path = Path(config_path)
        self._prompts_cache = None
        # Don't load prompts in __init__ to avoid blocking I/O
    
    def _load_prompts(self) -> None:
        """Load prompts from configuration file synchronously (fallback only)."""
        if self._prompts_cache is not None:
            return
            
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                # Extract only the prompts section
                self._prompts_cache = config.get('prompts', {})
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in configuration: {e}")
    
    async def _load_prompts_async(self) -> None:
        """Load prompts from configuration file asynchronously."""
        if self._prompts_cache is not None:
            return
            
        try:
            # Use asyncio.to_thread for non-blocking file I/O
            def _read_config():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f)
            
            config = await asyncio.to_thread(_read_config)
            # Extract only the prompts section
            self._prompts_cache = config.get('prompts', {})
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in configuration: {e}")
    
    async def _ensure_prompts_loaded(self) -> None:
        """Ensure prompts are loaded, preferring async method."""
        if self._prompts_cache is not None:
            return
        
        try:
            # Check if we're in an async context
            loop = asyncio.get_running_loop()
            if loop:
                await self._load_prompts_async()
            else:
                self._load_prompts()
        except RuntimeError:
            # No event loop running, use sync fallback
            self._load_prompts()
    
    def get_prompt(self, category: str, prompt_type: str, **kwargs) -> str:
        """
        Get a prompt from configuration with variable substitution.
        
        Args:
            category: Prompt category (e.g., 'orchestrator_agent', 'workers')
            prompt_type: Type of prompt (e.g., 'system_prompt', 'analysis_prompt')
            **kwargs: Variables to substitute in the prompt template
            
        Returns:
            Formatted prompt string
            
        Raises:
            KeyError: If prompt not found in configuration
        """
        # Ensure prompts are loaded (sync fallback for compatibility)
        if self._prompts_cache is None:
            self._load_prompts()
            
        try:
            if category == "workers":
                # For workers, need worker_name as additional parameter
                worker_name = kwargs.pop('worker_name', None)
                if worker_name is None:
                    raise ValueError("worker_name required for worker prompts")
                prompt_template = self._prompts_cache[category][worker_name][prompt_type]
            else:
                prompt_template = self._prompts_cache[category][prompt_type]
            
            # Format template with provided variables
            return prompt_template.format(**kwargs)
            
        except KeyError as e:
            raise KeyError(f"Prompt not found: {category}.{prompt_type} - {e}")
        except KeyError as e:
            raise ValueError(f"Missing variable in prompt template: {e}")
    
    def get_tool_prompt(self, tool_name: str, **kwargs) -> str:
        """
        Get a tool prompt with variable substitution.
        
        Args:
            tool_name: Name of the tool
            **kwargs: Variables to substitute in the prompt template
            
        Returns:
            Formatted tool prompt string
        """
        return self.get_prompt("tools", tool_name, **kwargs)
    
    def get_orchestrator_prompt(self, prompt_type: str, **kwargs) -> str:
        """Get orchestrator agent prompt."""
        return self.get_prompt("orchestrator_agent", prompt_type, **kwargs)
    
    async def get_orchestrator_prompt_async(self, prompt_type: str, **kwargs) -> str:
        """Get orchestrator agent prompt asynchronously."""
        await self._ensure_prompts_loaded()
        return self.get_prompt("orchestrator_agent", prompt_type, **kwargs)
    
    def get_worker_prompt(self, worker_name: str, prompt_type: str, **kwargs) -> str:
        """Get worker agent prompt."""
        return self.get_prompt("workers", prompt_type, worker_name=worker_name, **kwargs)
    
    def get_synthesizer_prompt(self, prompt_type: str, **kwargs) -> str:
        """Get synthesizer agent prompt."""
        return self.get_prompt("synthesizer_agent", prompt_type, **kwargs)
    
    def reload_prompts(self) -> None:
        """Reload prompts from configuration file."""
        self._load_prompts()
    
    def list_available_prompts(self) -> Dict[str, Any]:
        """Get structure of available prompts."""
        def extract_keys(obj, path=""):
            if isinstance(obj, dict):
                result = {}
                for key, value in obj.items():
                    current_path = f"{path}.{key}" if path else key
                    if isinstance(value, dict):
                        result[key] = extract_keys(value, current_path)
                    else:
                        result[key] = f"prompt_available_at_{current_path}"
                return result
            return "prompt_string"
        
        return extract_keys(self._prompts_cache)


# Global prompt loader instance
_prompt_loader = None

def get_prompt_loader() -> PromptLoader:
    """Get global prompt loader instance."""
    global _prompt_loader
    if _prompt_loader is None:
        _prompt_loader = PromptLoader()
    return _prompt_loader

def get_prompt(category: str, prompt_type: str, **kwargs) -> str:
    """Convenience function to get prompt."""
    return get_prompt_loader().get_prompt(category, prompt_type, **kwargs)

def get_orchestrator_prompt(prompt_type: str, **kwargs) -> str:
    """Convenience function to get orchestrator prompt."""
    return get_prompt_loader().get_orchestrator_prompt(prompt_type, **kwargs)

async def get_orchestrator_prompt_async(prompt_type: str, **kwargs) -> str:
    """Convenience function to get orchestrator prompt asynchronously."""
    return await get_prompt_loader().get_orchestrator_prompt_async(prompt_type, **kwargs)

def get_worker_prompt(worker_name: str, prompt_type: str, **kwargs) -> str:
    """Convenience function to get worker prompt."""
    return get_prompt_loader().get_worker_prompt(worker_name, prompt_type, **kwargs)

def get_synthesizer_prompt(prompt_type: str, **kwargs) -> str:
    """Convenience function to get synthesizer prompt."""
    return get_prompt_loader().get_synthesizer_prompt(prompt_type, **kwargs)

def get_tool_prompt(tool_name: str, **kwargs) -> str:
    """Convenience function to get tool prompt."""
    return get_prompt_loader().get_tool_prompt(tool_name, **kwargs)
