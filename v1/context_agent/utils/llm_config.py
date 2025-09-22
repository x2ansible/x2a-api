"""
LLM Configuration for Context Agent

Centralized LLM setup and configuration management.
"""

import yaml
from pathlib import Path
from langchain_openai import ChatOpenAI


def _load_config_sync():
    """Load configuration synchronously"""
    config_path = Path(__file__).parent.parent.parent / "config.yaml"
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def get_llm():
    """Get production-grade LLM instance with timeout and retry configuration"""
    config = _load_config_sync()
    llm_config = config.get("llm", {})
    
    return ChatOpenAI(
        base_url=llm_config.get("base_url", "https://lss-lss.apps.prod.rhoai.rh-aiservices-bu.com/v1/openai/v1"),
        model=llm_config.get("model", "llama-4-scout-17b-16e-w4a16"),
        api_key=llm_config.get("api_key", "dummy-key"),
        temperature=llm_config.get("temperature", 0.1),
        max_tokens=llm_config.get("max_tokens", 4096),
        
        # Production resilience configuration
        request_timeout=llm_config.get("request_timeout", 120.0),
        max_retries=llm_config.get("max_retries", 3)
    )


def get_prompts():
    """Get configured prompts for context agent"""
    config = _load_config_sync()
    return config.get('prompts', {}).get('context_agent', {})


def get_prompt(prompt_name: str, default: str = "") -> str:
    """Get a specific prompt by name with fallback to default"""
    prompts = get_prompts()
    return prompts.get(prompt_name, default)
