"""
x2a Enterprise Test Framework

Production-grade testing framework for x2a's LangGraph agentic infrastructure analysis solution.

This framework provides comprehensive testing capabilities for all agents, nodes, and workflows
in the x2a system, supporting both unit and integration testing with enterprise-grade patterns.

Key Components:
- BaseAgentTestSuite: Standard agent creation and configuration testing
- BaseNodeTestSuite: Individual LangGraph node testing patterns  
- StateFactory: Centralized state management for all agent types
- TestPatterns: Common assertion patterns for platform detection, confidence, etc.
- TestConfig: Configuration management for test environments
- MockBuilders: Agent and LLM mocking utilities

Supported Agents:
- Code Gen Agent: Chef to Ansible code generation and conversion
- Context Agent: RAG-based context retrieval and knowledge management
- Validation Agent: Ansible-lint validation and quality assurance
- Orchestrator Agent: Task planning and worker coordination
- Universal Extractor: Platform detection and fact extraction
- Structured Analyzer: Comprehensive infrastructure analysis
- Spec Generator: Specification and documentation generation
- Storage Manager: Neo4j storage and retrieval operations
- Synthesizer: Result synthesis and final output generation

Usage:
    from x2a_test_framework import BaseAgentTestSuite, StateFactory
    
    class TestMyAgent(BaseAgentTestSuite):
        def get_agent_creation_function(self):
            return create_my_agent
            
        def get_expected_tools(self):
            return ["tool1", "tool2"]

Version: 1.0.0
Author: x2a Engineering Team
"""

__version__ = "1.0.0"
__author__ = "x2a Engineering Team"

# Core framework components
from .core.base_test_suites import BaseAgentTestSuite, BaseNodeTestSuite
from .core.state_factories import StateFactory, WorkflowStateFactory
from .core.test_patterns import TestPatterns, AssertionHelpers
from .core.test_utilities import LangGraphTestMixin, AsyncTestRunner
from .core.test_config import X2ATestConfig, TestEnvironment

# Real-system test fixtures
from .fixtures.sample_codes import PlatformTestCodes, WorkflowTestData, X2ATestCodes

# Agent-specific test extensions (will be added step by step)
# from .agents.code_gen import CodeGenTestPatterns
# from .agents.context_agent import ContextAgentTestPatterns  
# from .agents.validation import ValidationTestPatterns
# from .agents.orchestrator import OrchestratorTestPatterns
# from .agents.universal_extractor import UniversalExtractorTestPatterns
# from .agents.structured_analyzer import StructuredAnalyzerTestPatterns
# from .agents.spec_generator import SpecGeneratorTestPatterns
# from .agents.storage_manager import StorageManagerTestPatterns
# from .agents.synthesizer import SynthesizerTestPatterns

__all__ = [
    # Core Framework
    "BaseAgentTestSuite",
    "BaseNodeTestSuite", 
    "StateFactory",
    "WorkflowStateFactory",
    "TestPatterns",
    "AssertionHelpers",
    "LangGraphTestMixin",
    "AsyncTestRunner",
    "X2ATestConfig",
    "TestEnvironment",
    
    # Real-System Test Fixtures
    "PlatformTestCodes",
    "WorkflowTestData",
    "X2ATestCodes",
    
    # Agent-specific patterns will be added step by step
    # Integration testing will be added later
]

# Framework metadata
FRAMEWORK_INFO = {
    "name": "x2a Enterprise Test Framework",
    "version": __version__,
    "description": "Production-grade testing framework for x2a LangGraph agents",
    "supported_agents": [
        "code_gen",
        "context_agent", 
        "validation",
        "orchestrator",
        "universal_extractor", 
        "structured_analyzer",
        "spec_generator",
        "storage_manager",
        "synthesizer"
    ],
    "capabilities": [
        "Agent creation testing",
        "Node isolation testing", 
        "State management validation",
        "Performance benchmarking",
        "Integration workflow testing",
        "Mock LLM and agent builders",
        "Platform detection validation",
        "Confidence scoring verification"
    ]
}

def get_framework_info():
    """Get comprehensive framework information."""
    return FRAMEWORK_INFO

def validate_framework_installation():
    """Validate that the framework is properly installed and configured."""
    try:
        # Test core imports
        from .core.base_test_suites import BaseAgentTestSuite
        from .core.state_factories import StateFactory
        from .core.test_patterns import TestPatterns
        
        # Test fixture imports
        from .fixtures.sample_codes import PlatformTestCodes
        from .fixtures.mock_builders import MockAgentBuilder
        
        return True, "x2a Test Framework successfully installed and validated"
        
    except ImportError as e:
        return False, f"Framework installation validation failed: {str(e)}"

# Framework constants
DEFAULT_TIMEOUT = 30.0
DEFAULT_TEST_ENVIRONMENT = "test"
SUPPORTED_PLATFORMS = ["chef", "terraform", "puppet", "salt", "bladelogic"]
SUPPORTED_AGENTS = ["code_gen", "context_agent", "validation", "orchestrator", 
                   "universal_extractor", "structured_analyzer", "spec_generator", 
                   "storage_manager", "synthesizer"]
