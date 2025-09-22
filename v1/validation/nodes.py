"""
Validation Agent Workflow Nodes

ReAct agent-based Ansible validation with iterative fixing.
All nodes organized in a single file for maintainability.
"""

import re
import uuid
import json
from datetime import datetime
from typing import Dict, Any

from langgraph.store.base import BaseStore
from langgraph.prebuilt import create_react_agent
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate

from validation.state import (
    ValidationState, 
    ValidationIssue,
    ValidationSummary,
    get_user_id_from_config, 
    should_continue_fixing,
    has_critical_errors,
    log_validation_attempt,
    save_successful_validation
)
from validation.utils import get_llm, AnsibleLintTool

# ============================================================================
# CONFIG LOADING UTILITIES
# ============================================================================

def _load_config_sync():
    """Load configuration from v1/config.yaml"""
    from pathlib import Path
    import yaml
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def get_prompts():
    """Get configured prompts for validation agent"""
    config = _load_config_sync()
    return config.get('prompts', {}).get('validation', {})

def get_prompt(prompt_name: str, default: str = "") -> str:
    """Get a specific validation prompt by name with fallback to default"""
    prompts = get_prompts()
    return prompts.get(prompt_name, default)


# ============================================================================
# GLOBAL COMPONENTS
# ============================================================================

# Initialize components once
llm = get_llm()
ansible_lint_tool = AnsibleLintTool()

# LLM Prompts for fixing - load from config
ITERATIVE_FIX_PROMPT = ChatPromptTemplate.from_messages([
    ("system", get_prompt('iterative_fix_system')),
    ("user", get_prompt('iterative_fix_user'))
])

# Create fixing chain
code_fixer = ITERATIVE_FIX_PROMPT | llm


# ============================================================================
# REACT AGENT SYSTEM PROMPT
# ============================================================================

# Load from config
VALIDATION_AGENT_SYSTEM_PROMPT = get_prompt('system')


# ============================================================================
# WORKFLOW NODES
# ============================================================================

def extract_ansible_code(state: ValidationState, config: RunnableConfig = None, *, store: BaseStore = None) -> ValidationState:
    """Extract Ansible code from state or chat messages"""
    print("📝 Extracting Ansible code...")
    
    # Check if ansible_code is already provided in state
    ansible_code = state.get("ansible_code", "") if isinstance(state, dict) else getattr(state, "ansible_code", "")
    
    if not ansible_code:
        # Fallback: extract from messages
        print("  📝 No direct ansible_code found, extracting from messages...")
        messages = state.get("messages", [])
        
        # Find the most recent human message with Ansible code
        for message in reversed(messages):
            if hasattr(message, 'content') and message.content:
                content = message.content
                
                # Handle both string and list content types
                if isinstance(content, list):
                    # Join list content or extract text from structured content
                    content_parts = []
                    for part in content:
                        if isinstance(part, dict) and 'text' in part:
                            content_parts.append(part['text'])
                        elif isinstance(part, str):
                            content_parts.append(part)
                        else:
                            content_parts.append(str(part))
                    content = '\n'.join(content_parts)
                elif not isinstance(content, str):
                    content = str(content)
                
                # Look for code blocks (markdown format)
                code_match = re.search(r'```(?:yaml|yml)?\n(.*?)\n```', content, re.DOTALL)
                if code_match:
                    ansible_code = code_match.group(1)
                    break
                
                # Look for Ansible-specific content
                if any(keyword in content.lower() for keyword in ["playbook", "tasks:", "hosts:", "- name:"]):
                    ansible_code = content
                    break
        
        if not ansible_code and messages:
            # Fallback: use the last human message
            last_content = messages[-1].content if messages[-1].content else ""
            if isinstance(last_content, list):
                # Handle list content
                content_parts = []
                for part in last_content:
                    if isinstance(part, dict) and 'text' in part:
                        content_parts.append(part['text'])
                    elif isinstance(part, str):
                        content_parts.append(part)
                    else:
                        content_parts.append(str(part))
                ansible_code = '\n'.join(content_parts)
            elif not isinstance(last_content, str):
                ansible_code = str(last_content)
            else:
                ansible_code = last_content
    else:
        print("  📄 Using provided ansible_code from state")
    
    print(f"📄 Extracted Ansible code: {len(ansible_code)} characters")
    
    # Get user_id from config for memory namespacing
    user_id = get_user_id_from_config(config)
    
    # Log extraction to memory if available
    if store:
        try:
            extraction_namespace = (user_id, "code_extractions")
            extraction_log = {
                "ansible_code_length": len(ansible_code),
                "timestamp": datetime.now().isoformat(),
                "has_code": bool(ansible_code),
                "validation_type": "ansible"
            }
            store.put(extraction_namespace, str(uuid.uuid4()), extraction_log)
        except Exception as e:
            print(f"⚠️ Memory logging error: {e}")
    
    return {
        **state,
        "ansible_code": ansible_code,
        "original_code": ansible_code,
        "current_code": ansible_code,
        "current_iteration": 0,
        "validation_complete": False,
        "issues_found": [],
        "iteration_history": [],
        "fixes_applied": [],
        "progress_stalled": False,
        "llm_analysis": "",
        "suggested_fixes": []
    }


