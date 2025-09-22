"""
x2a Agent-Specific Test Extensions

Agent-specific test patterns and utilities for all x2a agents.
Each agent module provides specialized test patterns, assertions, and utilities
tailored to that agent's specific behavior and requirements.

Agents Covered:
- code_gen: Code generation and conversion testing patterns
- context_agent: RAG retrieval and context management testing
- validation: Ansible-lint and validation testing patterns
- orchestrator: Task planning and coordination testing
- universal_extractor: Platform detection and extraction testing
- structured_analyzer: Infrastructure analysis testing
- spec_generator: Specification generation testing
- storage_manager: Neo4j storage operation testing
- synthesizer: Result synthesis testing
"""

# Primary x2a Agents (step by step implementation)
from .code_gen import CodeGenTestPatterns
from .context_agent import ContextAgentTestPatterns  #  Step 2 complete
from .validation import ValidationTestPatterns        #  Step 3 complete

# Infrastructure Analysis Agents (step by step implementation)
from .orchestrator import OrchestratorTestPatterns  #  Step 4 complete
from .universal_extractor import UniversalExtractorTestPatterns  #  Step 5 complete
from .structured_analyzer import StructuredAnalyzerTestPatterns  #  Step 6 complete
from .spec_generator import SpecGeneratorTestPatterns  #  Step 7 complete
from .storage_manager import StorageManagerTestPatterns  #  Step 8 complete
from .synthesizer import SynthesizerTestPatterns  #  Step 9 complete - FINAL!

__all__ = [
    # Currently implemented agents
    "CodeGenTestPatterns",
    "ContextAgentTestPatterns",  #  Step 2 complete
    "ValidationTestPatterns",    #  Step 3 complete
    "OrchestratorTestPatterns",  #  Step 4 complete
    "UniversalExtractorTestPatterns",  #  Step 5 complete
    "StructuredAnalyzerTestPatterns",  #  Step 6 complete
    "SpecGeneratorTestPatterns",  #  Step 7 complete
    "StorageManagerTestPatterns",  #  Step 8 complete
    "SynthesizerTestPatterns"   #  Step 9 complete - FINAL!
    
    # 🎉 ALL 9 X2A AGENTS COMPLETE! 🎉
]
