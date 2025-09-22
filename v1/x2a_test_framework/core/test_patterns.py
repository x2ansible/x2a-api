"""
x2a Test Patterns and Assertion Helpers

Enterprise-grade test patterns and assertion helpers for x2a LangGraph agent testing.
Provides standardized validation patterns that can be reused across all agents.

Key Features:
- Platform detection validation
- Confidence level verification  
- Worker assignment validation
- State structure validation
- Performance assertion patterns
- Business logic validation helpers
- Enterprise error reporting and debugging
"""

import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime

logger = logging.getLogger("x2a_test_framework.test_patterns")


class AssertionError(Exception):
    """Enhanced assertion error with detailed context."""
    def __init__(self, message: str, context: Dict[str, Any] = None):
        super().__init__(message)
        self.context = context or {}
        self.timestamp = datetime.now().isoformat()


class ValidationPatterns:
    """
    Enterprise validation patterns for x2a system components.
    
    Provides reusable validation logic for common x2a patterns.
    """
    
    @staticmethod
    def validate_platform_list(platforms: List[str], valid_platforms: List[str] = None) -> bool:
        """Validate that platform list contains valid platforms."""
        valid_platforms = valid_platforms or ["chef", "terraform", "puppet", "salt", "bladelogic", "unknown"]
        
        if not isinstance(platforms, list):
            return False
            
        return all(isinstance(p, str) and p.lower() in [vp.lower() for vp in valid_platforms] 
                  for p in platforms)
    
    @staticmethod
    def validate_confidence_score(confidence: float) -> bool:
        """Validate that confidence score is in valid range."""
        return isinstance(confidence, (int, float)) and 0.0 <= confidence <= 1.0
    
    @staticmethod
    def validate_complexity_level(complexity: str) -> bool:
        """Validate that complexity level is valid."""
        valid_levels = ["low", "medium", "high"]
        return isinstance(complexity, str) and complexity.lower() in valid_levels
    
    @staticmethod
    def validate_worker_assignment(assignment: Dict[str, Any]) -> bool:
        """Validate that worker assignment has required structure."""
        required_fields = ["worker_type", "platform", "priority"]
        return all(field in assignment for field in required_fields)
    
    @staticmethod
    def validate_state_structure(state: Dict[str, Any], required_fields: List[str]) -> List[str]:
        """Validate state structure and return list of missing fields."""
        missing_fields = []
        for field in required_fields:
            if field not in state:
                missing_fields.append(field)
        return missing_fields


