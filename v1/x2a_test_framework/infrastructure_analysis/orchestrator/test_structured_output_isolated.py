"""
Isolated Structured Output Tests for Orchestrator Agent

Tests only the Pydantic structured output schema without dependencies.
This provides a clean test that validates the schema independently.

Migrated to x2a_test_framework for centralized testing.
"""

import pytest
import sys
from pathlib import Path
from pydantic import BaseModel, Field, ValidationError
from typing import Dict, List, Any

# Add v1 directory to Python path for imports
v1_dir = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(v1_dir))

# Import x2a test framework components
from x2a_test_framework.core.base_test_suites import BaseAgentTestSuite


# Define the structured output schema locally to avoid dependency issues
class OrchestratorStructuredOutput(BaseModel):
    """Structured output schema for orchestrator decisions (isolated version)"""
    
    detected_platforms: List[str] = Field(
        description="List of detected infrastructure platforms (chef, puppet, terraform, etc.)"
    )
    complexity_assessment: str = Field(
        description="Complexity level: low, medium, or high"
    )
    processing_strategy: str = Field(
        description="Overall processing strategy description"
    )
    estimated_duration: int = Field(
        description="Estimated total processing time in minutes"
    )
    worker_assignments: List[dict] = Field(
        description="List of worker task assignments with worker_type, platform, priority, and requirements"
    )
    confidence: float = Field(
        description="Confidence in the analysis and assignments (0.0-1.0)",
        ge=0.0, le=1.0
    )
    reasoning: str = Field(
        description="Explanation of the orchestrator's decision-making process"
    )


class TestOrchestratorStructuredOutputIsolated:
    """Test structured output schema validation (isolated from dependencies)"""
    
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
    
    def test_framework_integration(self):
        """Test x2a framework integration without external dependencies"""
        
        # Test that we can import framework components
        try:
            from x2a_test_framework.fixtures.sample_codes import X2ATestCodes
            
            # Test that sample codes are available
            chef_code = X2ATestCodes.get_platform_code("chef", "simple")
            assert len(chef_code) > 50, "Chef test code should be available"
            
            # Test structured output with framework data
            valid_data = {
                "detected_platforms": ["chef"],
                "complexity_assessment": "simple",
                "processing_strategy": "basic_chef_analysis",
                "estimated_duration": 8,
                "worker_assignments": [
                    {
                        "worker_type": "chef_extractor",
                        "platform": "chef",
                        "priority": 1,
                        "requirements": {"code_length": len(chef_code)}
                    }
                ],
                "confidence": 0.75,
                "reasoning": f"Simple Chef cookbook ({len(chef_code)} chars) detected for basic analysis"
            }
            
            output = OrchestratorStructuredOutput(**valid_data)
            assert output.detected_platforms == ["chef"]
            assert output.confidence == 0.75
            
        except ImportError as e:
            pytest.skip(f"Framework components not available: {e}")


if __name__ == "__main__":
    pytest.main([__file__])
