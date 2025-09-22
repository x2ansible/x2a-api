"""
x2a Universal Extractor Agent Test Patterns

Specialized test patterns and assertions for the x2a Universal Extractor Agent.
Provides comprehensive testing utilities for multi-platform infrastructure code
detection, intelligent tool selection, and facts extraction validation.

Key Features:
- Multi-platform detection testing (Chef, Puppet, Terraform, Ansible, BladeLogic, Salt)
- Intelligent tool selection validation
- Facts extraction accuracy testing
- Mixed-platform codebase handling
- ReAct agent behavior validation
- Platform-specific extraction quality assessment
"""

import logging
from typing import Dict, Any, List, Optional, Union
import json
import re

logger = logging.getLogger("x2a_test_framework.agents.universal_extractor")


class UniversalExtractorTestPatterns:
    """
    Specialized test patterns for x2a Universal Extractor Agent.
    
    Provides comprehensive validation patterns for platform detection,
    intelligent extraction, and multi-platform infrastructure analysis.
    """
    
    @staticmethod
    def assert_successful_platform_detection(
        result: Dict[str, Any],
        expected_platforms: List[str],
        min_confidence: float = 0.7
    ):
        """
        Assert that platform detection completed successfully with expected platforms.
        
        Args:
            result: Extraction result to validate
            expected_platforms: Expected detected platforms
            min_confidence: Minimum expected confidence score
        """
        assert isinstance(result, dict), f"Result must be a dictionary, got {type(result)}"
        
        # Check for detected platforms
        platform_fields = ['detected_platforms', 'platforms', 'platform_detection']
        detected_platforms = None
        for field in platform_fields:
            if field in result:
                detected_platforms = result[field]
                break
        
        assert detected_platforms is not None, f"No detected platforms found. Available keys: {list(result.keys())}"
        assert isinstance(detected_platforms, list), f"Detected platforms must be list, got {type(detected_platforms)}"
        
        # Check for expected platforms
        for expected_platform in expected_platforms:
            assert expected_platform in detected_platforms, f"Expected platform '{expected_platform}' not detected. Found: {detected_platforms}"
        
        # Check confidence if available
        confidence_fields = ['confidence', 'detection_confidence', 'platform_confidence']
        confidence = None
        for field in confidence_fields:
            if field in result:
                confidence = result[field]
                break
        
        if confidence is not None:
            assert isinstance(confidence, (int, float)), f"Confidence must be numeric, got {type(confidence)}"
            assert 0.0 <= confidence <= 1.0, f"Confidence must be 0-1, got {confidence}"
            assert confidence >= min_confidence, f"Confidence too low: {confidence} < {min_confidence}"
        
        logger.info(f" Platform detection successful: {detected_platforms}, confidence={confidence}")
    
    @staticmethod
    def assert_comprehensive_facts_extraction(
        extracted_facts: Dict[str, Any],
        platform: str,
        min_facts_count: int = 3
    ):
        """
        Assert that facts extraction is comprehensive for the detected platform.
        
        Args:
            extracted_facts: Extracted facts to validate
            platform: Platform being validated
            min_facts_count: Minimum number of facts expected
        """
        assert isinstance(extracted_facts, dict), f"Extracted facts must be dict, got {type(extracted_facts)}"
        assert len(extracted_facts) >= min_facts_count, f"Too few facts extracted: {len(extracted_facts)} < {min_facts_count}"
        
        # Platform-specific validation
        platform_lower = platform.lower()
        
        if platform_lower == 'chef':
            chef_indicators = ['cookbook', 'recipe', 'resource', 'package', 'service', 'template']
            found_indicators = [key for key in extracted_facts.keys() if any(indicator in key.lower() for indicator in chef_indicators)]
            assert len(found_indicators) > 0, f"No Chef-specific facts found in: {list(extracted_facts.keys())}"
            
        elif platform_lower == 'terraform':
            terraform_indicators = ['provider', 'resource', 'variable', 'output', 'module']
            found_indicators = [key for key in extracted_facts.keys() if any(indicator in key.lower() for indicator in terraform_indicators)]
            assert len(found_indicators) > 0, f"No Terraform-specific facts found in: {list(extracted_facts.keys())}"
            
        elif platform_lower == 'puppet':
            puppet_indicators = ['class', 'module', 'manifest', 'package', 'service', 'file']
            found_indicators = [key for key in extracted_facts.keys() if any(indicator in key.lower() for indicator in puppet_indicators)]
            assert len(found_indicators) > 0, f"No Puppet-specific facts found in: {list(extracted_facts.keys())}"
        
        # Check for meaningful fact values
        non_empty_facts = {k: v for k, v in extracted_facts.items() if v and str(v).strip()}
        assert len(non_empty_facts) >= min_facts_count, f"Too few meaningful facts: {len(non_empty_facts)} < {min_facts_count}"
        
        logger.info(f" Facts extraction comprehensive: {len(extracted_facts)} total facts, {len(non_empty_facts)} meaningful for {platform}")
    
    @staticmethod
    def assert_intelligent_tool_selection(
        agent_output: Dict[str, Any],
        expected_tools: List[str],
        platform_context: str
    ):
        """
        Assert that the agent intelligently selected appropriate tools.
        
        Args:
            agent_output: Output from universal extractor agent
            expected_tools: Expected tools to be used
            platform_context: Platform context for tool selection validation
        """
        assert isinstance(agent_output, dict), f"Agent output must be dict, got {type(agent_output)}"
        
        # Check for messages containing tool usage
        messages = agent_output.get('messages', [])
        assert isinstance(messages, list), "Agent output should contain messages list"
        
        # Track tool usage
        tools_used = []
        for message in messages:
            # Check tool calls
            tool_calls = getattr(message, 'tool_calls', [])
            if tool_calls:
                for tool_call in tool_calls:
                    tool_name = tool_call.get('name') if isinstance(tool_call, dict) else getattr(tool_call, 'name', None)
                    if tool_name:
                        tools_used.append(tool_name)
            
            # Check message content for tool mentions
            message_content = getattr(message, 'content', str(message))
            for expected_tool in expected_tools:
                if expected_tool in str(message_content):
                    tools_used.append(expected_tool)
        
        # Validate expected tools were used
        for expected_tool in expected_tools:
            tool_found = any(expected_tool in tool for tool in tools_used)
            assert tool_found, f"Expected tool '{expected_tool}' not used for {platform_context}. Used: {tools_used}"
        
        # Platform-specific tool validation
        platform_lower = platform_context.lower()
        if platform_lower == 'chef':
            assert any('chef' in tool.lower() for tool in tools_used), f"No Chef-specific tools used: {tools_used}"
        elif platform_lower == 'terraform':
            assert any('terraform' in tool.lower() for tool in tools_used), f"No Terraform-specific tools used: {tools_used}"
        
        logger.info(f" Intelligent tool selection: {tools_used} for {platform_context}")
    
    @staticmethod
    def assert_mixed_platform_handling(
        result: Dict[str, Any],
        expected_platforms: List[str],
        min_platforms: int = 2
    ):
        """
        Assert that mixed-platform codebases are handled correctly.
        
        Args:
            result: Extraction result from mixed-platform code
            expected_platforms: Expected platforms to be detected
            min_platforms: Minimum number of platforms expected
        """
        assert isinstance(result, dict), f"Result must be dict, got {type(result)}"
        
        # Check for multiple platform detection
        detected_platforms = result.get('detected_platforms', [])
        assert isinstance(detected_platforms, list), f"Detected platforms must be list, got {type(detected_platforms)}"
        assert len(detected_platforms) >= min_platforms, f"Too few platforms detected: {len(detected_platforms)} < {min_platforms}"
        
        # Check all expected platforms are detected
        for expected_platform in expected_platforms:
            assert expected_platform in detected_platforms, f"Expected platform '{expected_platform}' not in {detected_platforms}"
        
        # Check for platform-specific facts
        extracted_facts = result.get('extracted_facts', {})
        if extracted_facts:
            assert isinstance(extracted_facts, dict), "Extracted facts must be dict"
            
            # Should have facts for multiple platforms
            platform_fact_counts = {}
            for platform in detected_platforms:
                platform_facts = [k for k in extracted_facts.keys() if platform.lower() in k.lower()]
                platform_fact_counts[platform] = len(platform_facts)
            
            # At least some platforms should have facts
            platforms_with_facts = sum(1 for count in platform_fact_counts.values() if count > 0)
            assert platforms_with_facts >= min(len(detected_platforms), 2), f"Too few platforms have extracted facts: {platform_fact_counts}"
        
        logger.info(f" Mixed-platform handling: {detected_platforms}, facts per platform: {platform_fact_counts if 'platform_fact_counts' in locals() else 'N/A'}")
    
    @staticmethod
    def assert_platform_extraction_accuracy(
        extracted_facts: Dict[str, Any],
        input_code: str,
        platform: str,
        min_accuracy: float = 0.7
    ):
        """
        Assert that platform-specific extraction is accurate relative to input code.
        
        Args:
            extracted_facts: Facts extracted from code
            input_code: Original input code
            platform: Platform being validated
            min_accuracy: Minimum expected accuracy
        """
        assert isinstance(extracted_facts, dict), f"Extracted facts must be dict, got {type(extracted_facts)}"
        assert isinstance(input_code, str) and input_code.strip(), "Input code must be non-empty string"
        
        # Platform-specific accuracy checks
        platform_lower = platform.lower()
        code_lower = input_code.lower()
        
        accuracy_score = 0.0
        total_checks = 0
        
        if platform_lower == 'chef':
            # Check for Chef-specific elements
            chef_elements = {
                'cookbook': 'cookbook_name' in code_lower or 'cookbook' in code_lower,
                'package': 'package ' in code_lower,
                'service': 'service ' in code_lower,
                'template': 'template ' in code_lower,
                'recipe': 'recipe' in code_lower
            }
            
            for element, present_in_code in chef_elements.items():
                total_checks += 1
                if present_in_code:
                    # Check if extracted facts mention this element
                    element_found = any(element in str(v).lower() or element in k.lower() 
                                      for k, v in extracted_facts.items())
                    if element_found:
                        accuracy_score += 1.0
                        
        elif platform_lower == 'terraform':
            # Check for Terraform-specific elements
            terraform_elements = {
                'resource': 'resource "' in code_lower,
                'provider': 'provider "' in code_lower,
                'variable': 'variable "' in code_lower,
                'output': 'output "' in code_lower,
                'module': 'module "' in code_lower
            }
            
            for element, present_in_code in terraform_elements.items():
                total_checks += 1
                if present_in_code:
                    element_found = any(element in str(v).lower() or element in k.lower() 
                                      for k, v in extracted_facts.items())
                    if element_found:
                        accuracy_score += 1.0
        
        if total_checks > 0:
            final_accuracy = accuracy_score / total_checks
            assert final_accuracy >= min_accuracy, f"Extraction accuracy too low: {final_accuracy:.2f} < {min_accuracy} for {platform}"
        
        logger.info(f" Platform extraction accurate: {accuracy_score}/{total_checks} = {final_accuracy:.2f if total_checks > 0 else 'N/A'} for {platform}")
    
    @staticmethod
    def assert_universal_extractor_performance(
        processing_time: float,
        code_length: int,
        platforms_detected: int,
        max_time_per_platform: float = 10.0
    ):
        """
        Assert that universal extraction completes within reasonable time.
        
        Args:
            processing_time: Actual processing time in seconds
            code_length: Length of code being analyzed
            platforms_detected: Number of platforms detected
            max_time_per_platform: Maximum time per platform
        """
        assert isinstance(processing_time, (int, float)), f"Processing time must be numeric, got {type(processing_time)}"
        assert processing_time > 0, f"Processing time must be positive, got {processing_time}"
        
        # Calculate expected time based on platforms and code
        base_time = max(platforms_detected, 1) * max_time_per_platform
        code_complexity_factor = min(code_length / 1000, 3)  # Max 3x factor for long code
        max_expected_time = base_time * code_complexity_factor
        
        assert processing_time <= max_expected_time, f"Universal extraction too slow: {processing_time:.2f}s > {max_expected_time:.2f}s for {platforms_detected} platforms, {code_length} chars"
        
        logger.info(f" Universal extractor performance good: {processing_time:.2f}s for {platforms_detected} platforms, {code_length} chars")
    
    @staticmethod
    def assert_react_agent_extraction_behavior(
        agent_output: Dict[str, Any],
        expected_reasoning_steps: int = 2,
        expected_tool_calls: int = 1
    ):
        """
        Assert that ReAct agent shows proper extraction behavior.
        
        Args:
            agent_output: Output from universal extractor ReAct agent
            expected_reasoning_steps: Expected reasoning steps
            expected_tool_calls: Expected tool calls
        """
        assert isinstance(agent_output, dict), f"Agent output must be dict, got {type(agent_output)}"
        
        messages = agent_output.get('messages', [])
        assert isinstance(messages, list), "Agent output should contain messages list"
        assert len(messages) > 0, "Agent should produce at least one message"
        
        # Count reasoning steps and tool calls
        reasoning_steps = 0
        tool_calls = 0
        
        for message in messages:
            message_content = getattr(message, 'content', str(message))
            
            # Count reasoning indicators
            reasoning_indicators = ['detect', 'analyze', 'extract', 'platform', 'strategy']
            if any(indicator in str(message_content).lower() for indicator in reasoning_indicators):
                reasoning_steps += 1
            
            # Count tool calls
            message_tool_calls = getattr(message, 'tool_calls', [])
            if message_tool_calls:
                tool_calls += len(message_tool_calls)
        
        assert reasoning_steps >= expected_reasoning_steps, f"Insufficient reasoning steps: {reasoning_steps} < {expected_reasoning_steps}"
        assert tool_calls >= expected_tool_calls, f"Insufficient tool calls: {tool_calls} < {expected_tool_calls}"
        
        logger.info(f" ReAct extraction behavior valid: {reasoning_steps} reasoning steps, {tool_calls} tool calls")


