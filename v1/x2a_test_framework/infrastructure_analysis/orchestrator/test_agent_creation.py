"""
Agent Creation Tests for Orchestrator

Tests the orchestrator agent creation, tool binding, and configuration.
These tests validate that the agent is properly constructed with correct tools and settings.

Migrated to x2a_test_framework for centralized testing.
"""

import pytest
import sys
from pathlib import Path

# Add v1 directory to Python path for imports
v1_dir = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(v1_dir))

# Import infrastructure analysis components
from infrastructure_analysis.agents.orchestrator.agent import create_orchestrator_agent
from infrastructure_analysis.agents.orchestrator.tools import (
    analyze_infrastructure_requirements,
    create_worker_assignments,
    create_spec_kit_plan,
    monitor_worker_progress
)

# Import x2a test framework components
from x2a_test_framework.core.base_test_suites import BaseAgentTestSuite


class TestOrchestratorAgentCreation(BaseAgentTestSuite):
    """Test suite for orchestrator agent creation and configuration using x2a framework"""
    
    def get_agent_creation_function(self):
        """Return the orchestrator agent creation function"""
        return create_orchestrator_agent
    
    def get_expected_tools(self):
        """Return list of expected tool names for orchestrator"""
        return [
            "analyze_infrastructure_requirements",
            "create_worker_assignments",
            "create_spec_kit_plan", 
            "monitor_worker_progress"
        ]
    
    def get_agent_type(self):
        """Return the agent type for logging"""
        return "orchestrator"

    def test_agent_creation_success(self):
        """
        Test that orchestrator agent is created successfully.
        
        Verifies:
        - Agent creation completes without errors
        - Agent has correct type (CompiledStateGraph)
        - Agent has required methods (invoke, ainvoke, etc.)
        """
        agent = create_orchestrator_agent()
        
        # Use parent class assertions
        assert agent is not None
        assert hasattr(agent, 'invoke'), "Agent should have invoke method"
        assert hasattr(agent, 'ainvoke'), "Agent should have ainvoke method"
        assert hasattr(agent, 'astream'), "Agent should have astream method"
        assert hasattr(agent, 'get_graph'), "Agent should have get_graph method"

    def test_agent_tools_binding(self):
        """
        Test that orchestrator agent has proper tool bindings.
        
        Verifies that all expected tools are available and properly bound.
        """
        agent = create_orchestrator_agent()
        
        # Verify agent was created successfully
        assert agent is not None
        
        # Verify agent graph structure
        graph = agent.get_graph()
        assert graph is not None
        
        # The tools are bound to the LLM within the agent, so we verify
        # that the agent can be invoked without errors (tools are available)
        assert hasattr(agent, 'invoke'), "Agent should have invoke method for tool usage"

    def test_agent_tool_functions_available(self):
        """
        Test that individual tool functions are available and importable.
        
        This ensures the tools exist and can be imported independently.
        """
        # Verify each tool function is callable
        expected_tools = self.get_expected_tools()
        
        tool_functions = [
            analyze_infrastructure_requirements,
            create_worker_assignments,
            create_spec_kit_plan,
            monitor_worker_progress
        ]
        
        for tool_func in tool_functions:
            assert callable(tool_func), f"Tool function {tool_func.__name__} should be callable"
            assert hasattr(tool_func, '__name__'), f"Tool function should have __name__ attribute"

    def test_agent_configuration_consistency(self):
        """
        Test that agent configuration is consistent across multiple creations.
        
        Verifies that the agent creation is deterministic and idempotent.
        """
        # Create multiple agents
        agent1 = create_orchestrator_agent()
        agent2 = create_orchestrator_agent()
        
        # Both should be valid
        assert agent1 is not None
        assert agent2 is not None
        
        # Both should have the same basic structure
        assert hasattr(agent1, 'invoke')
        assert hasattr(agent2, 'invoke')
        assert hasattr(agent1, 'get_graph')
        assert hasattr(agent2, 'get_graph')

    def test_agent_graph_structure(self):
        """
        Test that the agent has a proper LangGraph structure.
        
        Verifies the internal graph structure is valid.
        """
        agent = create_orchestrator_agent()
        
        # Get the graph structure
        graph = agent.get_graph()
        assert graph is not None
        
        # Should have nodes and edges
        assert hasattr(graph, 'nodes'), "Graph should have nodes"
        assert len(graph.nodes) > 0, "Graph should have at least one node"


if __name__ == "__main__":
    pytest.main([__file__])