class TestPatterns:
    """
    Production-grade test patterns for x2a agent validation.
    
    Provides comprehensive assertion methods with detailed error reporting
    and context for debugging test failures.
    """
    
    @staticmethod
    def assert_platform_detection(
        result: Dict[str, Any], 
        expected_platform: str,
        minimum_confidence: float = 0.5,
        context: str = "platform_detection"
    ):
        """
        Assert that platform detection worked correctly with detailed validation.
        
        Args:
            result: The agent result to validate
            expected_platform: Expected platform to be detected
            minimum_confidence: Minimum confidence threshold
            context: Test context for error reporting
        """
        # Validate input parameters
        if not isinstance(expected_platform, str):
            raise AssertionError(
                f"Expected platform must be string, got {type(expected_platform)}",
                {"context": context, "expected_platform": expected_platform}
            )
        
        # Check that result contains platform detection data
        platform_sources = ["orchestrator_decision", "detected_platforms", "extraction_results"]
        platform_data = None
        platform_source = None
        
        for source in platform_sources:
            if source in result:
                platform_data = result[source]
                platform_source = source
                break
        
        if platform_data is None:
            available_fields = list(result.keys())
            raise AssertionError(
                f"No platform detection data found. Expected one of: {platform_sources}",
                {
                    "context": context,
                    "available_fields": available_fields,
                    "expected_platform": expected_platform
                }
            )
        
        # Extract detected platforms from different result formats
        detected_platforms = []
        
        if platform_source == "orchestrator_decision":
            if hasattr(platform_data, 'detected_platforms'):
                detected_platforms = [p.lower() for p in platform_data.detected_platforms]
            elif isinstance(platform_data, dict) and "detected_platforms" in platform_data:
                detected_platforms = [p.lower() for p in platform_data["detected_platforms"]]
                
        elif platform_source == "detected_platforms":
            if isinstance(platform_data, list):
                detected_platforms = [p.lower() for p in platform_data]
                
        elif platform_source == "extraction_results":
            if isinstance(platform_data, dict) and "detected_platforms" in platform_data:
                detected_platforms = [p.lower() for p in platform_data["detected_platforms"]]
        
        # Validate detected platforms
        if not ValidationPatterns.validate_platform_list(detected_platforms):
            raise AssertionError(
                f"Invalid detected platforms format: {detected_platforms}",
                {
                    "context": context,
                    "platform_source": platform_source,
                    "expected_platform": expected_platform
                }
            )
        
        # Check if expected platform was detected
        expected_lower = expected_platform.lower()
        if expected_lower not in detected_platforms:
            raise AssertionError(
                f"Expected platform '{expected_platform}' not detected. Found: {detected_platforms}",
                {
                    "context": context,
                    "expected_platform": expected_platform,
                    "detected_platforms": detected_platforms,
                    "platform_source": platform_source
                }
            )
        
        # Validate confidence if available
        confidence_fields = ["confidence", "orchestrator_confidence", "extraction_confidence"]
        confidence = None
        
        for field in confidence_fields:
            if field in result:
                confidence = result[field]
                break
        
        if confidence is not None:
            if not ValidationPatterns.validate_confidence_score(confidence):
                raise AssertionError(
                    f"Invalid confidence score: {confidence}",
                    {
                        "context": context,
                        "confidence": confidence,
                        "expected_platform": expected_platform
                    }
                )
            
            if confidence < minimum_confidence:
                raise AssertionError(
                    f"Confidence {confidence} below minimum {minimum_confidence}",
                    {
                        "context": context,
                        "confidence": confidence,
                        "minimum_confidence": minimum_confidence,
                        "expected_platform": expected_platform
                    }
                )
        
        logger.info(f"{context}: Successfully detected {expected_platform} with confidence {confidence}")
    
    @staticmethod
    def assert_confidence_level(
        result: Dict[str, Any], 
        min_confidence: float = 0.5,
        max_confidence: float = 1.0,
        context: str = "confidence_validation"
    ):
        """
        Assert that confidence level meets requirements with detailed validation.
        
        Args:
            result: The agent result to validate
            min_confidence: Minimum acceptable confidence
            max_confidence: Maximum acceptable confidence  
            context: Test context for error reporting
        """
        confidence_fields = [
            "confidence", "orchestrator_confidence", "analysis_confidence", 
            "extraction_confidence", "synthesis_confidence"
        ]
        
        confidence = None
        confidence_field = None
        
        for field in confidence_fields:
            if field in result:
                confidence = result[field]
                confidence_field = field
                break
        
        if confidence is None:
            available_fields = list(result.keys())
            raise AssertionError(
                f"No confidence field found. Expected one of: {confidence_fields}",
                {
                    "context": context,
                    "available_fields": available_fields,
                    "min_confidence": min_confidence
                }
            )
        
        # Validate confidence format
        if not ValidationPatterns.validate_confidence_score(confidence):
            raise AssertionError(
                f"Invalid confidence format: {confidence} (type: {type(confidence)})",
                {
                    "context": context,
                    "confidence": confidence,
                    "confidence_field": confidence_field
                }
            )
        
        # Check confidence range
        if confidence < min_confidence:
            raise AssertionError(
                f"Confidence {confidence} below minimum {min_confidence}",
                {
                    "context": context,
                    "confidence": confidence,
                    "min_confidence": min_confidence,
                    "confidence_field": confidence_field
                }
            )
        
        if confidence > max_confidence:
            raise AssertionError(
                f"Confidence {confidence} above maximum {max_confidence}",
                {
                    "context": context,
                    "confidence": confidence,
                    "max_confidence": max_confidence,
                    "confidence_field": confidence_field
                }
            )
        
        logger.info(f"{context}: Confidence {confidence} within acceptable range [{min_confidence}, {max_confidence}]")
    
    @staticmethod
    def assert_worker_assignments(
        result: Dict[str, Any], 
        min_assignments: int = 1,
        max_assignments: int = 10,
        validate_structure: bool = True,
        context: str = "worker_assignments"
    ):
        """
        Assert that appropriate worker assignments were created with validation.
        
        Args:
            result: The agent result to validate
            min_assignments: Minimum number of assignments expected
            max_assignments: Maximum number of assignments allowed
            validate_structure: Whether to validate assignment structure
            context: Test context for error reporting
        """
        assignments_fields = ["worker_assignments", "assignments", "workers", "task_assignments"]
        
        assignments = None
        assignments_field = None
        
        for field in assignments_fields:
            if field in result:
                assignments = result[field]
                assignments_field = field
                break
        
        if assignments is None:
            available_fields = list(result.keys())
            raise AssertionError(
                f"No worker assignments found. Expected one of: {assignments_fields}",
                {
                    "context": context,
                    "available_fields": available_fields,
                    "min_assignments": min_assignments
                }
            )
        
        # Validate assignments format
        if not isinstance(assignments, list):
            raise AssertionError(
                f"Worker assignments must be a list, got {type(assignments)}",
                {
                    "context": context,
                    "assignments": assignments,
                    "assignments_field": assignments_field
                }
            )
        
        # Check assignment count
        assignment_count = len(assignments)
        
        if assignment_count < min_assignments:
            raise AssertionError(
                f"Expected at least {min_assignments} worker assignments, got {assignment_count}",
                {
                    "context": context,
                    "assignment_count": assignment_count,
                    "min_assignments": min_assignments,
                    "assignments": assignments
                }
            )
        
        if assignment_count > max_assignments:
            raise AssertionError(
                f"Too many worker assignments: {assignment_count} (max: {max_assignments})",
                {
                    "context": context,
                    "assignment_count": assignment_count,
                    "max_assignments": max_assignments
                }
            )
        
        # Validate assignment structure if requested
        if validate_structure:
            invalid_assignments = []
            
            for i, assignment in enumerate(assignments):
                if not isinstance(assignment, dict):
                    invalid_assignments.append(f"Assignment {i}: not a dict")
                elif not ValidationPatterns.validate_worker_assignment(assignment):
                    missing_fields = []
                    required_fields = ["worker_type", "platform", "priority"]
                    for field in required_fields:
                        if field not in assignment:
                            missing_fields.append(field)
                    invalid_assignments.append(f"Assignment {i}: missing fields {missing_fields}")
            
            if invalid_assignments:
                raise AssertionError(
                    f"Invalid worker assignment structure: {invalid_assignments}",
                    {
                        "context": context,
                        "invalid_assignments": invalid_assignments,
                        "assignments": assignments
                    }
                )
        
        logger.info(f"{context}: Validated {assignment_count} worker assignments")
    
    @staticmethod
    def assert_complexity_assessment(
        result: Dict[str, Any],
        expected_complexity: Optional[str] = None,
        allow_unknown: bool = True,
        context: str = "complexity_assessment"
    ):
        """
        Assert that complexity assessment is valid and reasonable.
        
        Args:
            result: The agent result to validate
            expected_complexity: Expected complexity level (optional)
            allow_unknown: Whether to allow unknown complexity
            context: Test context for error reporting
        """
        complexity_fields = ["complexity_assessment", "complexity_level", "complexity"]
        
        complexity = None
        complexity_field = None
        
        for field in complexity_fields:
            if field in result:
                complexity = result[field]
                complexity_field = field
                break
            
            # Check in nested structures
            if "orchestrator_decision" in result:
                decision = result["orchestrator_decision"]
                if hasattr(decision, field):
                    complexity = getattr(decision, field)
                    complexity_field = f"orchestrator_decision.{field}"
                    break
                elif isinstance(decision, dict) and field in decision:
                    complexity = decision[field]
                    complexity_field = f"orchestrator_decision.{field}"
                    break
        
        if complexity is None:
            if expected_complexity is not None:
                available_fields = list(result.keys())
                raise AssertionError(
                    f"No complexity assessment found. Expected one of: {complexity_fields}",
                    {
                        "context": context,
                        "available_fields": available_fields,
                        "expected_complexity": expected_complexity
                    }
                )
            else:
                return  # Complexity assessment not required
        
        # Validate complexity format
        if not ValidationPatterns.validate_complexity_level(complexity):
            valid_levels = ["low", "medium", "high"] + (["unknown"] if allow_unknown else [])
            raise AssertionError(
                f"Invalid complexity level: {complexity}. Valid levels: {valid_levels}",
                {
                    "context": context,
                    "complexity": complexity,
                    "complexity_field": complexity_field,
                    "valid_levels": valid_levels
                }
            )
        
        # Check expected complexity if specified
        if expected_complexity is not None:
            if complexity.lower() != expected_complexity.lower():
                raise AssertionError(
                    f"Expected complexity '{expected_complexity}', got '{complexity}'",
                    {
                        "context": context,
                        "expected_complexity": expected_complexity,
                        "actual_complexity": complexity,
                        "complexity_field": complexity_field
                    }
                )
        
        logger.info(f"{context}: Complexity assessment '{complexity}' is valid")
    
    @staticmethod
    def assert_execution_performance(
        execution_time: float,
        max_time: float = 60.0,
        memory_increase: float = None,
        max_memory: float = 100.0,
        context: str = "performance"
    ):
        """
        Assert that execution performance meets requirements.
        
        Args:
            execution_time: Actual execution time in seconds
            max_time: Maximum allowed execution time
            memory_increase: Memory increase in MB (optional)
            max_memory: Maximum allowed memory increase
            context: Test context for error reporting
        """
        # Validate execution time
        if execution_time > max_time:
            raise AssertionError(
                f"Execution time {execution_time:.2f}s exceeds maximum {max_time}s",
                {
                    "context": context,
                    "execution_time": execution_time,
                    "max_time": max_time
                }
            )
        
        # Validate memory usage if provided
        if memory_increase is not None and memory_increase > max_memory:
            logger.warning(
                f"{context}: Memory increase {memory_increase:.2f}MB exceeds threshold {max_memory}MB"
            )
        
        logger.info(f"{context}: Performance within acceptable limits (time: {execution_time:.2f}s)")
    
    @staticmethod
    def assert_state_structure(
        state: Dict[str, Any],
        required_fields: List[str],
        optional_fields: List[str] = None,
        context: str = "state_structure"
    ):
        """
        Assert that state has required structure with detailed validation.
        
        Args:
            state: The state to validate
            required_fields: Fields that must be present
            optional_fields: Fields that may be present (for documentation)
            context: Test context for error reporting
        """
        if not isinstance(state, dict):
            raise AssertionError(
                f"State must be a dictionary, got {type(state)}",
                {
                    "context": context,
                    "state_type": type(state)
                }
            )
        
        # Check required fields
        missing_fields = ValidationPatterns.validate_state_structure(state, required_fields)
        
        if missing_fields:
            available_fields = list(state.keys())
            raise AssertionError(
                f"Missing required state fields: {missing_fields}",
                {
                    "context": context,
                    "missing_fields": missing_fields,
                    "required_fields": required_fields,
                    "available_fields": available_fields
                }
            )
        
        logger.info(f"{context}: State structure validated with {len(state)} fields")


