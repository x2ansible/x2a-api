import logging
import requests
import time
from typing import Dict

logger = logging.getLogger("ansible_lint_tool")

SERVICE_URL = "https://lint-api-route-convert2ansible.apps.prod.rhoai.rh-aiservices-bu.com/v1/lint"
VALID_PROFILES = ("basic", "production", "safety", "test", "minimal")
REQUEST_TIMEOUT = 60

def ansible_lint_tool(playbook: str, profile: str = "basic") -> Dict:
    """
    Validate an Ansible playbook using ansible-lint and return lint issues, recommendations, and raw output.

    :param playbook: Ansible playbook YAML content to validate.
    :param profile: Ansible-lint profile to use. One of: basic, production, safety, test, minimal.
    :return: Dictionary containing validation status, issues, recommendations, and raw service output.
    """
    start_time = time.time()

    # Input validation
    if not isinstance(playbook, str) or not playbook.strip():
        return _error("Playbook content must be a non-empty string.", code=-10)
    if len(playbook) > 1024 * 1024:
        return _error("Playbook content exceeds 1MB.", code=-11)
    if profile not in VALID_PROFILES:
        logger.warning(f"Invalid profile '{profile}', defaulting to 'basic'")
        profile = "basic"

    try:
        url = f"{SERVICE_URL}/{profile}"
        files = {'file': ('playbook.yml', playbook.encode('utf-8'), 'application/x-yaml')}
        headers = {
            "accept": "application/json",
            "User-Agent": "x2ansible-lint-tool/1.0"
        }
        response = requests.post(url, files=files, headers=headers, timeout=REQUEST_TIMEOUT)

        if not response.ok:
            return _error(
                f"Lint service returned HTTP {response.status_code}: {response.text[:300]}", 
                code=response.status_code
            )

        result = response.json()
        return _process_lint_result(result, playbook, profile, time.time() - start_time)

    except requests.exceptions.Timeout:
        return _error("Lint service timed out.", code=408)
    except Exception as exc:
        logger.exception(f"Ansible lint tool error: {exc}")
        return _error(f"Internal error: {exc}")

def _process_lint_result(service_result, playbook, profile, elapsed):
    exit_code = service_result.get("exit_code", -1)
    stdout = service_result.get("stdout", "")
    stderr = service_result.get("stderr", "")

    validation_passed = (exit_code == 0)
    issues = _parse_issues(stdout, stderr)

    violations = len([i for i in issues if i.get("severity") in ("error", "fatal")])
    warnings = len([i for i in issues if i.get("severity") == "warning"])

    return {
        "validation_passed": validation_passed,
        "exit_code": exit_code,
        "message": _status_message(validation_passed, len(issues)),
        "summary": {
            "passed": validation_passed,
            "violations": violations,
            "warnings": warnings,
            "total_issues": len(issues),
            "profile_used": profile,
        },
        "issues": issues,
        "recommendations": _recommendations(issues),
        "raw_output": {
            "stdout": stdout,
            "stderr": stderr,
            "service_result": service_result
        },
        "playbook_length": len(playbook),
        "lint_profile": profile,
        "processing_time": round(elapsed, 2),
        "tool_version": "1.0.0",
        "service_metadata": {
            "service_url": SERVICE_URL,
            "profile": profile,
            "exit_code": exit_code,
            "timestamp": time.time()
        }
    }

def _parse_issues(stdout, stderr):
    issues = []
    if not stdout:
        return issues
    for line in stdout.splitlines():
        if not line or ':' not in line or '[' not in line or ']' not in line:
            continue
        try:
            parts = line.split(':', 2)
            if len(parts) < 3:
                continue
            filename, line_num, rest = parts
            rule_start = rest.find('[')
            rule_end = rest.find(']')
            rule = rest[rule_start+1:rule_end]
            description = rest[rule_end+1:].strip()
            issues.append({
                "rule": rule,
                "description": description,
                "filename": filename.strip(),
                "line": int(line_num.strip()) if line_num.strip().isdigit() else None,
                "severity": _severity(rule, description),
                "raw_line": line,
            })
        except Exception as e:
            logger.debug(f"Could not parse issue line: {line}: {e}")
    if stderr and stderr.strip():
        issues.append({
            "rule": "stderr",
            "description": stderr.strip(),
            "severity": "error",
            "raw_line": stderr
        })
    return issues

def _severity(rule, description):
    rule = rule.lower()
    desc = description.lower()
    if any(x in rule for x in ("error", "fatal", "syntax")): return "error"
    if any(x in desc for x in ("deprecated", "warning", "should")): return "warning"
    return "warning"

def _recommendations(issues):
    # Group issues by rule for simple recs
    recs = []
    if not issues:
        return recs
    rule_counts = {}
    for issue in issues:
        rule = issue.get("rule")
        rule_counts[rule] = rule_counts.get(rule, 0) + 1
    for rule, count in rule_counts.items():
        recs.append({
            "rule": rule,
            "count": count,
            "recommendation": f"Fix {count} instance(s) of '{rule}'",
        })
    return recs

def _status_message(validation_passed, n_issues):
    if validation_passed:
        return "Playbook validation passed"
    else:
        return f"Playbook validation failed with {n_issues} issue(s)"

def _error(message, code=-1):
    return {
        "validation_passed": False,
        "exit_code": code,
        "message": message,
        "summary": {
            "passed": False,
            "violations": 1,
            "warnings": 0,
            "total_issues": 1,
            "error": True,
        },
        "issues": [{
            "rule": "error",
            "description": message,
            "severity": "error",
        }],
        "recommendations": [],
        "raw_output": {},
    }
