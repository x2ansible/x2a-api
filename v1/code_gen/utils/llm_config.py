"""
Production-Grade LLM Configuration for Code Generation Agent

Centralized LLM setup with robust timeout and retry configuration.
"""

import os
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
        base_url=llm_config.get("base_url", "http://localhost:8000/v1"),
        model=llm_config.get("model", "llama-4-scout-17b-16e-w4a16"),
        api_key=llm_config.get("api_key", os.getenv("LLM_API_KEY", "dummy-key")),
        temperature=llm_config.get("temperature", 0.1),
        max_tokens=llm_config.get("max_tokens", 4096),
        
        # Production resilience configuration
        request_timeout=llm_config.get("request_timeout", 120.0),  # 2-minute timeout for complex requests
        max_retries=llm_config.get("max_retries", 3)              # Retry up to 3 times on failure
    )
