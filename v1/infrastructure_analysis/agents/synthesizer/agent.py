"""
Synthesizer Agent Implementation

Combines results from all worker agents into unified analysis and specifications.
"""

from datetime import datetime
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

from ...state import InfrastructureAnalysisState
from .tools import (
    analyze_worker_results,
    synthesize_unified_analysis,
    create_comprehensive_specification
)
from ...utils import get_synthesizer_prompt


async def get_llm():
    """Get production-grade LLM for synthesizer"""
    from ...utils.llm_config import get_production_llm
    return await get_production_llm("synthesizer")


async def create_synthesizer_agent():
    """
    Create the synthesizer agent with all synthesis tools.
    
    The synthesizer is responsible for:
    - Analyzing all worker results
    - Creating unified analysis from multiple sources
    - Generating comprehensive specifications
    - Ensuring quality and completeness
    """
    
    llm = await get_llm()
    
    tools = [
        analyze_worker_results,
        synthesize_unified_analysis,
        create_comprehensive_specification
    ]
    
    # Load system prompt from configuration
    system_prompt = get_synthesizer_prompt("system_prompt")
    
    return create_react_agent(llm, tools, prompt=system_prompt)


