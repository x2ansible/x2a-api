"""
x2a Validation Agent Test Patterns

Specialized test patterns and assertions for the x2a Validation Agent.
Provides comprehensive testing utilities for Ansible validation, ansible-lint
integration, iterative fixing, and code quality assessment.

Key Features:
- Ansible code validation testing
- ansible-lint tool integration validation
- Iterative fixing workflow testing
- Code quality assessment validation
- Validation issue detection testing
- Auto-fix capability testing
- ReAct agent behavior validation
"""

import logging
from typing import Dict, Any, List, Optional, Union
import re
import yaml

logger = logging.getLogger("x2a_test_framework.agents.validation")


class ValidationTestPatterns:
    """
    Specialized test patterns for x2a Validation Agent.
    
    Provides comprehensive validation patterns for Ansible code validation,
    quality assessment, and iterative fixing workflows.
    """
    
    @staticmethod
    def assert_successful_ansible_validation(
        result: Dict[str, Any],
        expect_issues: bool = False,
        min_quality_score: float = 0.7
    ):
        """
        Assert that Ansible validation completed successfully.
        
        Args:
            result: Validation result to validate
            expect_issues: Whether validation issues are expected
            min_quality_score: Minimum expected quality score (0-1)
        """
        assert isinstance(result, dict), f"Result must be a dictionary, got {type(result)}"
        
        # Check validation completion
        validation_complete = result.get('validation_complete', False)
        assert validation_complete is True, "Validation should be marked as complete"
        
        # Check for validation summary
        summary_fields = ['validation_summary', 'summary', 'final_summary']
        validation_summary = None
        for field in summary_fields:
            if field in result:
                validation_summary = result[field]
                break
        
        assert validation_summary is not None, f"No validation summary found. Available keys: {list(result.keys())}"
        
        # Check quality score if available
        quality_score = None
        if isinstance(validation_summary, dict):
            quality_score = validation_summary.get('code_quality_score') or validation_summary.get('quality_score')
        
        if quality_score is not None:
            assert isinstance(quality_score, (int, float)), f"Quality score must be numeric, got {type(quality_score)}"
            normalized_score = quality_score / 100 if quality_score > 1 else quality_score
            assert normalized_score >= min_quality_score, f"Quality score too low: {normalized_score} < {min_quality_score}"
        
        logger.info(f" Ansible validation successful: complete={validation_complete}, quality={quality_score}")
    
    @staticmethod
    def assert_ansible_lint_integration(
        lint_result: Any,
        expected_format: str = "structured"
    ):
        """
        Assert that ansible-lint integration works correctly.
        
        Args:
            lint_result: Result from ansible-lint tool
            expected_format: Expected result format
        """
        if expected_format == "structured":
            # ansible-lint should return structured data
            assert lint_result is not None, "ansible-lint should return a result"
            
            # Could be list of issues, dict with results, or string output
            assert isinstance(lint_result, (list, dict, str)), f"Unexpected lint result type: {type(lint_result)}"
            
            if isinstance(lint_result, str):
                # String output should contain validation information
                assert len(lint_result) > 0, "ansible-lint output should not be empty"
                
        logger.info(f" ansible-lint integration working: {type(lint_result)}")
    
    @staticmethod
    def assert_validation_issue_detection(
        issues: List[Dict[str, Any]],
        expected_issue_types: List[str] = None,
        min_issue_detail: int = 10
    ):
        """
        Assert that validation correctly identifies issues.
        
        Args:
            issues: List of detected validation issues
            expected_issue_types: Expected types of issues to find
            min_issue_detail: Minimum detail length for issue descriptions
        """
        assert isinstance(issues, list), f"Issues must be a list, got {type(issues)}"
        
        if expected_issue_types:
            assert len(issues) > 0, "Expected issues but none found"
        
        # Validate issue structure
        for i, issue in enumerate(issues):
            assert isinstance(issue, dict), f"Issue {i} must be a dict, got {type(issue)}"
            
            # Check for common issue fields
            issue_fields = ['rule', 'message', 'severity', 'description', 'type']
            has_field = any(field in issue for field in issue_fields)
            assert has_field, f"Issue {i} missing common fields: {list(issue.keys())}"
            
            # Check issue detail
            issue_text = str(issue.get('message', '') or issue.get('description', ''))
            if issue_text:
                assert len(issue_text) >= min_issue_detail, f"Issue {i} description too short: {len(issue_text)}"
        
        logger.info(f" Issue detection working: {len(issues)} issues found")
    
    @staticmethod
    def assert_iterative_fixing_workflow(
        fixing_iterations: List[Dict[str, Any]],
        max_expected_iterations: int = 5,
        expect_improvement: bool = True
    ):
        """
        Assert that iterative fixing workflow works correctly.
        
        Args:
            fixing_iterations: List of fixing iterations
            max_expected_iterations: Maximum expected iterations
            expect_improvement: Whether improvement is expected over iterations
        """
        assert isinstance(fixing_iterations, list), f"Iterations must be a list, got {type(fixing_iterations)}"
        assert len(fixing_iterations) <= max_expected_iterations, f"Too many iterations: {len(fixing_iterations)} > {max_expected_iterations}"
        
        if expect_improvement and len(fixing_iterations) > 1:
            # Check for improvement indicators
            first_iteration = fixing_iterations[0]
            last_iteration = fixing_iterations[-1]
            
            # Look for reduction in issues or improvement in quality
            first_issues = first_iteration.get('issue_count', len(first_iteration.get('issues', [])))
            last_issues = last_iteration.get('issue_count', len(last_iteration.get('issues', [])))
            
            # Some improvement expected (issues reduced or code quality improved)
            improvement_found = (
                last_issues < first_issues or
                last_iteration.get('validation_passed', False) or
                last_iteration.get('quality_improved', False)
            )
            
            if first_issues > 0:  # Only check improvement if there were initial issues
                assert improvement_found, f"No improvement found: {first_issues} → {last_issues} issues"
        
        logger.info(f" Iterative fixing working: {len(fixing_iterations)} iterations")
    
    @staticmethod
    def assert_ansible_code_quality(
        validated_code: str,
        original_code: str,
        min_improvement_ratio: float = 0.1
    ):
        """
        Assert that validated code shows quality improvement.
        
        Args:
            validated_code: Code after validation/fixing
            original_code: Original input code
            min_improvement_ratio: Minimum improvement ratio expected
        """
        assert isinstance(validated_code, str) and validated_code.strip(), "Validated code must be non-empty string"
        assert isinstance(original_code, str) and original_code.strip(), "Original code must be non-empty string"
        
        # Basic structure checks
        validated_lines = validated_code.strip().split('\n')
        original_lines = original_code.strip().split('\n')
        
        # Validated code should be reasonable length
        assert len(validated_lines) >= len(original_lines) * (1 - min_improvement_ratio), "Validated code too short"
        assert len(validated_lines) <= len(original_lines) * 3, "Validated code too long"
        
        # Try YAML parsing if it looks like YAML
        if validated_code.strip().startswith('---') or 'name:' in validated_code:
            try:
                yaml.safe_load(validated_code)
                logger.info(" Validated code parses as valid YAML")
            except yaml.YAMLError as e:
                logger.warning(f"YAML parsing issue: {e}")
        
        # Check for Ansible-specific improvements
        ansible_indicators = ['name:', 'tasks:', 'hosts:', 'become:', 'vars:']
        validated_indicators = sum(1 for indicator in ansible_indicators if indicator in validated_code)
        original_indicators = sum(1 for indicator in ansible_indicators if indicator in original_code)
        
        if original_indicators > 0:
            improvement_ratio = validated_indicators / original_indicators
            assert improvement_ratio >= (1 - min_improvement_ratio), f"Ansible structure degraded: {improvement_ratio:.2f}"
        
        logger.info(f" Code quality assessment passed: {len(validated_lines)} lines, {validated_indicators} ansible indicators")
    
    @staticmethod
    def assert_validation_error_handling(
        result: Dict[str, Any],
        error_context: str,
        expect_graceful_failure: bool = True
    ):
        """
        Assert that validation handles errors gracefully.
        
        Args:
            result: Validation result with potential errors
            error_context: Context of the error for debugging
            expect_graceful_failure: Whether graceful failure is expected
        """
        assert isinstance(result, dict), f"Result must be dict, got {type(result)}"
        
        if expect_graceful_failure:
            # Should have error information but not crash
            error_fields = ['error_message', 'error', 'validation_error', 'issues']
            has_error_info = any(field in result for field in error_fields)
            
            if has_error_info:
                # Error should be informative
                error_msg = result.get('error_message') or result.get('error', '')
                if error_msg:
                    assert len(str(error_msg)) >= 10, f"Error message too short: {error_msg}"
                    assert error_context.lower() in str(error_msg).lower() or "validation" in str(error_msg).lower(), f"Error message should mention context: {error_msg}"
        
        logger.info(f" Error handling validated: {error_context}")
    
    @staticmethod
    def assert_react_agent_validation_behavior(
        agent_output: Dict[str, Any],
        expected_tool_usage: bool = True,
        expected_analysis: bool = True
    ):
        """
        Assert that ReAct agent shows proper validation behavior.
        
        Args:
            agent_output: Output from validation ReAct agent
            expected_tool_usage: Whether ansible-lint tool usage is expected
            expected_analysis: Whether validation analysis is expected
        """
        assert isinstance(agent_output, dict), f"Agent output must be dict, got {type(agent_output)}"
        
        # Check for messages or output
        output_fields = ['messages', 'output', 'result', 'validation_output']
        agent_content = None
        
        for field in output_fields:
            if field in agent_output:
                content = agent_output[field]
                if isinstance(content, list) and content:
                    # Extract from messages
                    last_message = content[-1]
                    agent_content = getattr(last_message, 'content', str(last_message))
                elif isinstance(content, str):
                    agent_content = content
                break
        
        assert agent_content is not None, f"No agent output found. Available keys: {list(agent_output.keys())}"
        
        if expected_tool_usage:
            # Should mention ansible-lint or validation tools
            tool_keywords = ['ansible-lint', 'lint', 'validation', 'tool_calls']
            tool_usage_found = any(keyword in str(agent_content).lower() for keyword in tool_keywords)
            assert tool_usage_found, f"Expected tool usage but none found in: {agent_content[:200]}..."
        
        if expected_analysis:
            # Should provide analysis
            analysis_keywords = ['syntax', 'structure', 'best practices', 'issues', 'quality', 'recommendations']
            analysis_found = any(keyword in str(agent_content).lower() for keyword in analysis_keywords)
            assert analysis_found, f"Expected analysis but none found in: {agent_content[:200]}..."
        
        logger.info(f" ReAct agent validation behavior valid: tool_usage={expected_tool_usage}, analysis={expected_analysis}")
    
    @staticmethod
    def assert_validation_state_management(
        state_transitions: List[Dict[str, Any]],
        expected_states: List[str] = None,
        max_transitions: int = 10
    ):
        """
        Assert that validation state management works correctly.
        
        Args:
            state_transitions: List of state transitions during validation
            expected_states: Expected states in the workflow
            max_transitions: Maximum expected state transitions
        """
        assert isinstance(state_transitions, list), f"State transitions must be list, got {type(state_transitions)}"
        assert len(state_transitions) <= max_transitions, f"Too many state transitions: {len(state_transitions)}"
        
        if expected_states:
            state_names = []
            for transition in state_transitions:
                if isinstance(transition, dict):
                    state_name = transition.get('state') or transition.get('node') or transition.get('step')
                    if state_name:
                        state_names.append(state_name)
            
            for expected_state in expected_states:
                assert expected_state in state_names, f"Expected state '{expected_state}' not found in: {state_names}"
        
        logger.info(f" State management working: {len(state_transitions)} transitions")


