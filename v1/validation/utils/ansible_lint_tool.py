"""
Ansible-lint Tool Implementation

LangChain tool wrapper for ansible-lint validation with structured output.
"""

import subprocess
import tempfile
import json
import os
import re
from typing import Dict, List, Any, Optional
from pathlib import Path

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from validation.state import ValidationIssue, ValidationSummary


# Validation levels configuration
VALIDATION_LEVELS = {
    "basic": {
        "description": "Basic syntax and structure validation",
        "ansible_lint_args": ["--parseable", "--quiet"],
        "severity_threshold": "error"  # Only show errors
    },
    "standard": {
        "description": "Standard best practices validation", 
        "ansible_lint_args": ["--parseable"],
        "severity_threshold": "warning"  # Show errors and warnings
    },
    "strict": {
        "description": "Strict validation with all rules",
        "ansible_lint_args": ["--parseable", "--strict"],
        "severity_threshold": "info"  # Show everything
    }
}


class AnsibleLintInput(BaseModel):
    """Input schema for ansible-lint tool"""
    ansible_code: str = Field(description="Ansible playbook/tasks YAML code to validate")
    validation_level: str = Field(
        default="standard",
        description="Validation level: 'basic', 'standard', or 'strict'"
    )
    filename_hint: Optional[str] = Field(
        default="playbook.yml",
        description="Filename hint for better validation context"
    )


