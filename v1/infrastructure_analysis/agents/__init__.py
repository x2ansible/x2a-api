"""
Infrastructure Analysis Agents

Orchestrator-Worker pattern agents for production-ready infrastructure analysis.
Uses dynamic orchestrator-driven task planning with specialized worker agents.
"""

# Import agent creation functions
from .orchestrator.agent import create_orchestrator_agent
from .synthesizer.agent import create_synthesizer_agent
from .universal_extractor.agent import create_universal_extraction_agent
from .structured_analyzer.agent import create_structured_analysis_worker
from .spec_generator.agent import create_specification_generation_worker
from .storage_manager.agent import create_storage_management_worker

# Import node functions
from .orchestrator.nodes import orchestrator_node
from .synthesizer.nodes import synthesizer_node
from .universal_extractor.nodes import universal_extraction_node
from .structured_analyzer.nodes import structured_analysis_worker_node
from .spec_generator.nodes import specification_generation_worker_node
from .storage_manager.nodes import storage_management_worker_node

__all__ = [
    # Orchestrator-Worker Pattern Agents
    "orchestrator_node",
    "create_orchestrator_agent",
    
    # Universal Extraction Agent (replaces platform_detector + platform-specific extractors)
    "universal_extraction_node", 
    "create_universal_extraction_agent",
    
    # Structured Analysis Worker
    "structured_analysis_worker_node",
    "create_structured_analysis_worker", 
    
    # Specification Generation Worker
    "specification_generation_worker_node",
    "create_specification_generation_worker",
    
    # Storage Management Worker
    "storage_management_worker_node",
    "create_storage_management_worker",
    
    # Synthesizer
    "synthesizer_node", 
    "create_synthesizer_agent"
]