class UniversalExtractorTestHelpers:
    """Helper utilities for universal extractor testing."""
    
    @staticmethod
    def create_mixed_platform_code(
        platforms: List[str],
        complexity: str = "medium"
    ) -> str:
        """Create mixed-platform infrastructure code for testing."""
        
        platform_snippets = {
            'chef': '''
# Chef cookbook
cookbook_name = "web_server"

package "nginx" do
  action :install
end

service "nginx" do
  action [:enable, :start]
end
''',
            'terraform': '''
# Terraform configuration
resource "aws_instance" "web" {
  ami           = "ami-12345678"
  instance_type = "t2.micro"
  
  tags = {
    Name = "WebServer"
  }
}

provider "aws" {
  region = "us-west-2"
}
''',
            'puppet': '''
# Puppet manifest
class nginx {
  package { 'nginx':
    ensure => installed,
  }
  
  service { 'nginx':
    ensure => running,
    enable => true,
  }
}
''',
            'ansible': '''
# Ansible playbook
---
- name: Install nginx
  hosts: webservers
  tasks:
    - name: Install nginx package
      package:
        name: nginx
        state: present
'''
        }
        
        # Combine requested platforms
        combined_code = "# Mixed platform infrastructure code\n\n"
        for platform in platforms:
            if platform in platform_snippets:
                combined_code += platform_snippets[platform] + "\n"
        
        return combined_code
    
    @staticmethod
    def extract_platform_facts_summary(result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract summary of platform facts from extraction result."""
        summary = {
            'platforms_detected': [],
            'total_facts': 0,
            'facts_per_platform': {},
            'confidence': 0.0,
            'extraction_complete': False
        }
        
        # Extract basic information
        summary['platforms_detected'] = result.get('detected_platforms', [])
        summary['confidence'] = result.get('confidence', 0.0)
        summary['extraction_complete'] = result.get('worker_status') == 'completed'
        
        # Extract facts information
        extracted_facts = result.get('extracted_facts', {})
        if extracted_facts:
            summary['total_facts'] = len(extracted_facts)
            
            # Count facts per platform
            for platform in summary['platforms_detected']:
                platform_facts = [k for k in extracted_facts.keys() if platform.lower() in k.lower()]
                summary['facts_per_platform'][platform] = len(platform_facts)
        
        return summary
    
    @staticmethod
    def validate_platform_specific_tools(
        agent_result: Dict[str, Any],
        platform: str
    ) -> bool:
        """Validate that platform-specific tools were used appropriately."""
        
        platform_tool_mapping = {
            'chef': ['chef_facts_extractor', 'platform_detector'],
            'terraform': ['terraform_facts_extractor', 'platform_detector'],
            'puppet': ['puppet_facts_extractor', 'platform_detector'],
            'bladelogic': ['bladelogic_facts_extractor', 'platform_detector']
        }
        
        expected_tools = platform_tool_mapping.get(platform.lower(), ['platform_detector'])
        
        messages = agent_result.get('messages', [])
        tools_used = []
        
        for message in messages:
            tool_calls = getattr(message, 'tool_calls', [])
            for tool_call in tool_calls:
                tool_name = tool_call.get('name') if isinstance(tool_call, dict) else getattr(tool_call, 'name', None)
                if tool_name:
                    tools_used.append(tool_name)
        
        # Check if appropriate tools were used
        return any(tool in tools_used for tool in expected_tools)
    
    @staticmethod
    def create_platform_detection_scenario(
        platform: str,
        include_noise: bool = False
    ) -> Dict[str, Any]:
        """Create a platform detection test scenario."""
        
        scenario_codes = {
            'chef': 'cookbook_name = "test"\npackage "nginx" do\n  action :install\nend',
            'terraform': 'resource "aws_instance" "test" {\n  ami = "ami-123"\n}',
            'puppet': 'class nginx {\n  package { "nginx": ensure => installed }\n}',
            'ansible': '---\n- name: Test\n  hosts: all\n  tasks:\n    - package: name=nginx'
        }
        
        base_code = scenario_codes.get(platform, scenario_codes['chef'])
        
        if include_noise:
            # Add some generic comments that shouldn't affect detection
            base_code = f"# Generic infrastructure configuration\n{base_code}\n# End configuration"
        
        return {
            'input_code': base_code,
            'expected_platform': platform,
            'expected_confidence': 0.8,
            'expected_tools': ['platform_detector', f'{platform}_facts_extractor']
        }
