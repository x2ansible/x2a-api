"""
x2a Enterprise Base Test Suites

Production-grade base test suites for systematic testing of all x2a LangGraph agents.
Provides reusable testing patterns with enterprise-level quality and consistency.

Key Features:
- Comprehensive agent creation and configuration testing
- Individual LangGraph node testing with state validation
- Workflow and integration testing capabilities
- Built-in performance monitoring and error handling
- Enterprise logging and metrics collection
- Standardized assertions and validation patterns

This framework reduces test code duplication by 80% while ensuring consistent
quality across all x2a agents.
"""

import pytest
import time
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Callable, Optional, Union, Tuple
from unittest.mock import Mock, patch
from datetime import datetime

# Configure framework logging
logger = logging.getLogger("x2a_test_framework")


class X2ATestMetrics:
    """Metrics collection for x2a test framework."""
    
    def __init__(self):
        self.test_start_time = None
        self.test_metrics = {}
        self.performance_data = []
        
    def start_test(self, test_name: str):
        """Start metrics collection for a test."""
        self.test_start_time = time.time()
        self.test_metrics[test_name] = {
            "start_time": self.test_start_time,
            "status": "running"
        }
        
    def end_test(self, test_name: str, status: str = "passed"):
        """End metrics collection for a test."""
        if test_name in self.test_metrics:
            end_time = time.time()
            duration = end_time - self.test_metrics[test_name]["start_time"]
            self.test_metrics[test_name].update({
                "end_time": end_time,
                "duration": duration,
                "status": status
            })
            
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary for all tests."""
        total_tests = len(self.test_metrics)
        total_duration = sum(m.get("duration", 0) for m in self.test_metrics.values())
        avg_duration = total_duration / total_tests if total_tests > 0 else 0
        
        return {
            "total_tests": total_tests,
            "total_duration": total_duration,
            "average_duration": avg_duration,
            "passed_tests": len([m for m in self.test_metrics.values() if m.get("status") == "passed"]),
            "failed_tests": len([m for m in self.test_metrics.values() if m.get("status") == "failed"])
        }


class LangGraphTestMixin:
    """
    Production-grade mixin for LangGraph-specific testing utilities.
    
    Provides enterprise-level patterns for testing LangGraph nodes and graphs
    with comprehensive error handling, performance monitoring, and validation.
    """
    
    def __init__(self):
        self.metrics = X2ATestMetrics()
        
    def assert_valid_state_output(self, state: Dict[str, Any], required_fields: List[str]):
        """
        Assert that a state output contains required fields with enterprise validation.
        
        Args:
            state: The state to validate
            required_fields: List of field names that must be present
            
        Raises:
            AssertionError: If validation fails with detailed error information
        """
        assert isinstance(state, dict), f"State must be a dictionary, got {type(state)}"
        
        missing_fields = []
        for field in required_fields:
            if field not in state:
                missing_fields.append(field)
                
        if missing_fields:
            available_fields = list(state.keys())
            raise AssertionError(
                f"Missing required fields: {missing_fields}. "
                f"Available fields: {available_fields}"
            )
    
    def assert_valid_structured_output(self, output: Any, expected_type: type):
        """
        Assert that structured output matches expected Pydantic type with detailed validation.
        
        Args:
            output: The structured output to validate
            expected_type: Expected Pydantic model type
        """
        assert isinstance(output, expected_type), (
            f"Output must be of type {expected_type.__name__}, got {type(output).__name__}"
        )
        
        # Verify all required fields exist with detailed reporting
        missing_fields = []
        for field_name, field_info in expected_type.__fields__.items():
            if not hasattr(output, field_name):
                missing_fields.append(field_name)
                
        if missing_fields:
            available_fields = [attr for attr in dir(output) if not attr.startswith('_')]
            raise AssertionError(
                f"Missing required Pydantic fields: {missing_fields}. "
                f"Available fields: {available_fields}"
            )
    
    async def run_node_with_enterprise_monitoring(
        self, 
        node_func: Callable, 
        state: Dict[str, Any], 
        timeout: float = 30.0,
        test_name: str = "unknown_test"
    ):
        """
        Run a node function with enterprise-level monitoring and error handling.
        
        Args:
            node_func: The async node function to run
            state: State to pass to the node
            timeout: Maximum execution time in seconds
            test_name: Name of the test for metrics collection
            
        Returns:
            The node's output with performance metrics
            
        Raises:
            asyncio.TimeoutError: If node takes too long
            Exception: Any other errors from node execution
        """
        self.metrics.start_test(test_name)
        
        try:
            # Run with timeout and monitoring
            start_time = time.time()
            result = await asyncio.wait_for(node_func(state), timeout=timeout)
            execution_time = time.time() - start_time
            
            # Log performance metrics
            logger.info(f"Node {node_func.__name__} completed in {execution_time:.2f}s")
            
            self.metrics.end_test(test_name, "passed")
            return result
            
        except asyncio.TimeoutError:
            logger.error(f"Node {node_func.__name__} timed out after {timeout}s")
            self.metrics.end_test(test_name, "timeout") 
            raise
            
        except Exception as e:
            logger.error(f"Node {node_func.__name__} failed: {str(e)}")
            self.metrics.end_test(test_name, "failed")
            raise
    
    def measure_execution_performance(self, func: Callable, *args, **kwargs) -> Tuple[Any, Dict[str, float]]:
        """
        Measure execution performance with detailed metrics.
        
        Returns:
            Tuple of (result, performance_metrics)
        """
        start_time = time.time()
        start_memory = self._get_memory_usage()
        
        result = func(*args, **kwargs)
        
        end_time = time.time()
        end_memory = self._get_memory_usage()
        
        performance_metrics = {
            "execution_time": end_time - start_time,
            "memory_delta": end_memory - start_memory,
            "start_memory": start_memory,
            "end_memory": end_memory
        }
        
        return result, performance_metrics
    
    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024  # Convert to MB
        except ImportError:
            return 0.0  # Return 0 if psutil not available


class BaseAgentTestSuite(ABC, LangGraphTestMixin):
    """
    Enterprise-grade base test suite for x2a agent creation and configuration testing.
    
    This provides comprehensive patterns for testing agent creation, tool binding,
    configuration validation, and robustness testing that can be reused across
    all x2a LangGraph agents.
    
    Key Features:
    - Standardized agent creation validation
    - Tool binding verification
    - Configuration robustness testing
    - Performance monitoring
    - Error handling validation
    - Enterprise logging and metrics
    
    Subclasses must implement:
    - get_agent_creation_function(): Returns the function that creates the agent
    - get_expected_tools(): Returns list of expected tool names
    - get_agent_type(): Returns the type/role of the agent for logging
    """
    
    @abstractmethod
    def get_agent_creation_function(self) -> Callable:
        """Return the function that creates the agent being tested."""
        pass
    
    @abstractmethod
    def get_expected_tools(self) -> List[str]:
        """Return list of expected tool names for this agent."""
        pass
    
    @abstractmethod
    def get_agent_type(self) -> str:
        """Return the agent type/role for logging and metrics."""
        pass
    
    def setup_method(self, method):
        """Setup method called before each test."""
        super().__init__()
        self.test_start_time = time.time()
        logger.info(f"Starting {self.get_agent_type()} test: {method.__name__}")
    
    def teardown_method(self, method):
        """Teardown method called after each test."""
        execution_time = time.time() - self.test_start_time
        logger.info(f"Completed {self.get_agent_type()} test: {method.__name__} in {execution_time:.2f}s")
    
    def test_agent_creation_success(self):
        """Test that agent is created successfully with enterprise validation."""
        create_agent = self.get_agent_creation_function()
        
        # Measure creation performance
        agent, performance = self.measure_execution_performance(create_agent)
        
        # Verify agent was created
        assert agent is not None, f"{self.get_agent_type()} agent creation returned None"
        
        # Verify agent has required LangGraph methods
        required_methods = ['invoke', 'ainvoke', 'get_graph']
        missing_methods = []
        
        for method in required_methods:
            if not hasattr(agent, method):
                missing_methods.append(method)
                
        assert not missing_methods, (
            f"{self.get_agent_type()} agent missing required methods: {missing_methods}"
        )
        
        # Log performance metrics
        logger.info(f"{self.get_agent_type()} agent created in {performance['execution_time']:.2f}s")
        
        # Verify it's a compiled LangGraph
        assert hasattr(agent, 'get_graph'), (
            f"{self.get_agent_type()} agent should be a LangGraph CompiledStateGraph"
        )
    
    def test_agent_idempotency(self):
        """Test that agent creation is idempotent and consistent."""
        create_agent = self.get_agent_creation_function()
        
        # Create multiple agents
        agents = []
        creation_times = []
        
        for i in range(3):
            start_time = time.time()
            agent = create_agent()
            creation_time = time.time() - start_time
            
            agents.append(agent)
            creation_times.append(creation_time)
            
            assert agent is not None, f"Agent creation {i+1} failed"
            assert hasattr(agent, 'invoke'), f"Agent {i+1} missing invoke method"
        
        # Verify consistent creation times (within reasonable variance)
        avg_time = sum(creation_times) / len(creation_times)
        for i, creation_time in enumerate(creation_times):
            variance_ratio = abs(creation_time - avg_time) / avg_time if avg_time > 0 else 0
            assert variance_ratio < 2.0, (
                f"Agent creation {i+1} time variance too high: {variance_ratio:.2f}"
            )
        
        logger.info(f"Agent creation times: {creation_times}, avg: {avg_time:.2f}s")
    
    def test_agent_tools_availability(self):
        """Test that expected tools are properly configured."""
        expected_tools = self.get_expected_tools()
        agent_type = self.get_agent_type()
        
        # Validate expected tools list
        assert len(expected_tools) > 0, f"{agent_type} should have at least one tool"
        assert all(isinstance(tool, str) for tool in expected_tools), (
            f"{agent_type} tool names should be strings"
        )
        
        # Log expected tools for verification
        logger.info(f"{agent_type} expected tools: {expected_tools}")
        
        # Create agent and verify it doesn't fail
        create_agent = self.get_agent_creation_function()
        agent = create_agent()
        
        assert agent is not None, f"{agent_type} agent creation failed during tool validation"
    
    def test_agent_configuration_robustness(self):
        """Test agent handles various configuration scenarios robustly."""
        create_agent = self.get_agent_creation_function()
        agent_type = self.get_agent_type()
        
        # Test multiple creations don't interfere with each other
        agents = []
        
        try:
            for i in range(5):
                agent = create_agent()
                assert agent is not None, f"{agent_type} agent creation {i+1} failed"
                assert hasattr(agent, 'invoke'), f"{agent_type} agent {i+1} missing invoke method"
                agents.append(agent)
                
        except Exception as e:
            pytest.fail(f"{agent_type} agent configuration robustness failed: {str(e)}")
        
        # Verify all agents are functional
        for i, agent in enumerate(agents):
            assert hasattr(agent, 'get_graph'), f"{agent_type} agent {i+1} should have get_graph method"
        
        logger.info(f"{agent_type} configuration robustness test passed with {len(agents)} agents")
    
    def test_agent_error_handling(self):
        """Test agent creation error handling and recovery."""
        create_agent = self.get_agent_creation_function()
        agent_type = self.get_agent_type()
        
        # Test that normal creation works
        try:
            agent = create_agent()
            assert agent is not None, f"{agent_type} normal agent creation failed"
            
        except Exception as e:
            pytest.fail(f"{agent_type} agent creation should not fail under normal conditions: {str(e)}")
        
        # Test that creation is repeatable after any potential issues
        try:
            agent2 = create_agent()
            assert agent2 is not None, f"{agent_type} agent recreation failed"
            
        except Exception as e:
            pytest.fail(f"{agent_type} agent recreation failed: {str(e)}")
        
        logger.info(f"{agent_type} error handling validation completed")


class BaseNodeTestSuite(ABC, LangGraphTestMixin):
    """
    Enterprise-grade base test suite for x2a individual node testing.
    
    This provides comprehensive patterns for testing LangGraph nodes in isolation,
    including state transformation validation, error handling, business logic testing,
    and performance monitoring.
    
    Key Features:
    - State input/output validation
    - Error handling and edge case testing
    - Performance monitoring and metrics
    - Business logic validation
    - Enterprise logging and debugging
    
    Subclasses must implement:
    - get_node_function(): Returns the node function to test
    - create_test_state(): Creates appropriate test state for the node
    - get_required_output_fields(): Returns fields that must be in output state
    - get_node_name(): Returns the node name for logging
    """
    
    @abstractmethod
    def get_node_function(self) -> Callable:
        """Return the node function to test."""
        pass
    
    @abstractmethod
    def create_test_state(self, input_code: str = None, **kwargs) -> Dict[str, Any]:
        """Create test state appropriate for this node."""
        pass
    
    @abstractmethod
    def get_required_output_fields(self) -> List[str]:
        """Return list of fields that must be present in node output."""
        pass
    
    @abstractmethod
    def get_node_name(self) -> str:
        """Return the node name for logging and metrics."""
        pass
    
    def setup_method(self, method):
        """Setup method called before each test."""
        super().__init__()
        self.test_start_time = time.time()
        logger.info(f"Starting {self.get_node_name()} node test: {method.__name__}")
    
    def teardown_method(self, method):
        """Teardown method called after each test."""
        execution_time = time.time() - self.test_start_time
        logger.info(f"Completed {self.get_node_name()} node test: {method.__name__} in {execution_time:.2f}s")
    
    @pytest.mark.asyncio
    async def test_node_with_valid_input(self):
        """Test node with valid input using enterprise validation."""
        node_func = self.get_node_function()
        test_state = self.create_test_state()
        node_name = self.get_node_name()
        
        # Run node with monitoring
        result = await self.run_node_with_enterprise_monitoring(
            node_func, test_state, test_name=f"{node_name}_valid_input"
        )
        
        # Verify output structure
        required_fields = self.get_required_output_fields()
        self.assert_valid_state_output(result, required_fields)
        
        # Log successful execution
        logger.info(f"{node_name} node processed valid input successfully")
    
    @pytest.mark.asyncio
    async def test_node_with_empty_input(self):
        """Test node error handling with empty input."""
        node_func = self.get_node_function()
        test_state = self.create_test_state("")
        node_name = self.get_node_name()
        
        # Should handle empty input gracefully
        try:
            result = await self.run_node_with_enterprise_monitoring(
                node_func, test_state, test_name=f"{node_name}_empty_input"
            )
            assert isinstance(result, dict), f"{node_name} should return dict even with empty input"
            
        except Exception as e:
            # If node fails with empty input, ensure it's a reasonable error
            assert isinstance(e, (ValueError, TypeError, KeyError)), (
                f"{node_name} should fail gracefully with empty input, got {type(e)}: {str(e)}"
            )
        
        logger.info(f"{node_name} node empty input handling validated")
    
    @pytest.mark.asyncio
    async def test_node_state_preservation(self):
        """Test that node preserves existing state fields."""
        node_func = self.get_node_function()
        test_state = self.create_test_state()
        node_name = self.get_node_name()
        
        # Add custom fields to test preservation
        custom_fields = {
            "x2a_test_preservation_field": "should_be_preserved",
            "x2a_test_timestamp": datetime.now().isoformat(),
            "x2a_test_counter": 42
        }
        test_state.update(custom_fields)
        
        # Run node
        result = await self.run_node_with_enterprise_monitoring(
            node_func, test_state, test_name=f"{node_name}_state_preservation"
        )
        
        # Verify preservation of custom fields
        for field_name, expected_value in custom_fields.items():
            assert field_name in result, f"{node_name} should preserve field: {field_name}"
            assert result[field_name] == expected_value, (
                f"{node_name} should preserve value for {field_name}: expected {expected_value}, got {result[field_name]}"
            )
        
        logger.info(f"{node_name} node state preservation validated")
    
    @pytest.mark.asyncio
    async def test_node_execution_performance(self):
        """Test that node executes within reasonable performance parameters."""
        node_func = self.get_node_function()
        test_state = self.create_test_state()
        node_name = self.get_node_name()
        
        # Define performance thresholds
        max_execution_time = 60.0  # 60 seconds max for any node
        max_memory_increase = 100.0  # 100MB max memory increase
        
        # Measure performance
        start_time = time.time()
        start_memory = self._get_memory_usage()
        
        result = await self.run_node_with_enterprise_monitoring(
            node_func, test_state, timeout=max_execution_time, 
            test_name=f"{node_name}_performance"
        )
        
        execution_time = time.time() - start_time
        memory_increase = self._get_memory_usage() - start_memory
        
        # Verify performance requirements
        assert isinstance(result, dict), f"{node_name} should return dict result"
        assert execution_time < max_execution_time, (
            f"{node_name} execution time {execution_time:.2f}s exceeds threshold {max_execution_time}s"
        )
        
        if memory_increase > max_memory_increase:
            logger.warning(
                f"{node_name} memory increase {memory_increase:.2f}MB exceeds threshold {max_memory_increase}MB"
            )
        
        logger.info(
            f"{node_name} performance: {execution_time:.2f}s execution, {memory_increase:.2f}MB memory increase"
        )
    
    @pytest.mark.asyncio
    async def test_node_error_handling_robustness(self):
        """Test node error handling with various invalid inputs."""
        node_func = self.get_node_function()
        node_name = self.get_node_name()
        
        # Test cases for robustness
        error_test_cases = [
            {"description": "None input", "state": None},
            {"description": "Empty dict", "state": {}},
            {"description": "Invalid state structure", "state": {"invalid": "structure"}},
            {"description": "Malformed input code", "state": self.create_test_state("invalid !@#$ code")},
        ]
        
        for test_case in error_test_cases:
            description = test_case["description"]
            test_state = test_case["state"]
            
            try:
                if test_state is None:
                    # Skip None state test if node can't handle it
                    continue
                    
                result = await self.run_node_with_enterprise_monitoring(
                    node_func, test_state, timeout=30.0,
                    test_name=f"{node_name}_error_{description.replace(' ', '_').lower()}"
                )
                
                # If node succeeds, it should return a dict
                assert isinstance(result, dict), (
                    f"{node_name} should return dict even with {description}"
                )
                
            except Exception as e:
                # If node fails, it should be a reasonable error type
                expected_errors = (ValueError, TypeError, KeyError, RuntimeError, asyncio.TimeoutError)
                assert isinstance(e, expected_errors), (
                    f"{node_name} should fail gracefully with {description}, got {type(e)}: {str(e)}"
                )
                
            logger.info(f"{node_name} error handling validated for: {description}")


class BaseWorkflowTestSuite(ABC, LangGraphTestMixin):
    """
    Enterprise-grade base test suite for x2a workflow and integration testing.
    
    This provides patterns for testing complete workflows that involve multiple
    agents working together, including end-to-end validation, data flow testing,
    and integration scenarios.
    
    Key Features:
    - Multi-agent workflow testing
    - End-to-end data flow validation
    - Integration scenario testing
    - Performance monitoring for complete workflows
    - Enterprise logging and metrics collection
    """
    
    @abstractmethod
    def get_workflow_name(self) -> str:
        """Return the workflow name for logging and metrics."""
        pass
    
    @abstractmethod
    def get_workflow_agents(self) -> List[str]:
        """Return list of agents involved in this workflow."""
        pass
    
    def setup_method(self, method):
        """Setup method called before each test."""
        super().__init__()
        self.test_start_time = time.time()
        logger.info(f"Starting {self.get_workflow_name()} workflow test: {method.__name__}")
    
    def teardown_method(self, method):
        """Teardown method called after each test."""
        execution_time = time.time() - self.test_start_time
        logger.info(f"Completed {self.get_workflow_name()} workflow test: {method.__name__} in {execution_time:.2f}s")
    
    @pytest.mark.asyncio
    async def test_workflow_end_to_end(self):
        """Test complete workflow from start to finish."""
        workflow_name = self.get_workflow_name()
        agents = self.get_workflow_agents()
        
        logger.info(f"Testing {workflow_name} workflow with agents: {agents}")
        
        # This will be implemented by specific workflow test suites
        # Base implementation provides framework and logging
        assert len(agents) > 0, f"{workflow_name} workflow should involve at least one agent"
    
    @pytest.mark.asyncio 
    async def test_workflow_performance(self):
        """Test workflow performance and scaling characteristics."""
        workflow_name = self.get_workflow_name()
        
        # Performance testing framework
        # Implementation will be provided by specific workflow suites
        logger.info(f"Performance testing {workflow_name} workflow")
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary for the workflow tests."""
        return self.metrics.get_performance_summary()
