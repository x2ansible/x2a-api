#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Orchestrator Agent Implementation

Agent creation function for the orchestrator that analyzes infrastructure
code and creates dynamic worker assignments for optimal processing.
"""

from langgraph.prebuilt import create_react_agent

from .tools import (
    analyze_infrastructure_requirements,
    create_worker_assignments,
    monitor_worker_progress,
    create_spec_kit_plan
)
from ...utils import get_orchestrator_prompt_async
from ...utils.llm_config import get_production_llm


async def get_llm():
    """Get production-grade LLM for orchestrator with robust timeout and retry settings"""
    return await get_production_llm("orchestrator")


async def create_orchestrator_agent():
    """
    Create the orchestrator agent with all necessary tools.
    
    The orchestrator is responsible for:
    - Analyzing input requirements
    - Creating worker assignments
    - Monitoring worker progress 
    - Making high-level decisions
    """
    
    llm = await get_llm()
    
    # Define orchestrator tools
    tools = [
        analyze_infrastructure_requirements,
        create_worker_assignments,
        monitor_worker_progress,
        create_spec_kit_plan
    ]
    
    # Load system prompt from configuration (async)
    system_prompt = await get_orchestrator_prompt_async("system_prompt")
    
    return create_react_agent(
        llm,
        tools,
        prompt=system_prompt
    )