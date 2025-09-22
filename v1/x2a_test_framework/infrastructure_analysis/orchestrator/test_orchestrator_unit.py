"""
Unit Tests for Orchestrator Agent

Tests the orchestrator agent in isolation using LangGraph testing patterns.
Focuses on pure agentic behavior, structured output, and tool usage.

Migrated to x2a_test_framework for centralized testing.
"""

import pytest
import pytest_asyncio
import sys
from pathlib import Path
from typing_extensions import TypedDict

# Add v1 directory to Python path for imports
v1_dir = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(v1_dir))

# Import LangGraph components for testing
try:
    from langgraph.graph import StateGraph, START, END
    from langgraph.checkpoint.memory import MemorySaver
except ImportError:
    pytest.skip("LangGraph not available for testing", allow_module_level=True)

# Import infrastructure analysis components
from infrastructure_analysis.agents.orchestrator.nodes import orchestrator_node
from infrastructure_analysis.agents.orchestrator.nodes import OrchestratorStructuredOutput

# Import x2a test framework components
from x2a_test_framework.core.base_test_suites import BaseNodeTestSuite
from x2a_test_framework.fixtures.sample_codes import X2ATestCodes


class TestOrchestratorState(TypedDict):
    """Minimal state for isolated orchestrator testing"""
    input_code: str
    orchestrator_decision: dict
    worker_assignments: list
    orchestrator_confidence: float
    orchestrator_reasoning: str
    error_messages: list


def create_orchestrator_test_graph() -> StateGraph:
    """
    Create a minimal graph with just the orchestrator node for isolated testing.
    
    This follows the LangGraph testing pattern to test the orchestrator
    independently of other workflow components.
    """
    graph = StateGraph(TestOrchestratorState)
    
    # Add only the orchestrator node for isolation
    graph.add_node("orchestrator", orchestrator_node)
    
    # Simple linear flow for testing
    graph.add_edge(START, "orchestrator")
    graph.add_edge("orchestrator", END)
    
    return graph


