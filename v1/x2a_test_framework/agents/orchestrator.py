"""
x2a Orchestrator Agent Test Patterns

Specialized test patterns and assertions for the x2a Orchestrator Agent.
Provides comprehensive testing utilities for infrastructure analysis coordination,
worker assignment creation, and orchestration decision-making.

Key Features:
- Infrastructure analysis orchestration testing
- Worker assignment validation
- Platform detection coordination testing
- Complexity assessment validation
- Structured output schema validation
- ReAct agent orchestration behavior testing
- Tool usage validation (requirements analysis, worker assignments, etc.)
"""

import logging
from typing import Dict, Any, List, Optional, Union
import json

logger = logging.getLogger("x2a_test_framework.agents.orchestrator")


class OrchestratorTestPatterns:
    """
    Specialized test patterns for x2a Orchestrator Agent.
    
    Provides comprehensive validation patterns for orchestration decisions,
    worker assignments, and infrastructure analysis coordination.
    """
    
    @staticmethod
    def assert_successful_orchestration(
        result: Dict[str, Any],
        min_confidence: float = 0.7,
        expected_platforms: List[str] = None
    ):
        """
        Assert that orchestration completed successfully with valid decisions.
        
        Args:
            result: Orchestration result to validate
            min_confidence: Minimum expected confidence score
            expected_platforms: Expected detected platforms
        """
        assert isinstance(result, dict), f"Result must be a dictionary, got {type(result)}"
        
        # Check for orchestrator decision
        decision_fields = ['orchestrator_decision', 'decision', 'structured_decision']
        orchestrator_decision = None
        for field in decision_fields:
            if field in result:
                orchestrator_decision = result[field]
                break
        
        assert orchestrator_decision is not None, f"No orchestrator decision found. Available keys: {list(result.keys())}"
        
        # Validate decision structure
        if isinstance(orchestrator_decision, dict):
            # Check confidence
            confidence = orchestrator_decision.get('confidence')
            if confidence is not None:
                assert isinstance(confidence, (int, float)), f"Confidence must be numeric, got {type(confidence)}"
                assert 0.0 <= confidence <= 1.0, f"Confidence must be 0-1, got {confidence}"
                assert confidence >= min_confidence, f"Confidence too low: {confidence} < {min_confidence}"
            
            # Check detected platforms
            detected_platforms = orchestrator_decision.get('detected_platforms', [])
            assert isinstance(detected_platforms, list), f"Detected platforms must be list, got {type(detected_platforms)}"
            
            if expected_platforms:
                for expected_platform in expected_platforms:
                    assert expected_platform in detected_platforms, f"Expected platform '{expected_platform}' not in {detected_platforms}"
            
            # Check complexity assessment
            complexity = orchestrator_decision.get('complexity_assessment')
            if complexity:
                assert complexity.lower() in ['low', 'medium', 'high'], f"Invalid complexity: {complexity}"
        
        logger.info(f" Orchestration successful: confidence={orchestrator_decision.get('confidence')}, platforms={orchestrator_decision.get('detected_platforms', [])}")
    
    @staticmethod
    def assert_valid_worker_assignments(
        worker_assignments: List[Dict[str, Any]],
        min_assignments: int = 1,
        expected_worker_types: List[str] = None
    ):
        """
        Assert that worker assignments are valid and comprehensive.
        
        Args:
            worker_assignments: List of worker task assignments
            min_assignments: Minimum expected number of assignments
            expected_worker_types: Expected worker types to be assigned
        """
        assert isinstance(worker_assignments, list), f"Worker assignments must be list, got {type(worker_assignments)}"
        assert len(worker_assignments) >= min_assignments, f"Too few assignments: {len(worker_assignments)} < {min_assignments}"
        
        # Validate each assignment
        for i, assignment in enumerate(worker_assignments):
            assert isinstance(assignment, dict), f"Assignment {i} must be dict, got {type(assignment)}"
            
            # Check for required assignment fields
            required_fields = ['worker_type', 'platform', 'priority']
            optional_fields = ['requirements', 'estimated_duration', 'dependencies']
            
            for field in required_fields:
                assert field in assignment, f"Assignment {i} missing required field: {field}"
            
            # Validate worker type
            worker_type = assignment.get('worker_type')
            assert isinstance(worker_type, str) and worker_type, f"Assignment {i} worker_type must be non-empty string"
            
            # Validate platform
            platform = assignment.get('platform')
            assert isinstance(platform, str) and platform, f"Assignment {i} platform must be non-empty string"
            
            # Validate priority
            priority = assignment.get('priority')
            assert isinstance(priority, (int, str)), f"Assignment {i} priority must be int or string"
        
        # Check for expected worker types
        if expected_worker_types:
            assigned_types = [assignment.get('worker_type') for assignment in worker_assignments]
            for expected_type in expected_worker_types:
                assert expected_type in assigned_types, f"Expected worker type '{expected_type}' not in assignments: {assigned_types}"
        
        logger.info(f" Worker assignments valid: {len(worker_assignments)} assignments")
    
    @staticmethod
    def assert_platform_detection_accuracy(
        detected_platforms: List[str],
        input_code: str,
        expected_accuracy: float = 0.8
    ):
        """
        Assert that platform detection accurately identifies infrastructure platforms.
        
        Args:
            detected_platforms: List of detected platforms
            input_code: Original input code analyzed
            expected_accuracy: Expected detection accuracy
        """
        assert isinstance(detected_platforms, list), f"Detected platforms must be list, got {type(detected_platforms)}"
        assert isinstance(input_code, str) and input_code.strip(), "Input code must be non-empty string"
        
        # Analyze input code for platform indicators
        code_lower = input_code.lower()
        platform_indicators = {
            'chef': ['cookbook', 'recipe', 'chef', 'node[', 'attribute[', '.rb'],
            'puppet': ['class ', 'module ', 'manifest', '.pp', 'puppet'],
            'terraform': ['resource "', 'provider "', 'variable "', '.tf', 'terraform'],
            'ansible': ['- name:', 'hosts:', 'tasks:', 'playbook', '.yml', '.yaml'],
            'salt': ['salt:', 'pillar:', 'grains:', '.sls', 'highstate'],
            'bladelogic': ['blcli', 'nsh', 'bl_', 'bladelogic']
        }
        
        # Find actual platforms in code
        code_platforms = []
        for platform, indicators in platform_indicators.items():
            if any(indicator in code_lower for indicator in indicators):
                code_platforms.append(platform)
        
        if code_platforms:
            # Calculate detection accuracy
            correct_detections = len(set(detected_platforms).intersection(set(code_platforms)))
            total_actual = len(code_platforms)
            accuracy = correct_detections / total_actual if total_actual > 0 else 0
            
            assert accuracy >= expected_accuracy, f"Platform detection accuracy too low: {accuracy:.2f} < {expected_accuracy}. Detected: {detected_platforms}, Expected: {code_platforms}"
        
        logger.info(f" Platform detection accurate: {detected_platforms} from code with {code_platforms}")
    
    @staticmethod
    def assert_complexity_assessment_validity(
        complexity_assessment: str,
        worker_assignments: List[Dict[str, Any]],
        input_code_length: int
    ):
        """
        Assert that complexity assessment is reasonable given the assignments and code.
        
        Args:
            complexity_assessment: Assessed complexity level
            worker_assignments: Generated worker assignments
            input_code_length: Length of input code
        """
        assert isinstance(complexity_assessment, str), f"Complexity must be string, got {type(complexity_assessment)}"
        
        complexity_lower = complexity_assessment.lower()
        assert complexity_lower in ['low', 'medium', 'high'], f"Invalid complexity level: {complexity_assessment}"
        
        # Validate complexity consistency with assignments
        num_assignments = len(worker_assignments)
        
        if complexity_lower == 'low':
            assert num_assignments <= 3, f"Low complexity should have ≤3 assignments, got {num_assignments}"
        elif complexity_lower == 'medium':
            assert 2 <= num_assignments <= 5, f"Medium complexity should have 2-5 assignments, got {num_assignments}"
        elif complexity_lower == 'high':
            assert num_assignments >= 3, f"High complexity should have ≥3 assignments, got {num_assignments}"
        
        # Validate complexity consistency with code length
        if input_code_length < 500:
            assert complexity_lower in ['low', 'medium'], f"Short code ({input_code_length} chars) should not be high complexity"
        elif input_code_length > 2000:
            assert complexity_lower in ['medium', 'high'], f"Long code ({input_code_length} chars) should not be low complexity"
        
        logger.info(f" Complexity assessment valid: {complexity_assessment} for {num_assignments} assignments, {input_code_length} chars")
    
    @staticmethod
    def assert_orchestrator_structured_output(
        structured_output: Dict[str, Any],
        expected_schema_fields: List[str] = None
    ):
        """
        Assert that orchestrator produces valid structured output.
        
        Args:
            structured_output: Structured output from orchestrator
            expected_schema_fields: Expected fields in the schema
        """
        assert isinstance(structured_output, dict), f"Structured output must be dict, got {type(structured_output)}"
        
        # Check for required schema fields
        default_schema_fields = [
            'detected_platforms', 'complexity_assessment', 'processing_strategy',
            'estimated_duration', 'worker_assignments', 'confidence', 'reasoning'
        ]
        schema_fields = expected_schema_fields or default_schema_fields
        
        for field in schema_fields:
            assert field in structured_output, f"Structured output missing field: {field}"
        
        # Validate specific field types
        if 'detected_platforms' in structured_output:
            assert isinstance(structured_output['detected_platforms'], list), "detected_platforms must be list"
        
        if 'worker_assignments' in structured_output:
            assert isinstance(structured_output['worker_assignments'], list), "worker_assignments must be list"
        
        if 'confidence' in structured_output:
            confidence = structured_output['confidence']
            assert isinstance(confidence, (int, float)), "confidence must be numeric"
            assert 0.0 <= confidence <= 1.0, f"confidence must be 0-1, got {confidence}"
        
        if 'estimated_duration' in structured_output:
            duration = structured_output['estimated_duration']
            assert isinstance(duration, (int, float)), "estimated_duration must be numeric"
            assert duration > 0, f"estimated_duration must be positive, got {duration}"
        
        logger.info(f" Structured output valid: {len(structured_output)} fields")
    
    @staticmethod
    def assert_react_agent_orchestration_behavior(
        agent_output: Dict[str, Any],
        expected_tools_used: List[str] = None,
        min_reasoning_steps: int = 1
    ):
        """
        Assert that ReAct agent shows proper orchestration behavior.
        
        Args:
            agent_output: Output from orchestrator ReAct agent
            expected_tools_used: Expected tools to be used
            min_reasoning_steps: Minimum reasoning steps expected
        """
        assert isinstance(agent_output, dict), f"Agent output must be dict, got {type(agent_output)}"
        
        # Check for messages or tool calls
        messages = agent_output.get('messages', [])
        assert isinstance(messages, list), "Agent output should contain messages list"
        
        if expected_tools_used:
            # Check for tool usage
            tool_usage_found = []
            for message in messages:
                message_content = getattr(message, 'content', str(message))
                tool_calls = getattr(message, 'tool_calls', [])
                
                # Check tool calls
                if tool_calls:
                    for tool_call in tool_calls:
                        tool_name = tool_call.get('name') if isinstance(tool_call, dict) else getattr(tool_call, 'name', None)
                        if tool_name:
                            tool_usage_found.append(tool_name)
                
                # Check content for tool mentions
                for expected_tool in expected_tools_used:
                    if expected_tool in str(message_content):
                        tool_usage_found.append(expected_tool)
            
            for expected_tool in expected_tools_used:
                assert any(expected_tool in tool for tool in tool_usage_found), f"Expected tool '{expected_tool}' not used. Found: {tool_usage_found}"
        
        # Check for reasoning steps
        reasoning_indicators = ['analyze', 'plan', 'strategy', 'decision', 'assessment']
        reasoning_steps = 0
        for message in messages:
            message_content = str(getattr(message, 'content', message)).lower()
            if any(indicator in message_content for indicator in reasoning_indicators):
                reasoning_steps += 1
        
        assert reasoning_steps >= min_reasoning_steps, f"Insufficient reasoning steps: {reasoning_steps} < {min_reasoning_steps}"
        
        logger.info(f" ReAct orchestration behavior valid: {len(messages)} messages, {reasoning_steps} reasoning steps")
    
    @staticmethod
    def assert_orchestration_performance(
        processing_time: float,
        code_length: int,
        max_time_per_1k_chars: float = 5.0
    ):
        """
        Assert that orchestration completes within reasonable time.
        
        Args:
            processing_time: Actual processing time in seconds
            code_length: Length of code being analyzed
            max_time_per_1k_chars: Maximum time per 1000 characters
        """
        assert isinstance(processing_time, (int, float)), f"Processing time must be numeric, got {type(processing_time)}"
        assert processing_time > 0, f"Processing time must be positive, got {processing_time}"
        
        # Calculate expected time based on code length
        code_1k_units = max(code_length / 1000, 1)  # At least 1 unit
        max_expected_time = code_1k_units * max_time_per_1k_chars
        
        assert processing_time <= max_expected_time, f"Orchestration too slow: {processing_time:.2f}s > {max_expected_time:.2f}s for {code_length} chars"
        
        logger.info(f" Orchestration performance good: {processing_time:.2f}s for {code_length} chars")


