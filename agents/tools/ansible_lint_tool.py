"""
Ansible Lint Tool for LlamaStack Agent Integration
Validates Ansible playbooks using ansible-lint CLI with structured output
"""

import subprocess
import tempfile
import shutil
import os
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Remove the broken decorator and import

def ansible_lint_tool(playbook: str, lint_profile: str = "basic", correlation_id: str = None) -> Dict[str, Any]:
    """
    Lint an Ansible playbook using the local ansible-lint CLI.
    
    This tool provides comprehensive Ansible playbook validation including:
    - Syntax and structure validation
    - Best practice compliance checking
    - Security and style guideline enforcement
    - Detailed issue reporting with line numbers
    - Support for different linting profiles
    
    :param playbook: YAML playbook string content
    :param lint_profile: ansible-lint profile to use (default: basic)
    :param correlation_id: Optional correlation ID for logging and tracking
    :return: Structured validation results with issues and recommendations
    """
    try:
        # Handle string input (convert from JSON string if needed)
        if isinstance(playbook, str):
            playbook_content = playbook.strip()
        else:
            logger.error(f"[{correlation_id}] Playbook parameter is not a string: {type(playbook)}")
            return _create_empty_validation_structure()
        
        tmpdir = tempfile.mkdtemp()
        playbook_path = os.path.join(tmpdir, "playbook.yml")
        
        try:
            with open(playbook_path, "w", encoding="utf-8") as f:
                f.write(playbook_content)
        except Exception as e:
            logger.error(f"[{correlation_id}] Failed to write playbook to temp file: {e}")
            return _create_empty_validation_structure()
        
        logger.info(f"[{correlation_id}] Starting ansible-lint analysis with profile: {lint_profile}")
        
        cmd = [
            "ansible-lint",
            "--nocolor",
            "--offline",              # Do not fetch requirements for faster, safer runs
            "--format", "sarif",      # SARIF output for robust parsing
            "--profile", lint_profile,
            playbook_path
        ]
        
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        exit_code = proc.returncode

        # Parse SARIF results
        issues = []
        try:
            sarif = json.loads(proc.stdout)
            if "runs" in sarif and sarif["runs"]:
                for iss in sarif["runs"][0].get("results", []):
                    msg = iss.get("message", {}).get("text", "")
                    rule_id = iss.get("ruleId")
                    locations = iss.get("locations", [{}])[0].get("physicalLocation", {})
                    file_path = locations.get("artifactLocation", {}).get("uri", "playbook.yml")
                    region = locations.get("region", {})
                    start_line = region.get("startLine")
                    severity = iss.get("level", "warning")
                    issues.append({
                        "rule": rule_id,
                        "description": msg,
                        "filename": file_path,
                        "line": start_line,
                        "severity": severity,
                        "raw": iss
                    })
        except Exception as e:
            logger.warning(f"[{correlation_id}] Failed to parse SARIF output: {e}")
            issues = [{
                "rule": "sarif-parse-error",
                "description": f"Failed to parse SARIF output: {e}",
                "filename": "playbook.yml",
                "severity": "fatal"
            }]

        validation_passed = (exit_code == 0) and not issues

        summary = {
            "passed": validation_passed,
            "violations": sum(1 for i in issues if i["severity"] in ("error", "fatal")),
            "warnings": sum(1 for i in issues if i["severity"] == "warning"),
            "total_issues": len(issues)
        }

        recommendations = [
            {"issue": i["rule"], "recommendation": f"Review and resolve: {i['rule']}"} for i in issues
        ]

        logger.info(f"[{correlation_id}] ansible-lint analysis completed")
        logger.info(f"[{correlation_id}] Found {len(issues)} issues, validation passed: {validation_passed}")

        return {
            "validation_passed": validation_passed,
            "exit_code": exit_code,
            "message": (
                "Playbook passed all lint checks."
                if validation_passed else
                f"Playbook failed lint checks ({len(issues)} issues)."
            ),
            "summary": summary,
            "issues": issues,
            "recommendations": recommendations,
            "raw_output": {
                "cmd": " ".join(cmd),
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            },
        }
        
    except subprocess.TimeoutExpired:
        logger.error(f"[{correlation_id}] ansible-lint timed out")
        return {
            "validation_passed": False,
            "exit_code": -3,
            "message": "ansible-lint timed out.",
            "summary": {
                "passed": False,
                "violations": 1,
                "warnings": 0,
                "total_issues": 1,
                "error": True
            },
            "issues": [{
                "rule": "tool-timeout",
                "description": "ansible-lint timed out",
                "filename": "playbook.yml",
                "severity": "fatal"
            }],
            "recommendations": [],
            "raw_output": {},
        }
    except Exception as e:
        logger.error(f"[{correlation_id}] ansible-lint error: {e}")
        return {
            "validation_passed": False,
            "exit_code": -4,
            "message": f"ansible-lint error: {e}",
            "summary": {
                "passed": False,
                "violations": 1,
                "warnings": 0,
                "total_issues": 1,
                "error": True
            },
            "issues": [{
                "rule": "tool-exception",
                "description": f"ansible-lint error: {e}",
                "filename": "playbook.yml",
                "severity": "fatal"
            }],
            "recommendations": [],
            "raw_output": {},
        }
    finally:
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception as e:
            logger.warning(f"[{correlation_id}] Failed to cleanup temp directory: {e}")

def _create_empty_validation_structure() -> Dict[str, Any]:
    """Create empty validation structure when ansible-lint analysis fails."""
    return {
        "validation_passed": False,
        "exit_code": -1,
        "message": "ansible-lint analysis failed",
        "summary": {
            "passed": False,
            "violations": 1,
            "warnings": 0,
            "total_issues": 1,
            "error": True
        },
        "issues": [{
            "rule": "tool-failure",
            "description": "ansible-lint tool failed to execute",
            "filename": "playbook.yml",
            "severity": "fatal"
        }],
        "recommendations": [],
        "raw_output": {},
    }
