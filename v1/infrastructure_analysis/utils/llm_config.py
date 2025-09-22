#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Production-Grade LLM Configuration Utility

Centralized LLM configuration with robust timeout and retry settings
for all infrastructure analysis agents.
"""

import os
import asyncio
import yaml
from pathlib import Path
from langchain_openai import ChatOpenAI


async def get_production_llm(agent_name: str = "infrastructure_analysis") -> ChatOpenAI:
    """
    Get production-grade LLM configuration with timeout and retry settings.
    
    This function provides a robust LLM configuration suitable for production
    LangGraph applications with proper error handling and resilience.
    
    Args:
        agent_name: Name of the agent requesting the LLM (for logging)
        
    Returns:
        ChatOpenAI: Configured LLM with production-grade settings
    """
    
    # Load configuration from v1/config.yaml (async)
    config_path = Path(__file__).parent.parent.parent / "config.yaml"
    
    def _load_config():
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    config = await asyncio.to_thread(_load_config)
    llm_config = config.get("llm", {})
    
    # Production-grade LLM configuration with comprehensive timeout and retry settings
    llm = ChatOpenAI(
        base_url=llm_config.get("base_url", "https://api.openai.com/v1"),
        model=llm_config.get("model", "gpt-4o-mini"),
        api_key=llm_config.get("api_key", os.getenv("LLM_API_KEY", "dummy-key")),
        temperature=llm_config.get("temperature", 0.1),
        max_tokens=llm_config.get("max_tokens", 4096),
        
        # Production resilience configuration
        request_timeout=llm_config.get("request_timeout", 120.0),  # 2-minute timeout for complex requests
        max_retries=llm_config.get("max_retries", 3)              # Retry up to 3 times on failure
    )
    
    return llm


def get_llm_with_custom_timeout(timeout_seconds: float, agent_name: str = "custom") -> ChatOpenAI:
    """
    Get LLM with custom timeout for specific use cases.
    
    Args:
        timeout_seconds: Custom timeout in seconds
        agent_name: Name of the agent requesting the LLM
        
    Returns:
        ChatOpenAI: LLM configured with custom timeout
    """
    
    config_path = Path(__file__).parent.parent.parent / "config.yaml"
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    llm_config = config.get("llm", {})
    
    return ChatOpenAI(
        base_url=llm_config.get("base_url", "https://api.openai.com/v1"),
        model=llm_config.get("model", "gpt-4o-mini"),
        api_key=llm_config.get("api_key", os.getenv("LLM_API_KEY", "dummy-key")),
        temperature=llm_config.get("temperature", 0.1),
        max_tokens=llm_config.get("max_tokens", 4096),
        
        # Custom timeout configuration
        request_timeout=timeout_seconds,
        max_retries=llm_config.get("max_retries", 3),
        timeout=llm_config.get("connect_timeout", 30.0)
    )


def get_llm_config_summary() -> dict:
    """
    Get a summary of the current LLM configuration for debugging.
    
    Returns:
        dict: Configuration summary
    """
    config_path = Path(__file__).parent.parent.parent / "config.yaml"
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    llm_config = config.get("llm", {})
    
    return {
        "model": llm_config.get("model", "unknown"),
        "base_url": llm_config.get("base_url", "unknown"),
        "request_timeout": llm_config.get("request_timeout", "not configured"),
        "max_retries": llm_config.get("max_retries", "not configured"),
        "connect_timeout": llm_config.get("connect_timeout", "not configured"),
        "max_tokens": llm_config.get("max_tokens", "not configured")
    }
