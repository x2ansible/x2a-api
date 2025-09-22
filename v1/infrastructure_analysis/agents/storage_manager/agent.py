#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Storage Management Worker Agent

Handles Neo4j storage with intelligent deduplication and relationship management.
Uses real Neo4j database operations for production-ready infrastructure analysis storage.
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Dict, Any
from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import PydanticOutputParser
from langgraph.prebuilt import create_react_agent

from ...state import WorkerState, WorkerResult
from ...utils import get_worker_prompt
from ...response_models import Neo4jStorageResult, InfrastructureAnalysisStorage
from .tools import store_infrastructure_analysis, check_duplicate_analysis, create_analysis_relationships


async def get_llm():
    """Get production-grade LLM for storage management worker"""
    from ...utils.llm_config import get_production_llm
    return await get_production_llm("storage_manager")


async def create_storage_management_worker():
    """Create storage management worker agent with structured output"""
    
    llm = await get_llm()
    tools = [store_infrastructure_analysis, check_duplicate_analysis, create_analysis_relationships]
    
    # Load system prompt from configuration with format instructions
    parser = PydanticOutputParser(pydantic_object=Neo4jStorageResult)
    system_prompt = get_worker_prompt("storage_manager", "system_prompt")
    system_prompt += f"\n\nIMPORTANT: Use the provided tools to store analysis results in Neo4j. After successful storage, provide your final answer in this exact JSON format:\n{parser.get_format_instructions()}"
    
    return create_react_agent(llm, tools, prompt=system_prompt)
