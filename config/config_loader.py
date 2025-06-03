"""
Configuration loader with profile support.
Handles environment-specific configuration management.
"""
import yaml
import os
from pathlib import Path
from typing import Dict, Any, Optional


class ConfigLoader:
    """
    Profile-aware configuration loader.
    Supports environment-specific configurations with fallbacks.
    """
    
    def __init__(self, config_path: str = 'config.yaml'):
        self.config_path = Path(config_path)
        self._data: Optional[Dict[str, Any]] = None
        self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from YAML file."""
        try:
            if not self.config_path.exists():
                raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
            
            with self.config_path.open('r') as f:
                self._data = yaml.safe_load(f)
                
            if not self._data:
                raise ValueError("Configuration file is empty or invalid")
                
        except Exception as e:
            raise RuntimeError(f"Failed to load configuration: {str(e)}")
    
    def get_profile(self) -> Dict[str, Any]:
        """
        Get the active profile configuration.
        Returns the profile data based on active_profile setting.
        """
        if not self._data:
            return {}
        
        # Get active profile name (can be overridden by environment variable)
        profile_name = os.getenv('ACTIVE_PROFILE') or self._data.get("active_profile", "local")
        
        # Get profile configuration
        profiles = self._data.get("profiles", {})
        profile_config = profiles.get(profile_name, {})
        
        return profile_config
    
    def get_llamastack_base_url(self) -> Optional[str]:
        """
        Get LlamaStack base URL from profile or defaults.
        Supports environment variable substitution.
        """
        # Try profile first
        profile = self.get_profile()
        base_url = profile.get("llama_stack", {}).get("base_url")
        
        # Fall back to defaults
        if not base_url and self._data:
            base_url = self._data.get("defaults", {}).get("llama_stack", {}).get("base_url")
        
        # Handle environment variable substitution
        if base_url and base_url.startswith("${") and base_url.endswith("}"):
            env_var = base_url[2:-1]  # Remove ${ and }
            base_url = os.getenv(env_var)
        
        return base_url
    
    def get_llamastack_model(self) -> Optional[str]:
        """
        Get LlamaStack model from profile or defaults.
        """
        # Try profile first
        profile = self.get_profile()
        model = profile.get("llama_stack", {}).get("model")
        
        # Fall back to defaults
        if not model and self._data:
            model = self._data.get("defaults", {}).get("llama_stack", {}).get("model")
        
        return model
    
    def get_value(self, *keys, default=None) -> Any:
        """
        Get configuration value using dot notation.
        First tries profile, then falls back to defaults.
        
        Example:
            get_value("agents", "chef_analysis", "timeout", default=120)
        """
        if not self._data:
            return default
        
        # Try profile first
        profile = self.get_profile()
        value = self._get_nested_value(profile, keys)
        
        # Fall back to defaults
        if value is None:
            defaults = self._data.get("defaults", {})
            value = self._get_nested_value(defaults, keys)
        
        return value if value is not None else default
    
    def _get_nested_value(self, data: Dict[str, Any], keys: tuple) -> Any:
        """
        Get nested value from dictionary using key path.
        Returns None if any key in the path doesn't exist.
        """
        current = data
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        
        return current
    
    def reload(self) -> None:
        """
        Reload configuration from file.
        Useful for development or configuration updates.
        """
        self._load_config()
    
    def get_full_config(self) -> Dict[str, Any]:
        """
        Get the complete configuration data.
        Useful for debugging or advanced use cases.
        """
        return self._data or {}
    
    def validate_configuration(self) -> bool:
        """
        Validate essential configuration is present.
        Returns True if configuration is valid, False otherwise.
        """
        try:
            # Check essential configurations
            base_url = self.get_llamastack_base_url()
            model = self.get_llamastack_model()
            
            if not base_url:
                print("ERROR: LlamaStack base_url not configured")
                return False
            
            if not model:
                print("ERROR: LlamaStack model not configured")
                return False
            
            print(f"Configuration valid - Profile: {self.get_profile()}")
            print(f"Base URL: {base_url}")
            print(f"Model: {model}")
            
            return True
            
        except Exception as e:
            print(f"Configuration validation failed: {e}")
            return False