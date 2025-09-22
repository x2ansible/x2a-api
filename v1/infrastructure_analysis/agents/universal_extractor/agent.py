#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Universal Extraction Agent

A single intelligent agent that can detect platforms and extract facts from any
infrastructure code type (Chef, Puppet, Terraform, Ansible, BladeLogic, Salt).

This follows the pure agentic pattern where the LLM decides which tools to use
based on the input, rather than hardcoded routing.
"""

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from .tools import (
    platform_detector,
    puppet_facts_extractor,
    terraform_facts_extractor,
    bladelogic_facts_extractor,
    chef_facts_extractor_legacy
)
from ...utils import get_worker_prompt


async def get_llm():
    """Get production-grade LLM for universal extraction agent"""
    from ...utils.llm_config import get_production_llm
    return await get_production_llm("universal_extractor")


async def create_universal_extraction_agent():
    """
    Create the universal extraction agent with all platform tools.
    
    This agent can:
    - Detect what platform(s) the input code uses
    - Choose the appropriate extraction tool(s) 
    - Extract structured facts from any supported platform
    - Handle mixed-platform codebases intelligently
    
    Supported platforms:
    - Chef (cookbooks, recipes, resources)
    - Puppet (manifests, modules, classes)
    - Terraform (configurations, modules, providers)
    - BladeLogic (scripts, configurations)
    - Ansible (playbooks, roles) [via pattern matching]
    - Salt (states, formulas) [via pattern matching]
    """
    
    llm = await get_llm()
    
    # All available tools for platform detection and extraction
    tools = [
        # Platform detection tools
        platform_detector,
        
        # Extraction tools for all platforms
        chef_facts_extractor_legacy, # Legacy Chef extractor
        puppet_facts_extractor,      # Puppet manifests
        terraform_facts_extractor,   # Terraform configurations
        bladelogic_facts_extractor,  # BladeLogic scripts
    ]
    
    # Load system prompt from configuration
    system_prompt = get_worker_prompt("universal_extractor", "system_prompt")
    
    return create_react_agent(llm, tools, prompt=system_prompt)
