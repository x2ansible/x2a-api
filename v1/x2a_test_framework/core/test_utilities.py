"""
x2a Test Utilities

Enterprise-grade test utilities for x2a LangGraph agent testing.
Provides comprehensive utilities for LangGraph testing, async execution,
performance monitoring, and test debugging.

Key Features:
- LangGraph-specific testing patterns and utilities
- Async test execution with proper error handling
- Performance monitoring and metrics collection
- Test debugging and introspection tools
- Mock builders for agents and LLMs
- Test isolation and cleanup utilities
- Enterprise logging and audit trails
"""

import asyncio
import time
import logging
import traceback
from typing import Dict, Any, List, Optional, Callable, Union, Tuple
from unittest.mock import Mock, patch, MagicMock
from contextlib import asynccontextmanager
from datetime import datetime
import json

logger = logging.getLogger("x2a_test_framework.utilities")


class TestMetrics:
    """
    Comprehensive metrics collection for x2a tests.
    
    Tracks performance, success rates, and debugging information
    across all test executions.
    """
    
    def __init__(self):
        self.metrics = {}
        self.test_history = []
        self.performance_data = []
        self.error_log = []
        
    def start_test(self, test_name: str, test_type: str = "unit") -> str:
        """Start metrics collection for a test."""
        test_id = f"{test_name}_{int(time.time())}"
        
        self.metrics[test_id] = {
            "test_name": test_name,
            "test_type": test_type,
            "start_time": time.time(),
            "status": "running",
            "metrics": {}
        }
        
        logger.debug(f"Started metrics collection for test: {test_name}")
        return test_id
    
    def end_test(self, test_id: str, status: str = "passed", error_info: str = None):
        """End metrics collection for a test."""
        if test_id in self.metrics:
            end_time = time.time()
            test_data = self.metrics[test_id]
            
            test_data.update({
                "end_time": end_time,
                "duration": end_time - test_data["start_time"],
                "status": status,
                "error_info": error_info
            })
            
            # Add to history
            self.test_history.append(test_data.copy())
            
            # Log performance data
            if status == "passed":
                self.performance_data.append({
                    "test_name": test_data["test_name"],
                    "duration": test_data["duration"],
                    "timestamp": end_time
                })
            elif status == "failed" and error_info:
                self.error_log.append({
                    "test_name": test_data["test_name"],
                    "error": error_info,
                    "timestamp": end_time
                })
            
            logger.debug(f"Completed metrics collection for test: {test_data['test_name']}")
    
    def add_metric(self, test_id: str, metric_name: str, value: Any):
        """Add a specific metric to a test."""
        if test_id in self.metrics:
            self.metrics[test_id]["metrics"][metric_name] = value
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary."""
        if not self.performance_data:
            return {"message": "No performance data available"}
        
        durations = [data["duration"] for data in self.performance_data]
        
        return {
            "total_tests": len(self.performance_data),
            "total_duration": sum(durations),
            "average_duration": sum(durations) / len(durations),
            "min_duration": min(durations),
            "max_duration": max(durations),
            "success_rate": len(self.performance_data) / (len(self.performance_data) + len(self.error_log)) * 100,
            "total_errors": len(self.error_log)
        }
    
    def export_metrics(self, format: str = "json") -> str:
        """Export metrics in specified format."""
        export_data = {
            "test_history": self.test_history,
            "performance_data": self.performance_data,
            "error_log": self.error_log,
            "summary": self.get_performance_summary(),
            "export_timestamp": datetime.now().isoformat()
        }
        
        if format == "json":
            return json.dumps(export_data, indent=2)
        else:
            return str(export_data)


class AsyncTestRunner:
    """
    Enterprise-grade async test runner for x2a LangGraph tests.
    
    Provides robust async test execution with timeout handling,
    error recovery, and comprehensive logging.
    """
    
    def __init__(self, default_timeout: float = 30.0):
        self.default_timeout = default_timeout
        self.metrics = TestMetrics()
        self.active_tests = {}
        
    async def run_with_timeout(
        self,
        coro: Callable,
        timeout: float = None,
        test_name: str = "unknown_test",
        context: Dict[str, Any] = None
    ) -> Any:
        """
        Run async function with timeout and comprehensive error handling.
        
        Args:
            coro: Coroutine to run
            timeout: Timeout in seconds (uses default if None)
            test_name: Name of test for logging
            context: Additional context for debugging
            
        Returns:
            Result of the coroutine
            
        Raises:
            asyncio.TimeoutError: If execution times out
            Exception: Any other errors from the coroutine
        """
        timeout = timeout or self.default_timeout
        test_id = self.metrics.start_test(test_name, "async")
        
        try:
            logger.info(f"Running async test '{test_name}' with {timeout}s timeout")
            
            # Run with timeout
            result = await asyncio.wait_for(coro, timeout=timeout)
            
            self.metrics.end_test(test_id, "passed")
            logger.info(f"Async test '{test_name}' completed successfully")
            
            return result
            
        except asyncio.TimeoutError:
            error_msg = f"Test '{test_name}' timed out after {timeout}s"
            logger.error(error_msg)
            self.metrics.end_test(test_id, "timeout", error_msg)
            raise
            
        except Exception as e:
            error_msg = f"Test '{test_name}' failed: {str(e)}"
            logger.error(error_msg)
            logger.debug(f"Full traceback: {traceback.format_exc()}")
            self.metrics.end_test(test_id, "failed", error_msg)
            raise
    
    async def run_with_retry(
        self,
        coro: Callable,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        test_name: str = "unknown_test"
    ) -> Any:
        """
        Run async function with retry logic for flaky tests.
        
        Args:
            coro: Coroutine to run
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
            test_name: Name of test for logging
            
        Returns:
            Result of successful execution
            
        Raises:
            Exception: Last exception if all retries fail
        """
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                logger.debug(f"Running '{test_name}' attempt {attempt + 1}/{max_retries + 1}")
                return await self.run_with_timeout(coro, test_name=f"{test_name}_attempt_{attempt + 1}")
                
            except Exception as e:
                last_exception = e
                
                if attempt < max_retries:
                    logger.warning(f"Test '{test_name}' attempt {attempt + 1} failed, retrying in {retry_delay}s: {str(e)}")
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error(f"Test '{test_name}' failed after {max_retries + 1} attempts")
        
        raise last_exception
    
    @asynccontextmanager
    async def test_isolation(self, test_name: str):
        """
        Context manager for test isolation and cleanup.
        
        Ensures proper setup and teardown for each test.
        """
        test_id = self.metrics.start_test(test_name, "isolated")
        setup_success = False
        
        try:
            logger.debug(f"Setting up isolated environment for test: {test_name}")
            
            # Test setup
            self.active_tests[test_name] = {
                "start_time": time.time(),
                "test_id": test_id
            }
            
            setup_success = True
            yield
            
            # Test completed successfully
            self.metrics.end_test(test_id, "passed")
            logger.debug(f"Test isolation completed successfully for: {test_name}")
            
        except Exception as e:
            error_msg = f"Test '{test_name}' failed in isolation: {str(e)}"
            logger.error(error_msg)
            self.metrics.end_test(test_id, "failed", error_msg)
            raise
            
        finally:
            # Cleanup
            if test_name in self.active_tests:
                del self.active_tests[test_name]
            
            if setup_success:
                logger.debug(f"Cleaned up isolated environment for test: {test_name}")


class LangGraphTestMixin:
    """
    Enhanced LangGraph testing mixin with enterprise features.
    
    Provides comprehensive utilities for testing LangGraph agents and nodes
    with advanced debugging, performance monitoring, and validation.
    """
    
    def __init__(self):
        self.test_runner = AsyncTestRunner()
        self.metrics = TestMetrics()
        
    def assert_valid_state_output(
        self, 
        state: Dict[str, Any], 
        required_fields: List[str],
        context: str = "state_validation"
    ):
        """
        Enhanced state validation with detailed error reporting.
        
        Args:
            state: State to validate
            required_fields: Fields that must be present
            context: Context for error reporting
        """
        if not isinstance(state, dict):
            raise AssertionError(
                f"{context}: State must be a dictionary, got {type(state).__name__}. "
                f"State content: {str(state)[:200]}..."
            )
        
        missing_fields = []
        invalid_fields = {}
        
        for field in required_fields:
            if field not in state:
                missing_fields.append(field)
            elif state[field] is None:
                invalid_fields[field] = "Field is None"
        
        if missing_fields or invalid_fields:
            available_fields = list(state.keys())
            error_msg = f"{context}: Validation failed. "
            
            if missing_fields:
                error_msg += f"Missing fields: {missing_fields}. "
            if invalid_fields:
                error_msg += f"Invalid fields: {invalid_fields}. "
            
            error_msg += f"Available fields: {available_fields}"
            
            raise AssertionError(error_msg)
        
        logger.debug(f"{context}: State validation passed for {len(required_fields)} required fields")
    
    def assert_valid_structured_output(
        self, 
        output: Any, 
        expected_type: type,
        context: str = "structured_output_validation"
    ):
        """
        Enhanced structured output validation with detailed Pydantic checking.
        
        Args:
            output: Output to validate
            expected_type: Expected Pydantic model type
            context: Context for error reporting
        """
        if not isinstance(output, expected_type):
            raise AssertionError(
                f"{context}: Output must be of type {expected_type.__name__}, "
                f"got {type(output).__name__}. Output: {str(output)[:200]}..."
            )
        
        # Validate Pydantic model fields
        missing_fields = []
        field_errors = {}
        
        for field_name, field_info in expected_type.__fields__.items():
            if not hasattr(output, field_name):
                missing_fields.append(field_name)
            else:
                field_value = getattr(output, field_name)
                
                # Basic type validation
                if field_info.required and field_value is None:
                    field_errors[field_name] = "Required field is None"
        
        if missing_fields or field_errors:
            available_attrs = [attr for attr in dir(output) if not attr.startswith('_')]
            error_msg = f"{context}: Pydantic validation failed. "
            
            if missing_fields:
                error_msg += f"Missing fields: {missing_fields}. "
            if field_errors:
                error_msg += f"Field errors: {field_errors}. "
            
            error_msg += f"Available attributes: {available_attrs}"
            
            raise AssertionError(error_msg)
        
        logger.debug(f"{context}: Structured output validation passed for {expected_type.__name__}")
    
    async def run_node_with_comprehensive_monitoring(
        self,
        node_func: Callable,
        state: Dict[str, Any],
        timeout: float = 30.0,
        test_name: str = "node_test",
        validate_output: bool = True,
        expected_fields: List[str] = None
    ) -> Dict[str, Any]:
        """
        Run LangGraph node with comprehensive monitoring and validation.
        
        Args:
            node_func: Node function to execute
            state: Input state for the node
            timeout: Execution timeout
            test_name: Test name for logging
            validate_output: Whether to validate output structure
            expected_fields: Fields expected in output (if validate_output=True)
            
        Returns:
            Node execution result with performance metrics
        """
        # Pre-execution validation
        if not callable(node_func):
            raise ValueError(f"node_func must be callable, got {type(node_func)}")
        
        if not isinstance(state, dict):
            raise ValueError(f"state must be a dictionary, got {type(state)}")
        
        # Run node with monitoring
        start_time = time.time()
        test_id = self.metrics.start_test(test_name, "node_execution")
        
        try:
            logger.info(f"Executing node {node_func.__name__} for test: {test_name}")
            
            # Execute node with timeout
            result = await self.test_runner.run_with_timeout(
                node_func(state),
                timeout=timeout,
                test_name=test_name
            )
            
            execution_time = time.time() - start_time
            
            # Validate output if requested
            if validate_output:
                if expected_fields:
                    self.assert_valid_state_output(
                        result, expected_fields, 
                        context=f"{test_name}_output_validation"
                    )
                else:
                    # Basic validation
                    assert isinstance(result, dict), f"Node must return dict, got {type(result)}"
            
            # Add performance metrics
            self.metrics.add_metric(test_id, "execution_time", execution_time)
            self.metrics.add_metric(test_id, "input_state_size", len(str(state)))
            self.metrics.add_metric(test_id, "output_state_size", len(str(result)))
            
            self.metrics.end_test(test_id, "passed")
            
            logger.info(f"Node {node_func.__name__} completed successfully in {execution_time:.2f}s")
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"Node {node_func.__name__} failed after {execution_time:.2f}s: {str(e)}"
            
            self.metrics.add_metric(test_id, "execution_time", execution_time)
            self.metrics.add_metric(test_id, "error_type", type(e).__name__)
            self.metrics.end_test(test_id, "failed", error_msg)
            
            logger.error(error_msg)
            raise
    
    def measure_execution_performance(
        self, 
        func: Callable, 
        *args, 
        **kwargs
    ) -> Tuple[Any, Dict[str, float]]:
        """
        Enhanced performance measurement with detailed metrics.
        
        Returns:
            Tuple of (result, performance_metrics)
        """
        start_time = time.time()
        start_memory = self._get_memory_usage()
        
        try:
            result = func(*args, **kwargs)
            success = True
        except Exception as e:
            result = e
            success = False
        
        end_time = time.time()
        end_memory = self._get_memory_usage()
        
        performance_metrics = {
            "execution_time": end_time - start_time,
            "memory_delta": end_memory - start_memory,
            "start_memory": start_memory,
            "end_memory": end_memory,
            "peak_memory": max(start_memory, end_memory),
            "success": success
        }
        
        if not success:
            performance_metrics["error_type"] = type(result).__name__
        
        return result, performance_metrics
    
    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB with error handling."""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024  # Convert to MB
        except ImportError:
            logger.debug("psutil not available, memory monitoring disabled")
            return 0.0
        except Exception as e:
            logger.debug(f"Memory monitoring failed: {e}")
            return 0.0
    
    def debug_state_structure(self, state: Dict[str, Any], context: str = "debug"):
        """Debug utility to inspect state structure."""
        logger.debug(f"{context}: State structure analysis")
        logger.debug(f"  - Type: {type(state)}")
        logger.debug(f"  - Size: {len(state)} fields")
        logger.debug(f"  - Fields: {list(state.keys())}")
        
        for key, value in state.items():
            value_type = type(value).__name__
            value_size = len(str(value))
            logger.debug(f"  - {key}: {value_type} (size: {value_size})")
    
    def create_test_isolation_context(self, test_name: str):
        """Create isolation context for comprehensive test management."""
        return self.test_runner.test_isolation(test_name)


