#!/usr/bin/env python3

import os
import tempfile
import subprocess
import json
from pydantic import BaseModel
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
import httpx

# ---- Request/Response Models ----
class PlaybookValidationRequest(BaseModel):
    playbook_content: str

class PlaybookValidationResponse(BaseModel):
    passed: bool
    summary: str
    issues: list
    issues_count: int
    agent_response: str

# ---- Tool Definition ----
@tool
def run_ansible_lint(playbook_code: str) -> dict:
    """
    Run ansible-lint against an Ansible playbook to check for syntax errors, 
    best practices violations, and other issues.
    """
    # Add logging for ansible-lint execution
    import logging
    logger = logging.getLogger(__name__)
    logger.info("=== ANSIBLE-LINT TOOL EXECUTION START ===")
    logger.info(f"Ansible-lint input length: {len(playbook_code)} characters")
    logger.info(f"Ansible-lint input preview: {playbook_code[:200]}...")
    
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".yml") as f:
        f.write(playbook_code)
        fname = f.name
    
    try:
        logger.info(f"Executing ansible-lint on temporary file: {fname}")
        result = subprocess.run(
            ["ansible-lint", fname],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            timeout=180
        )
        output = result.stdout
        passed = result.returncode == 0
        summary = output.strip() if not passed else "No issues found."
        issues = output.strip().splitlines() if not passed else []
        
        logger.info(f"Ansible-lint execution completed")
        logger.info(f"Return code: {result.returncode}")
        logger.info(f"Passed: {passed}")
        logger.info(f"Output length: {len(output)} characters")
        logger.info(f"Output preview: {output[:200]}...")
        logger.info("=== ANSIBLE-LINT TOOL EXECUTION COMPLETE ===")
        
        return {"passed": passed, "summary": summary, "issues": issues}
    except subprocess.TimeoutExpired:
        logger.error("Ansible-lint command timed out")
        logger.info("=== ANSIBLE-LINT TOOL EXECUTION COMPLETE ===")
        return {"passed": False, "summary": "ansible-lint command timed out.", "issues": ["Timeout error."]}
    except Exception as e:
        logger.error(f"Error running ansible-lint: {e}")
        logger.info("=== ANSIBLE-LINT TOOL EXECUTION COMPLETE ===")
        return {"passed": False, "summary": f"Error running ansible-lint: {e}", "issues": [str(e)]}
    finally:
        if os.path.exists(fname):
            os.remove(fname)

# ---- Agent Creation Function ----
def create_ansible_lint_agent():
    """Create the LangGraph agent for Ansible validation."""
    # Hard-coded LLM settings as requested
    llm = ChatOpenAI(
        model="meta-llama/Llama-3.1-8B-Instruct",
        base_url="http://llm-ai-agent.apps.cluster-p4mxv.p4mxv.sandbox338.opentlc.com/v1",
        api_key="not-needed",
        temperature=0.0,
        max_tokens=1000,
        top_p=0.95,
        http_client=httpx.Client(timeout=120.0)
    )
    return create_react_agent(llm, [run_ansible_lint])

# ---- Agent Processing Function ----
def process_playbook_validation(agent, playbook_content: str) -> dict:
    """
    Process playbook validation using the agent and return structured results.
    
    Args:
        agent: The LangGraph agent
        playbook_content: The Ansible playbook content to validate
        
    Returns:
        dict: Structured validation results
    """
    # Add logging for validation processing
    import logging
    logger = logging.getLogger(__name__)
    logger.info("=== VALIDATION PROCESSING START ===")
    logger.info(f"Processing playbook validation for content length: {len(playbook_content)}")
    logger.info(f"Playbook content preview: {playbook_content[:200]}...")
    
    user_message = f"""Please validate this Ansible playbook using ansible-lint:

{playbook_content}

Use the run_ansible_lint tool to check for any issues or best practice violations."""

    # Run agent
    response = agent.invoke({"messages": [{"role": "user", "content": user_message}]})
    
    # Extract results
    tool_result = None
    agent_response = ""
    
    for message in response['messages']:
        if hasattr(message, 'content') and message.content:
            content = str(message.content)
            if content.startswith('{"passed"'):
                try:
                    tool_result = json.loads(content)
                except:
                    pass
            elif not content.startswith('Tool Calls:'):
                agent_response = content
    
    # Return structured results
    if tool_result:
        result = {
            'passed': tool_result.get("passed", False),
            'summary': tool_result.get("summary", ""),
            'issues': tool_result.get("issues", []),
            'issues_count': len(tool_result.get("issues", [])),
            'agent_response': agent_response
        }
        logger.info(f"=== VALIDATION PROCESSING COMPLETE ===")
        logger.info(f"Validation passed: {result['passed']}")
        logger.info(f"Issues count: {result['issues_count']}")
        logger.info(f"Summary: {result['summary'][:200]}...")
        return result
    else:
        result = {
            'passed': False,
            'summary': 'Could not parse validation results',
            'issues': ['Unable to extract tool results'],
            'issues_count': 1,
            'agent_response': agent_response
        }
        logger.info(f"=== VALIDATION PROCESSING COMPLETE ===")
        logger.info(f"Validation failed to parse results")
        return result