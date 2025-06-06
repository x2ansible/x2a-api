"""
Output Processor Helper for ValidationAgent

Handles processing of ansible-lint service output, including issue extraction,
statistics calculation, and recommendation generation.
"""

import logging
from typing import Dict, List, Any

logger = logging.getLogger("OutputProcessor")

class AnsibleLintOutputProcessor:
    """Processes ansible-lint service output into structured results."""
    
    def process_lint_result(self, lint_result: Dict, profile: str, original_length: int) -> Dict[str, Any]:
        """
        Process ansible-lint service result into standardized format.
        
        Args:
            lint_result: Raw result from ansible-lint service
            profile: Lint profile used
            original_length: Original playbook length
            
        Returns:
            Standardized validation result dictionary
        """
        exit_code = lint_result.get('exit_code', -1)
        stdout = lint_result.get('stdout', '')
        stderr = lint_result.get('stderr', '')
        
        validation_passed = exit_code == 0
        
        if validation_passed:
            return self._create_success_result(exit_code, stdout, stderr, profile, original_length)
        else:
            return self._create_failure_result(exit_code, stdout, stderr, profile, original_length)
    
    def _create_success_result(self, exit_code: int, stdout: str, stderr: str, 
                             profile: str, original_length: int) -> Dict[str, Any]:
        """Create result for successful validation."""
        logger.info(" Playbook validation PASSED!")
        
        return {
            "validation_passed": True,
            "exit_code": exit_code,
            "message": " Playbook successfully passed all lint checks",
            "summary": {
                "passed": True,
                "violations": 0,
                "warnings": 0,
                "total_issues": 0,
                "profile_used": profile
            },
            "issues": [],
            "recommendations": [],
            "raw_output": {"stdout": stdout, "stderr": stderr},
            "playbook_length": original_length,
            "lint_profile": profile
        }
    
    def _create_failure_result(self, exit_code: int, stdout: str, stderr: str,
                             profile: str, original_length: int) -> Dict[str, Any]:
        """Create result for failed validation."""
        logger.warning(f" Playbook validation FAILED (exit_code: {exit_code})")
        
        # Parse issues from output
        issues = self._extract_issues_from_output(stdout, stderr)
        summary_stats = self._calculate_summary_statistics(issues, stderr, profile)
        recommendations = self._generate_fix_recommendations(issues)
        
        return {
            "validation_passed": False,
            "exit_code": exit_code,
            "message": f" Playbook validation failed - {summary_stats['total_issues']} issues found",
            "summary": summary_stats,
            "issues": issues,
            "recommendations": recommendations,
            "raw_output": {"stdout": stdout, "stderr": stderr},
            "playbook_length": original_length,
            "lint_profile": profile
        }
    
    def _extract_issues_from_output(self, stdout: str, stderr: str) -> List[Dict]:
        """Extract structured issues from ansible-lint output."""
        issues = []
        
        try:
            lines = stdout.split('\n')
            
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                if not line or line.startswith('~'):
                    continue
                
                # Parse rule violations: "rule[specific]: description"
                if '[' in line and ']:' in line:
                    issue = self._parse_rule_violation(line, line_num, stderr)
                    if issue:
                        issues.append(issue)
                        
        except Exception as e:
            logger.warning(f"⚠️ Failed to parse issues from output: {e}")
        
        logger.info(f"📊 Extracted {len(issues)} issues from lint output")
        return issues
    
    def _parse_rule_violation(self, line: str, line_num: int, stderr: str) -> Dict:
        """Parse a single rule violation line."""
        parts = line.split(']:')
        if len(parts) < 2:
            return None
            
        rule_part = parts[0]
        description = parts[1].strip()
        
        # Extract rule information
        if '[' not in rule_part:
            return None
            
        rule_category = rule_part.split('[')[0].strip()
        rule_specific = rule_part.split('[')[1].rstrip(']')
        
        # Determine severity
        severity = self._determine_severity(stderr, line)
        
        return {
            "rule": f"{rule_category}[{rule_specific}]",
            "category": rule_category,
            "specific_rule": rule_specific,
            "description": description,
            "severity": severity,
            "file": "playbook.yml",
            "line": line_num
        }
    
    def _determine_severity(self, stderr: str, line: str) -> str:
        """Determine issue severity from context."""
        stderr_lower = stderr.lower()
        line_lower = line.lower()
        
        if any(word in stderr_lower for word in ["fatal", "critical"]):
            return "fatal"
        elif any(word in stderr_lower or word in line_lower for word in ["warning", "warn"]):
            return "warning"
        else:
            return "error"
    
    def _calculate_summary_statistics(self, issues: List[Dict], stderr: str, profile: str) -> Dict[str, Any]:
        """Calculate summary statistics from issues."""
        violations = len([i for i in issues if i.get("severity") in ["fatal", "error"]])
        warnings = len([i for i in issues if i.get("severity") == "warning"])
        
        return {
            "passed": False,
            "violations": violations,
            "warnings": warnings,
            "total_issues": len(issues),
            "has_fatal": any(i.get("severity") == "fatal" for i in issues),
            "profile_used": profile
        }
    
    def _generate_fix_recommendations(self, issues: List[Dict]) -> List[Dict]:
        """Generate actionable fix recommendations."""
        recommendations = []
        
        # Group issues by rule for better recommendations
        rule_groups = {}
        for issue in issues:
            rule = issue.get("specific_rule", "unknown")
            if rule not in rule_groups:
                rule_groups[rule] = []
            rule_groups[rule].append(issue)
        
        for rule, rule_issues in rule_groups.items():
            recommendation = self._get_rule_recommendation(rule, rule_issues)
            if recommendation:
                recommendations.append(recommendation)
        
        logger.info(f"💡 Generated {len(recommendations)} recommendations")
        return recommendations
    
    def _get_rule_recommendation(self, rule: str, issues: List[Dict]) -> Dict[str, Any]:
        """Get specific recommendation for a rule."""
        rule_recommendations = {
            "unknown-module": {
                "recommendation": "Install missing collection or fix module name",
                "action": "Add 'collections:' section or use fully qualified collection name",
                "example": "Use 'ansible.posix.firewalld' instead of 'firewalld'"
            },
            "syntax-check": {
                "recommendation": "Fix YAML syntax errors",
                "action": "Check YAML indentation and structure",
                "example": "Ensure proper spacing and no tabs in YAML"
            },
            "name": {
                "recommendation": "Add descriptive names to tasks",
                "action": "Add 'name:' field to all tasks and plays",
                "example": "- name: Install nginx package"
            },
            "yaml": {
                "recommendation": "Fix YAML formatting issues",
                "action": "Follow YAML best practices for indentation and structure",
                "example": "Use consistent 2-space indentation"
            },
            "risky-file-permissions": {
                "recommendation": "Use specific file permissions instead of overly permissive ones",
                "action": "Replace mode '777' or '666' with more restrictive permissions",
                "example": "Use mode: '0644' for files, '0755' for directories"
            },
            "package-latest": {
                "recommendation": "Pin package versions for reproducible deployments",
                "action": "Replace 'state: latest' with 'state: present' and specific version",
                "example": "state: present, version: '1.2.3'"
            }
        }
        
        recommendation_template = rule_recommendations.get(rule, {
            "recommendation": f"Review and fix {rule} issues",
            "action": "Consult ansible-lint documentation for specific rule guidance",
            "example": ""
        })
        
        return {
            "rule": f"*[{rule}]",
            "count": len(issues),
            "recommendation": recommendation_template["recommendation"],
            "action": recommendation_template["action"],
            "example": recommendation_template.get("example", "")
        }