class MockAgentBuilder:
    """
    Enterprise-grade mock builder for x2a agents and LLMs.
    
    Provides realistic mocks that behave like real agents while being
    deterministic and fast for testing.
    """
    
    @staticmethod
    def create_mock_agent(
        agent_type: str = "orchestrator",
        expected_tools: List[str] = None,
        mock_responses: Dict[str, Any] = None
    ) -> Mock:
        """
        Create a mock agent with realistic behavior.
        
        Args:
            agent_type: Type of agent to mock
            expected_tools: Tools the agent should have
            mock_responses: Predefined responses for specific inputs
            
        Returns:
            Mock agent with configured behavior
        """
        mock_agent = Mock()
        mock_responses = mock_responses or {}
        
        # Configure basic agent methods
        mock_agent.invoke = Mock(return_value=mock_responses.get("invoke_result", {}))
        mock_agent.ainvoke = Mock(return_value=mock_responses.get("ainvoke_result", {}))
        mock_agent.get_graph = Mock(return_value=Mock())
        
        # Configure agent-specific behavior
        if agent_type == "orchestrator":
            default_response = {
                "orchestrator_decision": Mock(
                    detected_platforms=["chef"],
                    complexity_assessment="medium",
                    worker_assignments=[
                        {"worker_type": "universal_extractor", "platform": "chef", "priority": 1}
                    ],
                    confidence=0.8
                ),
                "worker_assignments": [
                    {"worker_type": "universal_extractor", "platform": "chef", "priority": 1}
                ],
                "orchestrator_confidence": 0.8,
                "orchestrator_reasoning": "Mock orchestrator reasoning"
            }
            mock_agent.ainvoke.return_value = mock_responses.get("orchestrator_result", default_response)
        
        logger.debug(f"Created mock {agent_type} agent with {len(expected_tools or [])} tools")
        return mock_agent
    
    @staticmethod
    def create_mock_llm_response(
        platform: str = "chef",
        confidence: float = 0.8,
        complexity: str = "medium"
    ) -> Dict[str, Any]:
        """
        Create realistic mock LLM response.
        
        Args:
            platform: Platform to include in response
            confidence: Confidence level for the response
            complexity: Complexity assessment
            
        Returns:
            Mock LLM response structure
        """
        return {
            "detected_platforms": [platform],
            "complexity_assessment": complexity,
            "processing_strategy": f"standard_{platform}_analysis",
            "estimated_duration": 15,
            "confidence": confidence,
            "reasoning": f"Mock analysis detected {platform} with {complexity} complexity",
            "timestamp": datetime.now().isoformat()
        }
    
    @staticmethod
    def create_mock_tool_response(
        tool_name: str,
        success: bool = True,
        response_data: Dict[str, Any] = None
    ) -> Mock:
        """
        Create mock tool response.
        
        Args:
            tool_name: Name of the tool being mocked
            success: Whether the tool execution was successful
            response_data: Data to include in the response
            
        Returns:
            Mock tool response
        """
        response_data = response_data or {}
        
        mock_response = Mock()
        mock_response.name = tool_name
        mock_response.success = success
        
        if success:
            mock_response.content = response_data
        else:
            mock_response.error = response_data.get("error", "Mock tool error")
        
        logger.debug(f"Created mock response for tool: {tool_name} (success: {success})")
        return mock_response
