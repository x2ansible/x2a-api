"""
Infrastructure Analysis Test Suite

Centralized testing for all infrastructure analysis agents using x2a_test_framework.
Provides comprehensive test coverage for the complete infrastructure analysis system.

Agents Covered:
- orchestrator: Task planning and worker coordination
- universal_extractor: Platform detection and fact extraction  
- structured_analyzer: Infrastructure analysis and complexity assessment
- spec_generator: GitHub Spec Kit specification generation
- storage_manager: Neo4j storage and retrieval operations
- synthesizer: Result synthesis and final output generation

Usage:
    # Run all infrastructure analysis tests
    python run_all_infrastructure_tests.py
    
    # Quick validation
    python run_all_infrastructure_tests.py --quick
    
    # Test specific agent
    python run_all_infrastructure_tests.py --orchestrator
    
    # Test orchestrator specifically
    cd orchestrator && python run_tests.py
"""

__version__ = "1.0.0"

__all__ = [
    "orchestrator",
    "universal_extractor", 
    "structured_analyzer",
    "spec_generator",
    "storage_manager",
    "synthesizer"
]