class TestOrchestratorUnit(BaseNodeTestSuite):
    """Unit tests for orchestrator agent in isolation using x2a framework"""
    
    def get_node_function(self):
        """Return the orchestrator node function"""
        return orchestrator_node
    
    def create_test_state(self, input_code: str = None, **kwargs):
        """Create test state for orchestrator testing"""
        if input_code is None:
            input_code = X2ATestCodes.get_platform_code("chef", "simple")
        
        return {
            "input_code": input_code,
            "orchestrator_decision": {},
            "worker_assignments": [],
            "orchestrator_confidence": 0.0,
            "orchestrator_reasoning": "",
            "error_messages": []
        }
    
    def get_required_output_fields(self):
        """Return required output fields for orchestrator"""
        return ["orchestrator_decision", "worker_assignments", "orchestrator_confidence"]
    
    def get_node_name(self):
        """Return node name for logging"""
        return "orchestrator"
    
    @pytest.fixture
    def checkpointer(self):
        """Memory saver for state management in tests"""
        return MemorySaver()
    
    @pytest.fixture
    def test_graph(self):
        """Compiled test graph with orchestrator only"""
        graph = create_orchestrator_test_graph()
        return graph.compile(checkpointer=MemorySaver())
    
    @pytest.fixture
    def sample_chef_code(self):
        """Sample Chef cookbook code for testing"""
        return X2ATestCodes.get_platform_code("chef", "medium")
    
    @pytest.fixture
    def sample_terraform_code(self):
        """Sample Terraform configuration for testing"""
        return X2ATestCodes.get_platform_code("terraform", "medium")
    
    @pytest.fixture
    def sample_infrastructure_codes(self):
        """Sample infrastructure codes for mixed platform testing"""
        return {
            "mixed_platform": X2ATestCodes.get_platform_code("mixed_platform", "complex")
        }

    @pytest.mark.asyncio
    async def test_orchestrator_with_chef_code(self, test_graph, sample_chef_code):
        """
        Test orchestrator agent with Chef cookbook code using x2a framework.
        
        Verifies:
        - Structured output generation
        - Platform detection (should detect Chef)
        - Worker assignment creation
        - Confidence scoring
        """
        # Set up initial state for orchestrator testing
        test_graph.update_state(
            config={"configurable": {"thread_id": "chef_test"}},
            values={
                "input_code": sample_chef_code,
                "orchestrator_decision": {},
                "worker_assignments": [],
                "orchestrator_confidence": 0.0,
                "orchestrator_reasoning": "",
                "error_messages": []
            },
            as_node=START
        )
        
        # Execute orchestrator node in isolation using async invoke
        result = await test_graph.ainvoke(
            None,
            config={"configurable": {"thread_id": "chef_test"}},
            interrupt_after="orchestrator"
        )
        
        # Use x2a framework assertions
        self.assert_valid_state_output(result, self.get_required_output_fields())
        
        # Verify structured output was generated
        assert "orchestrator_decision" in result
        assert result["orchestrator_decision"] is not None
        
        # Verify Chef platform was detected
        orchestrator_decision = result["orchestrator_decision"]
        assert "chef" in [p.lower() for p in orchestrator_decision.detected_platforms]
        
        # Verify worker assignments were created
        assert len(result["worker_assignments"]) > 0
        
        # Verify confidence scoring
        assert result["orchestrator_confidence"] > 0.0
        assert result["orchestrator_confidence"] <= 1.0
        
        # Verify reasoning was provided
        assert len(result["orchestrator_reasoning"]) > 0
        
        # Verify no errors occurred in pure agentic execution
        assert len(result.get("error_messages", [])) == 0

    @pytest.mark.asyncio
    async def test_orchestrator_with_terraform_code(self, test_graph, sample_terraform_code):
        """
        Test orchestrator agent with Terraform configuration.
        
        Verifies platform detection works for different infrastructure types.
        """
        test_graph.update_state(
            config={"configurable": {"thread_id": "terraform_test"}},
            values={
                "input_code": sample_terraform_code,
                "orchestrator_decision": {},
                "worker_assignments": [],
                "orchestrator_confidence": 0.0,
                "orchestrator_reasoning": "",
                "error_messages": []
            },
            as_node=START
        )
        
        result = await test_graph.ainvoke(
            None,
            config={"configurable": {"thread_id": "terraform_test"}},
            interrupt_after="orchestrator"
        )
        
        # Verify Terraform platform detection
        orchestrator_decision = result["orchestrator_decision"]
        assert "terraform" in [p.lower() for p in orchestrator_decision.detected_platforms]
        
        # Verify complexity assessment for infrastructure code
        assert orchestrator_decision.complexity_assessment in ["low", "medium", "high"]

    @pytest.mark.asyncio
    async def test_orchestrator_with_mixed_platform_code(self, test_graph, sample_infrastructure_codes):
        """
        Test orchestrator agent with mixed platform code.
        
        Verifies detection of multiple platforms in a single codebase.
        """
        mixed_code = sample_infrastructure_codes["mixed_platform"]
        
        test_graph.update_state(
            config={"configurable": {"thread_id": "mixed_test"}},
            values={
                "input_code": mixed_code,
                "orchestrator_decision": {},
                "worker_assignments": [],
                "orchestrator_confidence": 0.0,
                "orchestrator_reasoning": "",
                "error_messages": []
            },
            as_node=START
        )
        
        result = await test_graph.ainvoke(
            None,
            config={"configurable": {"thread_id": "mixed_test"}},
            interrupt_after="orchestrator"
        )
        
        # Verify multiple platform detection
        orchestrator_decision = result["orchestrator_decision"]
        detected_platforms = [p.lower() for p in orchestrator_decision.detected_platforms]
        
        # Should detect at least 2 platforms from the mixed code (Chef, Terraform, Puppet)
        assert len(detected_platforms) >= 2
        
        # Complexity should be high for mixed platforms
        assert orchestrator_decision.complexity_assessment in ["medium", "high"]
        
        # Should have multiple worker assignments for mixed platforms
        assert len(result["worker_assignments"]) >= 2

    @pytest.mark.asyncio
    async def test_orchestrator_error_handling_empty_input(self, test_graph):
        """
        Test orchestrator error handling with empty input.
        
        Verifies pure agentic failure behavior (no fallbacks).
        """
        test_graph.update_state(
            config={"configurable": {"thread_id": "error_test"}},
            values={
                "input_code": "",  # Empty input should cause failure
                "orchestrator_decision": {},
                "worker_assignments": [],
                "orchestrator_confidence": 0.0,
                "orchestrator_reasoning": "",
                "error_messages": []
            },
            as_node=START
        )
        
        # Should raise an exception (pure agentic - no fallbacks)
        with pytest.raises((ValueError, RuntimeError)):
            await test_graph.ainvoke(
                None,
                config={"configurable": {"thread_id": "error_test"}},
                interrupt_after="orchestrator"
            )


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__])
