"""
Prod-Grade Specification Generation Worker Agent

Creates comprehensive infrastructure specifications using GitHub Spec Kit methodology.
Based on: https://github.com/github/spec-kit.git
"""

from langgraph.prebuilt import create_react_agent

from .tools import generate_spec_kit_specification
from ...utils import get_worker_prompt


async def get_llm():
    """Get production-grade LLM for spec generation worker"""
    from ...utils.llm_config import get_production_llm
    return await get_production_llm("spec_generator")


async def create_specification_generation_worker():
    """
    Create prod-grade specification generation worker agent.
    
    Uses GitHub Spec Kit methodology for prod-grade specifications.
    """
    
    llm = await get_llm()
    tools = [generate_spec_kit_specification]
    
    # Load system prompt from configuration
    system_prompt = get_worker_prompt("spec_generator", "system_prompt")
    
    return create_react_agent(llm, tools, prompt=system_prompt)