def create_validation_react_agent():
    """Create ReAct agent for intelligent validation"""
    tools = [ansible_lint_tool]
    
    return create_react_agent(llm, tools, prompt=VALIDATION_AGENT_SYSTEM_PROMPT)


def validate_and_analyze(state: ValidationState, config: RunnableConfig = None, *, store: BaseStore = None) -> ValidationState:
    """Main validation node using ReAct agent"""
    print("🔍 Validating Ansible code with ReAct agent...")
    
    # Handle both dict and ValidationState objects
    current_code = state.get('current_code', '') if isinstance(state, dict) else state.current_code
    if not current_code:
        return {**state, "error_message": "No Ansible code provided for validation"}
    
    # Log validation attempt
    user_id = get_user_id_from_config(config)
    if store:
        log_validation_attempt(store, user_id, state)
    
    try:
        # Create ReAct agent
        validation_agent = create_validation_react_agent()
        
        # Get state values (handle both dict and ValidationState)
        validation_level = state.get('validation_level', 'standard') if isinstance(state, dict) else state.validation_level
        current_iteration = state.get('current_iteration', 0) if isinstance(state, dict) else state.current_iteration
        enable_auto_fix = state.get('enable_auto_fix', True) if isinstance(state, dict) else state.enable_auto_fix
        
        # Prepare validation request
        validation_request = f"""Please validate this Ansible code thoroughly:

```yaml
{current_code}
```

Validation level: {validation_level}
Current iteration: {current_iteration}
Auto-fix enabled: {enable_auto_fix}

Run ansible-lint validation and provide comprehensive analysis including:
- Syntax and structure validation
- Best practices compliance  
- Specific issues and recommendations
- Overall code quality assessment

If issues are found and auto-fix is enabled, provide specific guidance for fixes."""
        
        # Run validation through ReAct agent
        validation_messages = [{"role": "user", "content": validation_request}]
        result = validation_agent.invoke({"messages": validation_messages})
        
        # Extract validation output and tool results
        validation_output = ""
        tool_result_json = None
        
        if result.get("messages"):
            for message in result["messages"]:
                # Collect all content for analysis
                if hasattr(message, 'content'):
                    validation_output += str(message.content) + "\n"
                
                # Look for ToolMessage with JSON results
                if hasattr(message, '__class__') and 'ToolMessage' in str(message.__class__):
                    try:
                        tool_result_json = json.loads(message.content)
                        print(f"✅ Found tool result JSON in ToolMessage")
                        break
                    except (json.JSONDecodeError, AttributeError):
                        continue
        
        # Parse structured validation results from tool calls
        issues_found = []
        validation_summary = None
        raw_validation_data = {}
        
        # First try to use tool result JSON (most reliable)
        if tool_result_json:
            try:
                raw_validation_data = tool_result_json
                print(f"📊 Using tool result JSON with status: {tool_result_json.get('validation_status')}")
            except Exception as e:
                print(f"⚠️ Error using tool result JSON: {e}")
                tool_result_json = None
        
        # Fallback: Try to extract JSON from validation output
        if not tool_result_json:
            json_pattern = r'\{.*"validation_status".*\}'
            json_match = re.search(json_pattern, validation_output, re.DOTALL)
            if json_match:
                try:
                    validation_data = json.loads(json_match.group(0))
                    raw_validation_data = validation_data
                    print(f"📊 Extracted JSON from text with status: {validation_data.get('validation_status')}")
                except (json.JSONDecodeError, TypeError) as e:
                    print(f"⚠️ Could not parse validation JSON from text: {e}")
        
        # Process validation results if we have them
        if raw_validation_data:
            try:
                # Parse issues
                for issue_data in raw_validation_data.get("issues_found", []):
                    issues_found.append(ValidationIssue(**issue_data))
                
                # Parse summary
                summary_data = raw_validation_data.get("summary", {})
                if summary_data:
                    # Calculate quality score
                    issues_count = len(issues_found)
                    summary_data["code_quality_score"] = max(0, 100 - (issues_count * 10)) if issues_found else 100.0
                    validation_summary = ValidationSummary(**summary_data)
                
            except (json.JSONDecodeError, TypeError) as e:
                print(f"⚠️ Could not process validation results: {e}")
        
        # Get iteration history (handle both dict and ValidationState)
        iteration_history = state.get('iteration_history', []) if isinstance(state, dict) else state.iteration_history
        
        # Update iteration history
        iteration_record = {
            "iteration": current_iteration + 1,
            "issues_count": len(issues_found),
            "validation_status": validation_summary.validation_status if validation_summary else "unknown",
            "timestamp": datetime.now().isoformat(),
            "llm_output": validation_output[:500]  # Truncated for storage
        }
        
        new_history = iteration_history + [iteration_record]
        
        # Get max iterations (handle both dict and ValidationState)
        max_fix_iterations = state.get('max_fix_iterations', 3) if isinstance(state, dict) else state.max_fix_iterations
        
        # Determine if validation is complete
        validation_complete = (
            len(issues_found) == 0 or  # No issues found
            not enable_auto_fix or  # Auto-fix disabled
            current_iteration >= max_fix_iterations or  # Max iterations reached
            has_critical_errors(state)  # Unfixable critical errors
        )
        
        # Update state
        updated_state = {
            **state,
            "current_iteration": current_iteration + 1,
            "validation_results": raw_validation_data,
            "issues_found": issues_found,
            "validation_summary": validation_summary,
            "iteration_history": new_history,
            "llm_analysis": validation_output,
            "validation_complete": validation_complete
        }
        
        # Save successful validation if complete and no critical issues
        if validation_complete and len(issues_found) == 0 and store:
            save_successful_validation(store, user_id, updated_state)
        
        print(f" Validation complete: {len(issues_found)} issues found")
        return updated_state
        
    except Exception as e:
        error_msg = f"Validation failed: {str(e)}"
        print(f" {error_msg}")
        return {**state, "error_message": error_msg, "validation_complete": True}