class AnsibleLintTool(BaseTool):
    """LangChain tool for ansible-lint validation."""
    
    name: str = "ansible_lint_validator"
    description: str = """
    Validates Ansible playbook code using ansible-lint.
    
    Input: ansible_code (YAML string), validation_level (basic/standard/strict)
    Output: Structured validation results with issues, suggestions, and overall status
    
    Use this tool when you need to:
    - Validate Ansible playbook syntax and best practices
    - Check for common Ansible anti-patterns  
    - Get specific line-by-line feedback on Ansible code
    - Ensure generated Ansible code follows best practices
    """
    args_schema: type = AnsibleLintInput
    
    def _run(self, ansible_code: str, validation_level: str = "standard", filename_hint: str = "playbook.yml") -> str:
        """Run ansible-lint validation synchronously"""
        try:
            result = self._validate_ansible_code(ansible_code, validation_level, filename_hint)
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps({
                "error": f"Validation failed: {str(e)}",
                "validation_status": "error",
                "issues_found": [],
                "summary": {"total_issues": 0, "errors": 1, "validation_status": "error"}
            })
    
    async def _arun(self, ansible_code: str, validation_level: str = "standard", filename_hint: str = "playbook.yml") -> str:
        """Run ansible-lint validation asynchronously"""
        return self._run(ansible_code, validation_level, filename_hint)
    
    def _validate_ansible_code(self, ansible_code: str, validation_level: str, filename_hint: str) -> Dict[str, Any]:
        """Core validation logic - runs ansible-lint and parses results"""
        
        if not ansible_code.strip():
            return {
                "error": "Empty ansible code provided",
                "validation_status": "error",
                "issues_found": [],
                "summary": {"total_issues": 0, "errors": 1, "validation_status": "error"}
            }
        
        if validation_level not in VALIDATION_LEVELS:
            validation_level = "standard"
        
        level_config = VALIDATION_LEVELS[validation_level]
        
        # Create temporary file with ansible code
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as temp_file:
            temp_file.write(ansible_code)
            temp_file_path = temp_file.name
        
        try:
            # Run ansible-lint
            cmd = ["ansible-lint"] + level_config["ansible_lint_args"] + [temp_file_path]
            
            print(f"🔍 Running: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30  # 30 second timeout
            )
            
            # Parse ansible-lint output
            validation_results = self._parse_ansible_lint_output(
                result.stdout,
                result.stderr, 
                result.returncode,
                level_config["severity_threshold"]
            )
            
            return validation_results
            
        except subprocess.TimeoutExpired:
            return {
                "error": "ansible-lint timed out after 30 seconds",
                "validation_status": "error",
                "issues_found": [],
                "summary": {"total_issues": 0, "errors": 1, "validation_status": "error"}
            }
        except FileNotFoundError:
            return {
                "error": "ansible-lint not found. Please install: pip install ansible-lint",
                "validation_status": "error", 
                "issues_found": [],
                "summary": {"total_issues": 0, "errors": 1, "validation_status": "error"}
            }
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_file_path)
            except OSError:
                pass
    
    def _parse_ansible_lint_output(self, stdout: str, stderr: str, return_code: int, severity_threshold: str) -> Dict[str, Any]:
        """Parse ansible-lint parseable output into structured format"""
        
        issues = []
        
        # Parse stdout (main results)
        if stdout:
            for line in stdout.strip().split('\n'):
                if line.strip():
                    issue = self._parse_lint_line(line)
                    if issue and self._meets_severity_threshold(issue.severity, severity_threshold):
                        issues.append(issue)
        
        # Parse stderr for additional errors
        if stderr and return_code != 0:
            if "WARNING: Listing" in stderr:
                pass  # Just warnings about file discovery - ignore
            elif "CRITICAL" in stderr or "ERROR" in stderr:
                # Critical errors
                issues.append(ValidationIssue(
                    rule_id="ansible-lint-error",
                    severity="error",
                    message=stderr.strip()[:200],  # Truncate long error messages
                    filename="playbook.yml",
                    line_number=None,
                    column_number=None
                ))
        
        # Create summary
        summary = self._create_validation_summary(issues, return_code)
        
        return {
            "validation_status": summary.validation_status,
            "issues_found": [issue.model_dump() for issue in issues],
            "summary": summary.model_dump(),
            "raw_output": {
                "stdout": stdout,
                "stderr": stderr,
                "return_code": return_code
            }
        }
    
    def _parse_lint_line(self, line: str) -> Optional[ValidationIssue]:
        """Parse a single line of ansible-lint parseable output"""
        
        # Expected format: filename:line:column: rule_id: message
        pattern = r'^([^:]+):(\d+):(\d+):\s*([^:]+):\s*(.+)$'
        match = re.match(pattern, line)
        
        if match:
            filename, line_num, col_num, rule_id, message = match.groups()
            
            # Determine severity from rule_id
            severity = self._get_severity_from_rule(rule_id)
            
            return ValidationIssue(
                rule_id=rule_id.strip(),
                severity=severity,
                message=message.strip(),
                filename=filename,
                line_number=int(line_num),
                column_number=int(col_num),
                rule_description=None,  # Could be enhanced later
                suggested_fix=None      # To be filled by LLM
            )
        
        return None
    
    def _get_severity_from_rule(self, rule_id: str) -> str:
        """Determine severity level from ansible-lint rule ID"""
        
        # Some rules are more critical than others
        critical_rules = {
            "syntax-check", "yaml[syntax]", "playbook-extension", 
            "var-naming[no-reserved]", "name[missing]"
        }
        
        warning_rules = {
            "yaml[line-too-long]", "yaml[trailing-spaces]", "yaml[new-line-at-end-of-file]",
            "name[casing]", "risky-file-permissions", "package-latest"
        }
        
        if any(critical in rule_id for critical in critical_rules):
            return "error"
        elif any(warning in rule_id for warning in warning_rules):
            return "warning"
        else:
            return "info"
    
    def _meets_severity_threshold(self, severity: str, threshold: str) -> bool:
        """Check if issue severity meets the threshold"""
        
        severity_levels = {"error": 3, "warning": 2, "info": 1}
        threshold_levels = {"error": 3, "warning": 2, "info": 1}
        
        return severity_levels.get(severity, 1) >= threshold_levels.get(threshold, 1)
    
    def _create_validation_summary(self, issues: List[ValidationIssue], return_code: int) -> ValidationSummary:
        """Create validation summary from issues"""
        
        errors = len([i for i in issues if i.severity == "error"])
        warnings = len([i for i in issues if i.severity == "warning"])
        info = len([i for i in issues if i.severity == "info"])
        total_issues = len(issues)
        
        # Determine overall status
        if errors > 0:
            validation_status = "invalid"
        elif warnings > 0:
            validation_status = "warnings"
        else:
            validation_status = "valid"
        
        # Extract rule information
        failed_rules = list(set([issue.rule_id for issue in issues]))
        passed_rules = []  # Would need enhanced ansible-lint integration to get this
        
        return ValidationSummary(
            total_issues=total_issues,
            errors=errors,
            warnings=warnings,
            info=info,
            validation_status=validation_status,
            passed_rules=passed_rules,
            failed_rules=failed_rules,
            code_quality_score=None  # Calculated elsewhere
        )
