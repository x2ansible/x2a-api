"""
Code Generation Agent State Definitions

State management for the AlphaCodium-based code generation workflow.
"""

from langgraph.graph import MessagesState
from langchain_core.runnables import RunnableConfig
from typing import Optional, Any as BaseStore


class CodeGenState(MessagesState):
    """
    State for Infrastructure-to-Ansible code generation workflow.
    Extends MessagesState for LangGraph Studio chat compatibility.
    Supports multiple source platforms (Chef, Puppet, Terraform, etc.)
    
    Additional attributes beyond messages:
        source_code: Input infrastructure code to convert
        source_platform: Detected platform (chef, puppet, terraform, etc.)
        ansible_code: Generated Ansible code
        best_practices: Retrieved best practices from Context Agent
        infrastructure_specification: Formal specification from Infrastructure Analysis
        error: Validation error messages
        iterations: Number of generation attempts
        max_iterations: Maximum allowed attempts
        infrastructure_analysis: Analysis of infrastructure code patterns
        validation_results: Results from code validation
        use_reflection: Whether to use reflection on errors (AlphaCodium pattern)
        reflections: LLM-generated reflections on errors
    """
    
    # Core workflow data
    source_code: str = ""  # Platform-agnostic source code
    source_platform: str = "unknown"  # Detected platform (chef, puppet, terraform, etc.)
    ansible_code: str = ""
    best_practices: str = ""
    infrastructure_specification: str = ""  # Enhanced with formal specifications
    
    # Error handling and iteration
    error: str = ""
    iterations: int = 0
    max_iterations: int = 3
    
    # Analysis and validation
    infrastructure_analysis: str = ""  # Platform-agnostic analysis
    validation_results: dict = {}
    
    # AlphaCodium reflection pattern
    use_reflection: bool = True
    reflections: str = ""


def get_user_id_from_config(config: RunnableConfig) -> str:
    """Extract user ID from config, with fallback to anonymous"""
    if not config:
        return "anonymous"
    return config.get("configurable", {}).get("user_id", "anonymous")


def should_reflect(state: CodeGenState) -> bool:
    """Determine if reflection should be used based on state"""
    # Handle both dict and CodeGenState objects
    use_reflection = state.get('use_reflection', True) if isinstance(state, dict) else state.use_reflection
    error = state.get('error', '') if isinstance(state, dict) else state.error
    iterations = state.get('iterations', 0) if isinstance(state, dict) else state.iterations
    max_iterations = state.get('max_iterations', 3) if isinstance(state, dict) else state.max_iterations
    
    return (
        use_reflection and 
        error and 
        iterations > 0 and 
        iterations < max_iterations
    )


def should_continue_iteration(state: CodeGenState) -> bool:
    """Determine if iteration should continue"""
    # Handle both dict and CodeGenState objects
    error = state.get('error', '') if isinstance(state, dict) else state.error
    iterations = state.get('iterations', 0) if isinstance(state, dict) else state.iterations
    max_iterations = state.get('max_iterations', 3) if isinstance(state, dict) else state.max_iterations
    
    return (
        error and 
        iterations < max_iterations
    )


def log_generation_attempt(store: BaseStore, user_id: str, state: CodeGenState) -> None:
    """Log code generation attempt for learning (if store available)"""
    if not store:
        return
        
    try:
        import uuid
        from datetime import datetime
        
        generation_namespace = (user_id, "code_generation_attempts")
        attempt_log = {
            "source_platform": state.source_platform,
            "iteration": state.iterations,
            "has_error": bool(state.error),
            "used_reflection": bool(state.reflections),
            "timestamp": datetime.now().isoformat(),
            "source_code_length": len(state.source_code),
            "ansible_code_length": len(state.ansible_code)
        }
        store.put(generation_namespace, str(uuid.uuid4()), attempt_log)
    except Exception as e:
        print(f"⚠️ Generation logging error: {e}")


def save_successful_generation(store: BaseStore, user_id: str, state: CodeGenState) -> None:
    """Save successful generation for learning (if store available)"""
    if not store:
        return
        
    try:
        import uuid
        import hashlib
        from datetime import datetime
        
        # Save successful generation pattern
        success_namespace = (user_id, "successful_generations")
        success_data = {
            "source_platform": state.source_platform,
            "total_iterations": state.iterations,
            "used_reflection": bool(state.reflections),
            "source_code_hash": hashlib.sha256(state.source_code.encode()).hexdigest()[:12],
            "ansible_code_length": len(state.ansible_code),
            "timestamp": datetime.now().isoformat(),
            "best_practices_used": bool(state.best_practices),
            "specification_used": bool(state.infrastructure_specification)
        }
        store.put(success_namespace, str(uuid.uuid4()), success_data)
        
        # Update user generation preferences
        user_namespace = (user_id, "generation_preferences")
        prefs = {
            "preferred_platform": state.source_platform,
            "uses_reflection": state.use_reflection,
            "total_generations": getattr(store.search(user_namespace), 'total_generations', 0) + 1,
            "last_activity": datetime.now().isoformat()
        }
        store.put(user_namespace, "profile", prefs)
        
    except Exception as e:
        print(f"⚠️ Success save error: {e}")
