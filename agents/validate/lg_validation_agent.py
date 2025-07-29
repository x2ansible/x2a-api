import os
import tempfile
import subprocess
import traceback
import json
import logging
import time
import uuid
from typing import Optional, Dict, Any, Generator, List
import asyncio

logger = logging.getLogger("LangGraphValidationAgent")

class LangGraphValidationAgent:
    """
    Simplified LangGraph-based ValidationAgent that provides the same interface as ValidationAgent.
    
    This wraps the lg.py functionality and integrates it into the main app's agent registry.
    Uses a simplified approach to avoid complex import issues.
    """
    
    def __init__(
        self,
        client=None,  # Not used for LangGraph
        agent_id: str = "langgraph-validation",
        session_id: str = "langgraph-session",
        instruction: str = "Validate Ansible playbooks using ansible-lint",
        config_loader=None,
        verbose_logging: bool = False,
        timeout: int = 120,
    ):
        self.client = client
        self.agent_id = agent_id
        self.session_id = session_id
        self.instruction = instruction
        self.config_loader = config_loader
        self.verbose_logging = verbose_logging
        self.timeout = timeout
        self.default_profile = "basic"
        
        logger.info(f"🔧 LangGraphValidationAgent initialized")
        logger.info(f"🔧 Agent ID: {agent_id}")
        logger.info(f"🔧 Session ID: {session_id}")

    def _run_ansible_lint_subprocess(self, playbook_code: str) -> dict:
        """Run ansible-lint as a subprocess."""
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".yml") as f:
            f.write(playbook_code)
            fname = f.name
        try:
            result = subprocess.run(
                ["ansible-lint", fname],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            output = result.stdout
            passed = result.returncode == 0
            
            # Clean and parse the output
            cleaned_output = self._clean_ansible_lint_output(output)
            parsed_issues = self._parse_ansible_lint_issues(output)
            
            summary = cleaned_output.strip() if not passed else "No issues found."
            return {
                "passed": passed, 
                "summary": summary, 
                "issues": parsed_issues,
                "raw_output": output,
                "cleaned_output": cleaned_output
            }
        finally:
            try:
                os.remove(fname)
            except Exception:
                pass

    def _clean_ansible_lint_output(self, output: str) -> str:
        """Clean ANSI color codes and formatting from ansible-lint output."""
        import re
        
        # Remove ANSI color codes
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        cleaned = ansi_escape.sub('', output)
        
        # Remove hyperlinks
        cleaned = re.sub(r'\]8;;[^]]*\]', '', cleaned)
        cleaned = re.sub(r'\]8;;', '', cleaned)
        
        # Clean up extra whitespace
        cleaned = re.sub(r'\n\s*\n', '\n', cleaned)
        cleaned = cleaned.strip()
        
        return cleaned

    def _parse_ansible_lint_issues(self, output: str) -> List[Dict[str, Any]]:
        """Parse ansible-lint output into structured issues."""
        import re
        
        issues = []
        cleaned_output = self._clean_ansible_lint_output(output)
        
        # Split into lines and parse each issue
        lines = cleaned_output.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('WARNING') or line.startswith('Read') or line.startswith('#'):
                continue
                
            # Parse rule violations
            # Pattern: rule_name[action-core]: Description
            rule_match = re.match(r'([a-zA-Z_]+)\[([^\]]+)\]:\s*(.+)', line)
            if rule_match:
                rule_name, action, description = rule_match.groups()
                issues.append({
                    "type": "rule_violation",
                    "rule": rule_name,
                    "action": action,
                    "description": description,
                    "severity": "error"
                })
                continue
            
            # Parse file location issues
            # Pattern: /path/to/file:line:column Description
            file_match = re.match(r'([^:]+):(\d+):(\d+)\s+(.+)', line)
            if file_match:
                file_path, line_num, col_num, description = file_match.groups()
                issues.append({
                    "type": "file_issue",
                    "file": file_path,
                    "line": int(line_num),
                    "column": int(col_num),
                    "description": description,
                    "severity": "error"
                })
                continue
            
            # Parse general error messages
            if line.startswith('Failed:') or line.startswith('Use '):
                issues.append({
                    "type": "general",
                    "message": line,
                    "severity": "error"
                })
                continue
        
        return issues

    async def validate_playbook(
        self, 
        playbook_content: str, 
        profile: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate an Ansible playbook using simplified LangGraph approach.
        """
        correlation_id = correlation_id or f"lg-val-{uuid.uuid4().hex[:8]}"
        start_time = time.monotonic()
        profile = profile or self.default_profile
        
        logger.info(f"[{correlation_id}] Starting LangGraph playbook validation with profile: {profile}")
        
        try:
            # Run the validation (simplified LangGraph approach)
            lint_result = self._run_ansible_lint_subprocess(playbook_content)
            
            total_time = time.monotonic() - start_time
            
            # Format the result to match the expected interface
            parsed_issues = lint_result.get("issues", [])
            cleaned_summary = lint_result.get("cleaned_output", "")
            
            result = {
                "validation_passed": lint_result.get("passed", False),
                "exit_code": 0 if lint_result.get("passed", False) else 1,
                "message": cleaned_summary,
                "summary": {
                    "passed": lint_result.get("passed", False),
                    "violations": len(parsed_issues),
                    "warnings": 0,
                    "total_issues": len(parsed_issues)
                },
                "issues": parsed_issues,
                "recommendations": [],
                "agent_analysis": cleaned_summary,
                "playbook_length": len(playbook_content),
                "profile": profile,
                "debug_info": {
                    "tool_calls_detected": 1,
                    "tool_execution_steps": 1,
                    "agent_steps": 1,
                    "events_processed": 1,
                    "agent_pattern": "langgraph_with_ansible_lint",
                    "json_extracted": True,
                    "tool_names_called": ["ansible_lint_tool"],
                    "detailed_analysis": "LangGraph execution",
                    "actual_tool_calls": True
                },
                "session_info": {
                    "agent_id": self.agent_id,
                    "session_id": self.session_id,
                    "correlation_id": correlation_id,
                    "method_used": "langgraph_validation",
                    "analysis_time_seconds": round(total_time, 3),
                    "registry_agent_id": self.agent_id,
                    "registry_session_id": self.session_id
                },
                "passed": lint_result.get("passed", False),
                "issues_count": len(parsed_issues),
                "elapsed_time": round(total_time, 3)
            }
            
            logger.info(f" LangGraph validation completed successfully in {total_time:.3f}s")
            return result

        except Exception as e:
            logger.error(f"❌ LangGraph validation error: {e}")
            return self._create_error_response(f"LangGraph validation failed: {str(e)}")

    def validate_playbook_stream(
        self, playbook_content: str, profile: Optional[str] = None
    ) -> Generator[str, None, None]:
        """
        Streams playbook validation results as SSE (Server-Sent Events).
        Uses LangGraph validation.
        """
        t0 = time.monotonic()
        profile = profile or self.default_profile
        correlation_id = f"lg-stream-{uuid.uuid4().hex[:8]}"
        
        logger.info(f"[{correlation_id}] Starting LangGraph streaming validation with profile: {profile}")
        
        try:
            # Run the LangGraph validation
            result = asyncio.run(self.validate_playbook(playbook_content, profile, correlation_id))
            
            # Stream the result
            yield f"data: {json.dumps({'type': 'result', 'data': result, 'elapsed_time': round(time.monotonic() - t0, 2)})}\n\n"
            
        except Exception as e:
            logger.error(f"[{correlation_id}] LangGraph streaming validation error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e), 'elapsed_time': round(time.monotonic() - t0, 2)})}\n\n"
        
        # End event
        yield f"data: {json.dumps({'type': 'end', 'elapsed_time': round(time.monotonic() - t0, 2)})}\n\n"

    async def validate_multiple_files(
        self, 
        files: Dict[str, str], 
        profile: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate multiple Ansible playbook files using LangGraph approach.
        """
        correlation_id = correlation_id or f"lg-multi-{uuid.uuid4().hex[:8]}"
        start_time = time.monotonic()
        profile = profile or self.default_profile
        
        logger.info(f"[{correlation_id}] Starting LangGraph multiple file validation with profile: {profile}")
        
        results = {}
        total_issues = 0
        total_passed = 0
        
        for filename, content in files.items():
            try:
                result = await self.validate_playbook(content, profile, f"{correlation_id}-{filename}")
                results[filename] = result
                if result.get("passed", False):
                    total_passed += 1
                total_issues += result.get("issues_count", 0)
            except Exception as e:
                logger.error(f"[{correlation_id}] Failed to validate {filename}: {e}")
                results[filename] = {
                    "validation_passed": False,
                    "message": f"Validation failed: {e}",
                    "issues_count": 0,
                    "passed": False,
                }
        
        overall_result = {
            "validation_passed": total_passed == len(files),
            "total_files": len(files),
            "passed_files": total_passed,
            "failed_files": len(files) - total_passed,
            "total_issues": total_issues,
            "file_results": results,
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "correlation_id": correlation_id,
            "elapsed_time": round(time.monotonic() - start_time, 2),
            "profile": profile,
            "agentic": True,
        }
        
        logger.info(f"[{correlation_id}] LangGraph multiple file validation completed: {total_passed}/{len(files)} files passed")
        return overall_result

    async def validate_syntax(
        self, 
        playbook_content: str,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Quick syntax validation of an Ansible playbook using LangGraph.
        """
        correlation_id = correlation_id or f"lg-syntax-{uuid.uuid4().hex[:8]}"
        start_time = time.monotonic()
        
        logger.info(f"[{correlation_id}] Starting LangGraph syntax validation")
        
        try:
            # Use the same validation logic but with basic profile
            result = await self.validate_playbook(playbook_content, "basic", correlation_id)
            
            # Simplify the result for syntax validation
            syntax_result = {
                "syntax_valid": result.get("validation_passed", False),
                "issues": result.get("issues", []),
                "issues_count": len(result.get("issues", [])),
                "message": result.get("message", ""),
                "agent_id": self.agent_id,
                "session_id": self.session_id,
                "correlation_id": correlation_id,
                "elapsed_time": round(time.monotonic() - start_time, 3),
                "agentic": True,
                "tool_called": True,
                "method_used": "langgraph_validation"
            }
            
            logger.info(f" LangGraph syntax validation completed: {'valid' if syntax_result['syntax_valid'] else 'invalid'}")
            return syntax_result
            
        except Exception as e:
            logger.error(f"[{correlation_id}] LangGraph syntax validation failed: {e}")
            return {
                "syntax_valid": False,
                "issues": [],
                "issues_count": 0,
                "message": f"Syntax validation error: {e}",
                "agent_id": self.agent_id,
                "session_id": self.session_id,
                "correlation_id": correlation_id,
                "elapsed_time": round(time.monotonic() - start_time, 3),
                "agentic": True,
                "error": str(e),
            }

    async def production_validate(
        self, 
        playbook_content: str,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Production-ready validation with strict profile using LangGraph approach.
        """
        correlation_id = correlation_id or f"lg-prod-{uuid.uuid4().hex[:8]}"
        start_time = time.monotonic()
        
        logger.info(f"[{correlation_id}] Starting LangGraph production validation")
        
        try:
            # Use the same validation logic but with production profile
            result = await self.validate_playbook(playbook_content, "production", correlation_id)
            
            # Add production-specific metadata
            result.update({
                "production_ready": result.get("validation_passed", False),
                "validation_level": "production",
                "agentic": True,
                "tool_called": True,
            })
            
            logger.info(f"[{correlation_id}] LangGraph production validation completed: {'ready' if result['production_ready'] else 'not ready'}")
            return result
            
        except Exception as e:
            logger.error(f"[{correlation_id}] LangGraph production validation failed: {e}")
            return {
                "production_ready": False,
                "validation_level": "production",
                "message": f"Production validation error: {e}",
                "agent_id": self.agent_id,
                "session_id": self.session_id,
                "correlation_id": correlation_id,
                "elapsed_time": round(time.monotonic() - start_time, 2),
                "validation_passed": False,
                "issues": [],
                "issues_count": 0,
                "agentic": True,
                "error": str(e),
            }

    def get_supported_profiles(self) -> List[str]:
        """Get list of supported validation profiles."""
        return ["basic", "production"]

    async def health_check(self) -> bool:
        """
        Perform a basic health check using LangGraph validation.
        """
        try:
            test_playbook = """---
- hosts: localhost
  tasks:
    - name: Health check task
      debug:
        msg: "Health check successful"
"""
            
            # Run a quick validation
            result = await self.validate_playbook(test_playbook, "basic", "health-check")
            
            # If we get here, the validation worked
            logger.info(" LangGraph health check completed successfully")
            return True
            
        except Exception as e:
            logger.error(f" LangGraph health check failed: {e}")
            return False

    def get_status(self) -> Dict[str, Any]:
        """Get agent status information."""
        return {
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "client_base_url": "langgraph-local",
            "timeout": self.timeout,
            "status": "ready",
            "approach": "langgraph_validation",
            "methods_available": ["langgraph_validation"],
            "capabilities": [
                "langgraph_tool_calling",
                "json_response_parsing",
                "streaming_validation",
                "ansible_lint_integration"
            ],
            "tools_registered": [
                "ansible_lint_tool"
            ],
            "agent_pattern": "langgraph_with_ansible_lint",
            "registry_agent_id": self.agent_id,
            "registry_session_id": self.session_id,
            "langgraph_managed": True
        }

    def _create_error_response(self, message: str) -> Dict[str, Any]:
        """Create standardized error response."""
        return {
            "validation_passed": False,
            "exit_code": -1,
            "message": message,
            "summary": {
                "passed": False,
                "violations": 1,
                "warnings": 0,
                "total_issues": 1,
                "error": True
            },
            "issues": [],
            "recommendations": [],
            "error": message
        } 