class ValidationTestHelpers:
    """Helper utilities for validation agent testing."""
    
    @staticmethod
    def create_test_ansible_code(
        complexity: str = "simple",
        with_issues: bool = False
    ) -> str:
        """Create test Ansible code for validation testing."""
        if complexity == "simple":
            base_code = '''---
- name: Install and configure nginx
  hosts: all
  become: yes
  tasks:
    - name: Install nginx
      package:
        name: nginx
        state: present
    - name: Start nginx
      service:
        name: nginx
        state: started
        enabled: yes'''
        else:
            base_code = '''---
- name: Complex web server setup
  hosts: webservers
  become: yes
  vars:
    nginx_version: "1.20"
    ssl_enabled: true
  tasks:
    - name: Install nginx
      package:
        name: "nginx={{ nginx_version }}"
        state: present
      tags: installation
    
    - name: Configure nginx
      template:
        src: nginx.conf.j2
        dest: /etc/nginx/nginx.conf
        backup: yes
      notify: restart nginx
      
  handlers:
    - name: restart nginx
      service:
        name: nginx
        state: restarted'''
        
        if with_issues:
            # Introduce common Ansible issues
            base_code = base_code.replace('become: yes', 'become: true')  # Style issue
            base_code = base_code.replace('state: present', 'state: latest')  # Best practice issue
        
        return base_code
    
    @staticmethod
    def extract_validation_metrics(result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract validation metrics from result."""
        metrics = {
            'validation_complete': result.get('validation_complete', False),
            'issue_count': 0,
            'quality_score': None,
            'iterations_used': result.get('current_iteration', 0),
            'auto_fix_applied': result.get('fixes_applied', False)
        }
        
        # Extract issue count
        issues = result.get('issues', []) or result.get('validation_issues', [])
        if issues:
            metrics['issue_count'] = len(issues)
        
        # Extract quality score
        summary = result.get('validation_summary', {}) or result.get('summary', {})
        if isinstance(summary, dict):
            metrics['quality_score'] = summary.get('code_quality_score') or summary.get('quality_score')
        
        return metrics
    
    @staticmethod
    def create_validation_test_scenario(
        ansible_code: str,
        validation_level: str = "standard",
        enable_auto_fix: bool = True
    ) -> Dict[str, Any]:
        """Create a test scenario for validation testing."""
        return {
            'input_code': ansible_code,
            'validation_level': validation_level,
            'enable_auto_fix': enable_auto_fix,
            'max_iterations': 3,
            'expected_completion': True
        }
    
    @staticmethod
    def check_container_prerequisites() -> tuple[bool, Dict[str, bool]]:
        """Check container deployment prerequisites for validation agent."""
        import subprocess
        import tempfile
        from pathlib import Path
        
        checks = {}
        
        # Check ansible-lint availability
        try:
            result = subprocess.run(['ansible-lint', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            checks['ansible_lint'] = result.returncode == 0
        except Exception:
            checks['ansible_lint'] = False
        
        # Check Python dependencies
        try:
            import validation.graph
            import langchain_openai
            import yaml
            checks['python_deps'] = True
        except ImportError:
            checks['python_deps'] = False
        
        # Check config file
        config_path = Path(__file__).parent.parent.parent / "config.yaml"
        checks['config'] = config_path.exists()
        
        # Check test data
        test_data_dir = Path(__file__).parent.parent.parent / "testing" / "functional" / "test_data" / "validation"
        checks['test_data'] = test_data_dir.exists()
        
        # Check file permissions
        try:
            with tempfile.NamedTemporaryFile(mode='w', delete=True) as f:
                f.write("test")
            checks['file_permissions'] = True
        except Exception:
            checks['file_permissions'] = False
        
        return all(checks.values()), checks
    
    @staticmethod
    def assert_container_readiness(
        test_results: Dict[str, Any],
        min_success_rate: float = 80.0
    ):
        """Assert that validation agent is ready for container deployment."""
        # Check prerequisites
        prereq_passed, prereq_checks = ValidationTestHelpers.check_container_prerequisites()
        assert prereq_passed, f"Prerequisites failed: {prereq_checks}"
        
        # Check test results
        success_rate = test_results.get('success_rate', 0)
        assert success_rate >= min_success_rate, f"Success rate {success_rate}% below minimum {min_success_rate}%"
        
        failed_tests = test_results.get('failed_tests', 0)
        assert failed_tests == 0, f"Found {failed_tests} failed tests"
        
        total_tests = test_results.get('scenarios_tested', 0)
        assert total_tests >= 4, f"Insufficient tests run: {total_tests}"
        
        logger.info(f"Container readiness validated: {success_rate}% success rate, {total_tests} tests")