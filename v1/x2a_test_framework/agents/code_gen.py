"""
x2a Code Generation Agent Test Patterns

Specialized test patterns and assertions for the x2a Code Generation Agent.
Provides comprehensive testing utilities for Chef to Ansible conversion,
code generation quality validation, and conversion accuracy testing.

Key Features:
- Code conversion validation (Chef to Ansible)
- Generated code quality assertions
- Conversion accuracy and fidelity testing
- YAML format validation
- Ansible playbook structure validation
- Migration strategy testing
- Performance monitoring for code generation
"""

import logging
from typing import Dict, Any, List, Optional
import yaml
import re

logger = logging.getLogger("x2a_test_framework.agents.code_gen")


class CodeGenTestPatterns:
    """
    Specialized test patterns for x2a Code Generation Agent.
    
    Provides comprehensive validation patterns for code generation,
    conversion quality, and Ansible output validation.
    """
    
    @staticmethod
    def assert_successful_code_generation(
        result: Dict[str, Any],
        min_code_length: int = 50,
        context: str = "code_generation"
    ):
        """
        Assert that code generation completed successfully with valid output.
        
        Args:
            result: Code generation result to validate
            min_code_length: Minimum expected length of generated code
            context: Context for error reporting
        """
        # Check for generated code
        code_fields = ["generated_code", "output_code", "ansible_code"]
        generated_code = None
        code_field = None
        
        for field in code_fields:
            if field in result and result[field]:
                generated_code = result[field]
                code_field = field
                break
        
        if generated_code is None:
            available_fields = list(result.keys())
            raise AssertionError(
                f"{context}: No generated code found. Expected one of: {code_fields}. "
                f"Available fields: {available_fields}"
            )
        
        # Validate code length
        if len(generated_code.strip()) < min_code_length:
            raise AssertionError(
                f"{context}: Generated code too short ({len(generated_code)} chars, "
                f"minimum {min_code_length})"
            )
        
        # Check generation status
        status_fields = ["generation_status", "status"]
        status = None
        
        for field in status_fields:
            if field in result:
                status = result[field]
                break
        
        if status and status not in ["completed", "success", "finished"]:
            raise AssertionError(
                f"{context}: Generation status indicates failure: {status}"
            )
        
        logger.info(f"{context}: Code generation successful, {len(generated_code)} chars generated")
    
    @staticmethod
    def assert_valid_ansible_playbook(
        generated_code: str,
        context: str = "ansible_validation"
    ):
        """
        Assert that generated code is a valid Ansible playbook.
        
        Args:
            generated_code: The generated Ansible code to validate
            context: Context for error reporting
        """
        if not generated_code or not generated_code.strip():
            raise AssertionError(f"{context}: Generated code is empty")
        
        # Try to parse as YAML
        try:
            parsed_yaml = yaml.safe_load(generated_code)
        except yaml.YAMLError as e:
            raise AssertionError(
                f"{context}: Generated code is not valid YAML: {str(e)}"
            )
        
        # Check basic Ansible playbook structure
        if not isinstance(parsed_yaml, list):
            raise AssertionError(
                f"{context}: Ansible playbook must be a list of plays"
            )
        
        if len(parsed_yaml) == 0:
            raise AssertionError(
                f"{context}: Ansible playbook is empty"
            )
        
        # Validate first play structure
        first_play = parsed_yaml[0]
        if not isinstance(first_play, dict):
            raise AssertionError(
                f"{context}: Ansible play must be a dictionary"
            )
        
        # Check for required Ansible fields
        ansible_fields = ["hosts", "tasks"]
        missing_fields = []
        
        for field in ansible_fields:
            if field not in first_play:
                missing_fields.append(field)
        
        if missing_fields:
            raise AssertionError(
                f"{context}: Missing required Ansible fields: {missing_fields}"
            )
        
        # Validate tasks structure
        tasks = first_play.get("tasks", [])
        if not isinstance(tasks, list):
            raise AssertionError(
                f"{context}: Ansible tasks must be a list"
            )
        
        if len(tasks) == 0:
            raise AssertionError(
                f"{context}: Ansible playbook has no tasks"
            )
        
        logger.info(f"{context}: Valid Ansible playbook with {len(tasks)} tasks")
    
    @staticmethod
    def assert_chef_to_ansible_conversion_quality(
        chef_input: str,
        ansible_output: str,
        context: str = "conversion_quality"
    ):
        """
        Assert conversion quality from Chef to Ansible.
        
        Args:
            chef_input: Original Chef code
            ansible_output: Generated Ansible code
            context: Context for error reporting
        """
        # Extract Chef resources
        chef_resources = CodeGenTestPatterns._extract_chef_resources(chef_input)
        
        # Extract Ansible tasks
        ansible_tasks = CodeGenTestPatterns._extract_ansible_tasks(ansible_output)
        
        # Basic conversion validation
        if len(chef_resources) == 0:
            raise AssertionError(f"{context}: No Chef resources found in input")
        
        if len(ansible_tasks) == 0:
            raise AssertionError(f"{context}: No Ansible tasks found in output")
        
        # Check resource mapping coverage
        mapped_resources = 0
        
        for chef_resource in chef_resources:
            if CodeGenTestPatterns._is_resource_mapped(chef_resource, ansible_tasks):
                mapped_resources += 1
        
        mapping_percentage = (mapped_resources / len(chef_resources)) * 100
        
        if mapping_percentage < 70:  # At least 70% of resources should be mapped
            raise AssertionError(
                f"{context}: Low conversion coverage {mapping_percentage:.1f}% "
                f"({mapped_resources}/{len(chef_resources)} resources mapped)"
            )
        
        logger.info(
            f"{context}: Conversion quality good - {mapping_percentage:.1f}% coverage "
            f"({mapped_resources}/{len(chef_resources)} resources)"
        )
    
    @staticmethod
    def assert_conversion_confidence(
        result: Dict[str, Any],
        min_confidence: float = 0.7,
        context: str = "conversion_confidence"
    ):
        """
        Assert that conversion confidence meets minimum threshold.
        
        Args:
            result: Code generation result with confidence information
            min_confidence: Minimum confidence threshold
            context: Context for error reporting
        """
        confidence_fields = [
            "generation_confidence", "conversion_confidence", 
            "confidence", "quality_score"
        ]
        
        confidence = None
        confidence_field = None
        
        for field in confidence_fields:
            if field in result and result[field] is not None:
                confidence = result[field]
                confidence_field = field
                break
        
        if confidence is None:
            # If no confidence field, skip this assertion
            logger.warning(f"{context}: No confidence information available")
            return
        
        # Validate confidence format
        if not isinstance(confidence, (int, float)):
            raise AssertionError(
                f"{context}: Confidence must be numeric, got {type(confidence)}"
            )
        
        if not 0 <= confidence <= 1:
            raise AssertionError(
                f"{context}: Confidence must be between 0 and 1, got {confidence}"
            )
        
        # Check minimum threshold
        if confidence < min_confidence:
            raise AssertionError(
                f"{context}: Conversion confidence {confidence:.2f} below minimum {min_confidence:.2f}"
            )
        
        logger.info(f"{context}: Conversion confidence {confidence:.2f} meets threshold")
    
    @staticmethod
    def assert_no_generation_errors(
        result: Dict[str, Any],
        context: str = "generation_errors"
    ):
        """
        Assert that no generation errors occurred.
        
        Args:
            result: Code generation result to check for errors
            context: Context for error reporting
        """
        error_fields = ["generation_errors", "errors", "error_messages"]
        
        for field in error_fields:
            if field in result:
                errors = result[field]
                
                if errors and len(errors) > 0:
                    error_details = errors if isinstance(errors, list) else [errors]
                    raise AssertionError(
                        f"{context}: Generation errors found: {error_details}"
                    )
        
        logger.info(f"{context}: No generation errors found")
    
    @staticmethod
    def assert_yaml_format_compliance(
        generated_code: str,
        context: str = "yaml_format"
    ):
        """
        Assert that generated code complies with YAML format standards.
        
        Args:
            generated_code: The generated code to validate
            context: Context for error reporting
        """
        if not generated_code or not generated_code.strip():
            raise AssertionError(f"{context}: Generated code is empty")
        
        # Check for common YAML issues
        lines = generated_code.split('\n')
        
        # Check for tabs (should use spaces)
        for i, line in enumerate(lines, 1):
            if '\t' in line:
                raise AssertionError(
                    f"{context}: YAML should use spaces, not tabs (line {i})"
                )
        
        # Check for consistent indentation (2 spaces is Ansible standard)
        indentation_pattern = re.compile(r'^( *)[^\s]')
        indentations = []
        
        for line in lines:
            if line.strip():  # Skip empty lines
                match = indentation_pattern.match(line)
                if match:
                    indent_level = len(match.group(1))
                    if indent_level > 0:
                        indentations.append(indent_level)
        
        # Check if indentations are multiples of 2
        if indentations:
            invalid_indents = [i for i in indentations if i % 2 != 0]
            if invalid_indents:
                raise AssertionError(
                    f"{context}: Invalid indentation levels found: {invalid_indents} "
                    "(Ansible YAML should use 2-space indentation)"
                )
        
        # Try to parse as YAML to catch syntax errors
        try:
            yaml.safe_load(generated_code)
        except yaml.YAMLError as e:
            raise AssertionError(f"{context}: YAML syntax error: {str(e)}")
        
        logger.info(f"{context}: YAML format compliance validated")
    
    @staticmethod
    def _extract_chef_resources(chef_code: str) -> List[str]:
        """Extract Chef resources from Chef code."""
        # Simple regex to find Chef resources like 'package "name" do'
        resource_pattern = re.compile(r'(\w+)\s+["\']([^"\']+)["\']?\s+do', re.MULTILINE)
        matches = resource_pattern.findall(chef_code)
        return [f"{resource_type}[{resource_name}]" for resource_type, resource_name in matches]
    
    @staticmethod
    def _extract_ansible_tasks(ansible_code: str) -> List[Dict[str, Any]]:
        """Extract Ansible tasks from Ansible YAML code."""
        try:
            parsed = yaml.safe_load(ansible_code)
            if isinstance(parsed, list) and len(parsed) > 0:
                first_play = parsed[0]
                if isinstance(first_play, dict) and "tasks" in first_play:
                    return first_play["tasks"]
        except yaml.YAMLError:
            pass
        return []
    
    @staticmethod
    def _is_resource_mapped(chef_resource: str, ansible_tasks: List[Dict[str, Any]]) -> bool:
        """Check if a Chef resource is mapped to Ansible tasks."""
        # Extract resource type and name from chef_resource like "package[nginx]"
        match = re.match(r'(\w+)\[([^\]]+)\]', chef_resource)
        if not match:
            return False
        
        resource_type, resource_name = match.groups()
        
        # Map Chef resource types to Ansible modules
        chef_to_ansible_mapping = {
            "package": ["package", "apt", "yum", "dnf"],
            "service": ["service", "systemd"],
            "template": ["template", "copy"],
            "file": ["file", "copy"],
            "directory": ["file"],
            "user": ["user"],
            "group": ["group"]
        }
        
        ansible_modules = chef_to_ansible_mapping.get(resource_type, [])
        
        # Check if any task uses the mapped modules with similar name
        for task in ansible_tasks:
            if isinstance(task, dict):
                for module in ansible_modules:
                    if module in task:
                        # Check if the resource name appears in the task
                        task_content = str(task[module])
                        if resource_name.lower() in task_content.lower():
                            return True
        
        return False