def fix_issues(state: ValidationState, config: RunnableConfig = None, *, store: BaseStore = None) -> ValidationState:
    """Attempt to fix validation issues using LLM"""
    print("🔧 Attempting to fix validation issues...")
    
    # Handle both dict and ValidationState objects
    issues_found = state.get('issues_found', []) if isinstance(state, dict) else state.issues_found
    enable_auto_fix = state.get('enable_auto_fix', True) if isinstance(state, dict) else state.enable_auto_fix
    current_code = state.get('current_code', '') if isinstance(state, dict) else state.current_code
    
    if not issues_found or not enable_auto_fix:
        return {**state, "validation_complete": True}
    
    try:
        # Create issues summary for LLM
        issues_summary = "\n".join([
            f"- Line {getattr(issue, 'line_number', 'unknown')}: {getattr(issue, 'rule_id', 'unknown')} - {getattr(issue, 'message', str(issue))}"
            for issue in issues_found[:10]  # Top 10 issues
        ])
        
        # Ask LLM to fix the issues
        fix_response = code_fixer.invoke({
            "current_code": current_code,
            "issues_summary": issues_summary
        })
        
        fixed_code = fix_response.content.strip()
        
        # Extract YAML from response if wrapped in markdown
        if "```yaml" in fixed_code:
            yaml_start = fixed_code.find("```yaml") + 7
            yaml_end = fixed_code.find("```", yaml_start)
            if yaml_end > yaml_start:
                fixed_code = fixed_code[yaml_start:yaml_end].strip()
        elif "```" in fixed_code:
            yaml_start = fixed_code.find("```") + 3
            yaml_end = fixed_code.find("```", yaml_start)
            if yaml_end > yaml_start:
                fixed_code = fixed_code[yaml_start:yaml_end].strip()
        
        # Validate the fixed code is not empty or invalid
        if fixed_code and len(fixed_code.strip()) > 10:
            print(f"🔄 Code updated for next iteration")
            
            # Record the fix applied
            current_iteration = state.get('current_iteration', 0) if isinstance(state, dict) else state.current_iteration
            fixes_applied = state.get('fixes_applied', []) if isinstance(state, dict) else state.fixes_applied
            fix_description = f"Iteration {current_iteration}: Fixed {len(issues_found)} issues"
            fixes_applied = fixes_applied + [fix_description]
            
            return {
                **state,
                "current_code": fixed_code,
                "fixes_applied": fixes_applied
            }
        else:
            print("⚠️ LLM provided invalid fix, marking as stalled")
            return {**state, "progress_stalled": True, "validation_complete": True}
            
    except Exception as e:
        error_msg = f"Fix attempt failed: {str(e)}"
        print(f" {error_msg}")
        return {**state, "error_message": error_msg, "validation_complete": True}


