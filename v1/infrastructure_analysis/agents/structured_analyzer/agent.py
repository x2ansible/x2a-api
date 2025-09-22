#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Structured Analysis Worker Agent

LangGraph-compliant agent creation for structured analysis.
Contains ONLY agent creation logic - all business logic is in focused tools.

The agent acts as an intelligent orchestrator, making decisions about
which specialized tools to use based on the specific analysis requirements.
"""

from langgraph.prebuilt import create_react_agent

from ...utils import get_worker_prompt
from .tools import (
    # Platform Analysis Tools
    analyze_chef_infrastructure,
    analyze_puppet_infrastructure, 
    analyze_terraform_infrastructure,
    analyze_generic_infrastructure,
    
    # Specialized Analysis Tools
    calculate_infrastructure_complexity,
    generate_security_considerations, 
    generate_migration_recommendations
)


async def get_llm():
    """Get production-grade LLM with timeout and retry configuration"""
    from ...utils.llm_config import get_production_llm
    return await get_production_llm("structured_analyzer")


async def create_structured_analysis_worker():
    """
    Create structured analysis worker agent with focused tools.
    
    The agent has access to all specialized tools and acts as an intelligent
    orchestrator, making decisions about which tools to use based on the
    specific analysis requirements and context.
    
    Available Tools:
    - Platform Analysis: chef, puppet, terraform, generic infrastructure analysis
    - Complexity Analysis: infrastructure complexity scoring and assessment  
    - Security Analysis: security considerations and vulnerability assessment
    - Migration Analysis: migration recommendations and modernization strategies
    
    Returns a ReAct agent configured with all focused analysis tools
    and system prompt from configuration.
    """
    llm = await get_llm()
    
    # All focused tools available to the agent for intelligent decision-making
    tools = [
        # Platform Analysis Tools - Agent chooses based on detected platform
        analyze_chef_infrastructure,
        analyze_puppet_infrastructure, 
        analyze_terraform_infrastructure,
        analyze_generic_infrastructure,
        
        # Specialized Analysis Tools - Agent decides which analyses to perform
        calculate_infrastructure_complexity,
        generate_security_considerations, 
        generate_migration_recommendations
    ]
    
    # Load system prompt from configuration
    system_prompt = get_worker_prompt("structured_analyzer", "system_prompt")
    
    return create_react_agent(llm, tools, prompt=system_prompt)