class AssertionHelpers:
    """
    Helper methods for common x2a testing assertions.
    
    Provides convenience methods that combine multiple validation patterns.
    """
    
    @staticmethod
    def assert_agent_output_complete(
        result: Dict[str, Any],
        agent_type: str,
        expected_platform: str = None,
        min_confidence: float = 0.5
    ):
        """
        Complete validation of agent output including all common checks.
        
        Args:
            result: Agent result to validate
            agent_type: Type of agent for context
            expected_platform: Expected platform detection (optional)
            min_confidence: Minimum confidence threshold
        """
        context = f"{agent_type}_complete_validation"
        
        # Validate basic structure
        assert isinstance(result, dict), f"{agent_type} must return dictionary result"
        
        # Platform detection (if expected)
        if expected_platform:
            TestPatterns.assert_platform_detection(result, expected_platform, min_confidence, context)
        
        # Confidence level
        TestPatterns.assert_confidence_level(result, min_confidence, context=context)
        
        # State preservation (check for no data loss)
        assert len(result) > 0, f"{agent_type} result should not be empty"
        
        logger.info(f"{context}: Complete validation passed")
    
    @staticmethod
    def assert_workflow_state_valid(
        state: Dict[str, Any],
        workflow_stage: str,
        required_agents: List[str] = None
    ):
        """
        Validate workflow state at specific stage.
        
        Args:
            state: Workflow state to validate
            workflow_stage: Expected workflow stage
            required_agents: Agents that should have completed by this stage
        """
        context = f"workflow_validation_{workflow_stage}"
        
        # Basic workflow fields
        required_fields = ["workflow_id", "workflow_stage", "input_code"]
        TestPatterns.assert_state_structure(state, required_fields, context=context)
        
        # Check workflow stage
        actual_stage = state.get("workflow_stage")
        if actual_stage != workflow_stage:
            raise AssertionError(
                f"Expected workflow stage '{workflow_stage}', got '{actual_stage}'",
                {
                    "context": context,
                    "expected_stage": workflow_stage,
                    "actual_stage": actual_stage
                }
            )
        
        # Check agent completion if specified
        if required_agents:
            workflow_history = state.get("workflow_history", [])
            completed_agents = [entry.get("agent") for entry in workflow_history]
            
            missing_agents = [agent for agent in required_agents if agent not in completed_agents]
            if missing_agents:
                raise AssertionError(
                    f"Required agents not completed: {missing_agents}",
                    {
                        "context": context,
                        "required_agents": required_agents,
                        "completed_agents": completed_agents,
                        "missing_agents": missing_agents
                    }
                )
        
        logger.info(f"{context}: Workflow state validated for stage '{workflow_stage}'")
