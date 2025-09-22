"""
Structured Output Tests for Orchestrator Agent

Focused tests specifically for LangChain structured output functionality.
Ensures our pure agentic orchestrator produces valid Pydantic objects.

Migrated to x2a_test_framework for centralized testing.
"""

import pytest
import sys
from pathlib import Path
from pydantic import ValidationError

# Add v1 directory to Python path for imports
v1_dir = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(v1_dir))

# Import infrastructure analysis components
from infrastructure_analysis.agents.orchestrator.nodes import OrchestratorStructuredOutput
from infrastructure_analysis.agents.orchestrator.agent import create_orchestrator_agent

# Import x2a test framework components
from x2a_test_framework.core.base_test_suites import BaseAgentTestSuite
from x2a_test_framework.agents.orchestrator import OrchestratorTestPatterns


class TestOrchestratorStructuredOutput(BaseAgentTestSuite):
    """Test structured output schema and validation using x2a framework"""
    
    def get_agent_creation_function(self):
        """Return orchestrator agent creation function"""
        return create_orchestrator_agent
    
    def get_expected_tools(self):
        """Return expected orchestrator tools"""
        return [
            "analyze_infrastructure_requirements",
            "create_worker_assignments", 
            "create_spec_kit_plan",
            "monitor_worker_progress"
        ]
    
    def get_agent_type(self):
        """Return agent type for logging"""
        return "orchestrator"
    
    def test_structured_output_schema_validation(self):
        """Test that the Pydantic schema validates correctly"""
        
        # Valid structured output data
        valid_data = {
            "detected_platforms": ["chef", "terraform"],
            "complexity_assessment": "medium",
            "processing_strategy": "orchestrator_worker_sequential",
            "estimated_duration": 15,
            "worker_assignments": [
                {
                    "worker_type": "universal_extractor",
                    "platform": "chef",
                    "priority": 1,
                    "requirements": {"analysis_depth": "standard"}
                }
            ],
            "confidence": 0.85,
            "reasoning": "Detected Chef cookbook with moderate complexity requiring standard analysis"
        }
        
        # Should create valid object
        output = OrchestratorStructuredOutput(**valid_data)
        
        assert output.detected_platforms == ["chef", "terraform"]
        assert output.complexity_assessment == "medium"
        assert output.confidence == 0.85
        assert len(output.worker_assignments) == 1
        assert output.worker_assignments[0]["worker_type"] == "universal_extractor"
    
    def test_structured_output_field_validation(self):
        """Test field validation constraints"""
        
        # Test confidence range validation
        with pytest.raises(ValidationError):
            OrchestratorStructuredOutput(
                detected_platforms=["chef"],
                complexity_assessment="medium", 
                processing_strategy="test",
                estimated_duration=10,
                worker_assignments=[],
                confidence=1.5,  # Invalid: > 1.0
                reasoning="Test"
            )
        
        with pytest.raises(ValidationError):
            OrchestratorStructuredOutput(
                detected_platforms=["chef"],
                complexity_assessment="medium",
                processing_strategy="test", 
                estimated_duration=10,
                worker_assignments=[],
                confidence=-0.1,  # Invalid: < 0.0
                reasoning="Test"
            )
    
    def test_structured_output_required_fields(self):
        """Test that all required fields are enforced"""
        
        # Missing required fields should raise ValidationError
        with pytest.raises(ValidationError):
            OrchestratorStructuredOutput(
                detected_platforms=["chef"],
                # Missing other required fields
            )
    
    def test_structured_output_with_agent(self):
        """Test that the orchestrator agent can be created successfully"""
        
        # Create orchestrator agent (this is a ReAct agent, not a base LLM)
        orchestrator_agent = create_orchestrator_agent()
        
        # Verify the agent was created successfully
        assert orchestrator_agent is not None
        
        # Verify it's a LangGraph agent (CompiledStateGraph)
        assert hasattr(orchestrator_agent, 'ainvoke')
        assert hasattr(orchestrator_agent, 'invoke')
        
        # The structured output is applied in the nodes.py file directly to the LLM
        # This test just verifies the agent creation works
    
    def test_structured_output_empty_platforms(self):
        """Test handling of empty platform detection"""
        
        # Should handle empty platforms list
        valid_data = {
            "detected_platforms": [],  # Empty list should be valid
            "complexity_assessment": "low",
            "processing_strategy": "minimal_processing",
            "estimated_duration": 5,
            "worker_assignments": [],
            "confidence": 0.3,  # Low confidence for empty detection
            "reasoning": "No clear platforms detected, using minimal processing"
        }
        
        output = OrchestratorStructuredOutput(**valid_data)
        assert output.detected_platforms == []
        assert output.confidence == 0.3
    
    def test_structured_output_multiple_platforms(self):
        """Test handling of multiple platform detection"""
        
        valid_data = {
            "detected_platforms": ["chef", "puppet", "terraform"],
            "complexity_assessment": "high",
            "processing_strategy": "multi_platform_comprehensive",
            "estimated_duration": 25,
            "worker_assignments": [
                {"worker_type": "chef_extractor", "platform": "chef", "priority": 1, "requirements": {}},
                {"worker_type": "puppet_extractor", "platform": "puppet", "priority": 1, "requirements": {}},
                {"worker_type": "terraform_extractor", "platform": "terraform", "priority": 1, "requirements": {}}
            ],
            "confidence": 0.92,
            "reasoning": "Multiple platforms detected requiring comprehensive analysis"
        }
        
        output = OrchestratorStructuredOutput(**valid_data)
        assert len(output.detected_platforms) == 3
        assert output.complexity_assessment == "high"
        assert len(output.worker_assignments) == 3
    
    def test_structured_output_using_framework_patterns(self):
        """Test structured output using x2a framework patterns"""
        
        # Use framework pattern for validation
        valid_structured_output = {
            "detected_platforms": ["chef"],
            "complexity_assessment": "medium",
            "processing_strategy": "standard_analysis",
            "estimated_duration": 12,
            "worker_assignments": [
                {
                    "worker_type": "universal_extractor",
                    "platform": "chef",
                    "priority": 1,
                    "requirements": {"analysis_depth": "standard"}
                }
            ],
            "confidence": 0.88,
            "reasoning": "Chef cookbook detected with standard complexity requirements"
        }
        
        # Use x2a framework assertion patterns
        OrchestratorTestPatterns.assert_orchestrator_structured_output(
            valid_structured_output
        )
        
        # Should not raise any exceptions if validation passes


if __name__ == "__main__":
    pytest.main([__file__])
