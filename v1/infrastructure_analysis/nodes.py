#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Infrastructure Analysis Nodes

LangGraph node functions for the orchestrator-worker pattern.
Each node processes state and returns updated state.
"""

from infrastructure_analysis.agents.orchestrator.nodes import orchestrator_node
from infrastructure_analysis.agents.synthesizer.nodes import synthesizer_node
from infrastructure_analysis.agents.universal_extractor.nodes import universal_extraction_node
from infrastructure_analysis.agents.structured_analyzer.nodes import structured_analysis_worker_node
from infrastructure_analysis.agents.spec_generator.nodes import specification_generation_worker_node
from infrastructure_analysis.agents.storage_manager.nodes import storage_management_worker_node

__all__ = [
    "orchestrator_node",
    "universal_extraction_node",  # Replaces platform_detection + platform-specific extraction
    "structured_analysis_worker_node",
    "specification_generation_worker_node",
    "storage_management_worker_node",
    "synthesizer_node"
]