class OrchestratorTestHelpers:
    """Helper utilities for orchestrator agent testing."""
    
    @staticmethod
    def create_test_orchestration_scenario(
        platform: str,
        complexity: str = "medium",
        code_length: int = 1000
    ) -> Dict[str, Any]:
        """Create a test scenario for orchestration testing."""
        
        # Platform-specific code samples
        platform_codes = {
            'chef': '''
cookbook_name = "test_cookbook"

package "nginx" do
  action :install
end

service "nginx" do
  action [:enable, :start]
end

template "/etc/nginx/nginx.conf" do
  source "nginx.conf.erb"
  variables({ server_name: node['hostname'] })
  notifies :restart, "service[nginx]", :delayed
end
''',
            'terraform': '''
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

resource "aws_instance" "web" {
  ami           = var.ami_id
  instance_type = "t2.micro"
  
  tags = {
    Name = "WebServer"
  }
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-west-2"
}
'''
        }
        
        base_code = platform_codes.get(platform, platform_codes['chef'])
        
        # Adjust code length
        if complexity == "simple":
            code = base_code[:min(len(base_code), 300)]
        elif complexity == "complex":
            code = base_code * 3  # Replicate for complexity
        else:
            code = base_code
        
        return {
            'input_code': code,
            'expected_platform': platform,
            'expected_complexity': complexity,
            'expected_assignments': 3 if complexity == "medium" else (2 if complexity == "simple" else 5)
        }
    
    @staticmethod
    def extract_orchestration_metrics(result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract orchestration metrics from result."""
        metrics = {
            'orchestration_complete': False,
            'platforms_detected': [],
            'assignments_created': 0,
            'confidence_score': 0.0,
            'complexity_level': 'unknown',
            'processing_time': 0.0
        }
        
        # Extract from orchestrator decision
        decision = result.get('orchestrator_decision', {})
        if isinstance(decision, dict):
            metrics.update({
                'orchestration_complete': True,
                'platforms_detected': decision.get('detected_platforms', []),
                'assignments_created': len(decision.get('worker_assignments', [])),
                'confidence_score': decision.get('confidence', 0.0),
                'complexity_level': decision.get('complexity_assessment', 'unknown')
            })
        
        # Extract processing time
        metrics['processing_time'] = result.get('processing_time', 0.0)
        
        return metrics
    
    @staticmethod
    def validate_orchestrator_tools_integration(agent_result: Dict[str, Any]) -> Dict[str, bool]:
        """Validate that orchestrator tools are properly integrated."""
        expected_tools = [
            'analyze_infrastructure_requirements',
            'create_worker_assignments', 
            'monitor_worker_progress',
            'create_spec_kit_plan'
        ]
        
        tool_status = {}
        messages = agent_result.get('messages', [])
        
        for tool in expected_tools:
            tool_used = False
            for message in messages:
                if hasattr(message, 'tool_calls') and message.tool_calls:
                    for tool_call in message.tool_calls:
                        if tool_call.get('name') == tool:
                            tool_used = True
                            break
                if tool_used:
                    break
            tool_status[tool] = tool_used
        
        return tool_status