def finalize_validation(state: ValidationState, config: RunnableConfig = None, *, store: BaseStore = None) -> ValidationState:
    """Finalize validation results and create summary message"""
    print("🎯 Finalizing validation results...")
    
    # Handle both dict and ValidationState objects
    messages = state.get("messages", [])
    validation_summary = state.get('validation_summary') if isinstance(state, dict) else state.validation_summary
    
    # Create comprehensive summary
    if validation_summary:
        # Get additional state values
        validation_level = state.get('validation_level', 'standard') if isinstance(state, dict) else state.validation_level
        current_iteration = state.get('current_iteration', 0) if isinstance(state, dict) else state.current_iteration
        enable_auto_fix = state.get('enable_auto_fix', True) if isinstance(state, dict) else state.enable_auto_fix
        fixes_applied = state.get('fixes_applied', []) if isinstance(state, dict) else state.fixes_applied
        
        # Calculate quality score
        if hasattr(validation_summary, 'code_quality_score') and validation_summary.code_quality_score:
            quality_score = validation_summary.code_quality_score
        else:
            # Simple quality score calculation
            total_issues = getattr(validation_summary, 'total_issues', 0) if validation_summary else 0
            quality_score = max(0, 100 - (total_issues * 10))  # Deduct 10 points per issue
        
        summary_text = f"""🎯 **Ansible Validation Complete**

**Overall Status:** {getattr(validation_summary, 'validation_status', 'unknown').upper()}
**Quality Score:** {quality_score:.1f}/100

**Issues Summary:**
- Total Issues: {getattr(validation_summary, 'total_issues', 0)}
- Errors: {getattr(validation_summary, 'errors', 0)}
- Warnings: {getattr(validation_summary, 'warnings', 0)}
- Info: {getattr(validation_summary, 'info', 0)}

**Process Details:**
- Validation Level: {validation_level}
- Iterations: {current_iteration}
- Auto-fix: {'Enabled' if enable_auto_fix else 'Disabled'}
- Fixes Applied: {len(fixes_applied)}

**Final Code Status:**
{f" Code is lint-clean!" if getattr(validation_summary, 'total_issues', 0) == 0 else f"⚠️ {getattr(validation_summary, 'total_issues', 0)} issues remaining"}"""

        if fixes_applied:
            summary_text += f"\n\n**Fixes Applied:**\n" + "\n".join(f"- {fix}" for fix in fixes_applied)
        
        failed_rules = getattr(validation_summary, 'failed_rules', [])
        if failed_rules:
            summary_text += f"\n\n**Failed Rules:** {', '.join(failed_rules[:5])}"
        
    else:
        summary_text = " Validation failed - no results available"
    
    # Add final code if requested
    current_code = state.get('current_code', '') if isinstance(state, dict) else state.current_code
    original_code = state.get('original_code', '') if isinstance(state, dict) else state.original_code
    
    if current_code != original_code and current_code:
        summary_text += f"\n\n**Final Code:**\n```yaml\n{current_code}\n```"
    
    final_message = AIMessage(content=summary_text)
    
    return {
        **state,
        "validation_complete": True,
        "messages": messages + [final_message]
    }


# ============================================================================
# ROUTING FUNCTIONS
# ============================================================================

def should_continue_validation(state: ValidationState) -> str:
    """Determine if validation should continue or end"""
    # Handle both dict and ValidationState objects
    validation_complete = state.get('validation_complete', False) if isinstance(state, dict) else state.validation_complete
    
    if validation_complete:
        return "finalize"
    elif should_continue_fixing(state):
        return "fix"
    else:
        return "finalize"


def needs_fixing(state: ValidationState) -> str:
    """Determine if issues need fixing"""
    # Handle both dict and ValidationState objects
    enable_auto_fix = state.get('enable_auto_fix', True) if isinstance(state, dict) else state.enable_auto_fix
    issues_found = state.get('issues_found', []) if isinstance(state, dict) else state.issues_found
    current_iteration = state.get('current_iteration', 0) if isinstance(state, dict) else state.current_iteration
    max_fix_iterations = state.get('max_fix_iterations', 3) if isinstance(state, dict) else state.max_fix_iterations
    progress_stalled = state.get('progress_stalled', False) if isinstance(state, dict) else state.progress_stalled
    
    if (enable_auto_fix and 
        issues_found and 
        current_iteration < max_fix_iterations and
        not progress_stalled):
        return "fix"
    else:
        return "finalize"
