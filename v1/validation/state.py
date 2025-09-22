"""
Validation Agent State Definitions

State management for the Ansible validation workflow with iterative fixing.
"""

from langgraph.graph import MessagesState
from langgraph.store.base import BaseStore
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional


class ValidationIssue(BaseModel):
    """Individual validation issue found by ansible-lint"""
    
    rule_id: str = Field(description="Ansible-lint rule ID (e.g., 'yaml[line-too-long]')")
    severity: str = Field(description="Issue severity: 'error', 'warning', 'info'")
    message: str = Field(description="Human-readable issue description")
    filename: str = Field(description="File where issue was found")
    line_number: Optional[int] = Field(default=None, description="Line number of the issue")
    column_number: Optional[int] = Field(default=None, description="Column number of the issue")
    rule_description: Optional[str] = Field(default=None, description="Detailed rule explanation")
    suggested_fix: Optional[str] = Field(default=None, description="LLM-generated fix suggestion")


class ValidationSummary(BaseModel):
    """High-level validation results summary"""
    
    total_issues: int = Field(default=0, description="Total number of issues found")
    errors: int = Field(default=0, description="Number of error-level issues") 
    warnings: int = Field(default=0, description="Number of warning-level issues")
    info: int = Field(default=0, description="Number of info-level issues")
    validation_status: str = Field(default="unknown", description="Overall status: 'valid', 'invalid', 'warnings'")
    passed_rules: List[str] = Field(default_factory=list, description="Ansible-lint rules that passed")
    failed_rules: List[str] = Field(default_factory=list, description="Ansible-lint rules that failed")
    code_quality_score: Optional[float] = Field(default=None, description="Quality score 0-100")


class ValidationState(MessagesState):
    """
    State for Ansible Validation workflow with iterative fixing.
    Extends MessagesState for LangGraph Studio chat compatibility.
    """
    
    # Input data
    ansible_code: str = ""  # Original code provided by user
    validation_level: str = "standard"  # "basic", "standard", "strict"
    
    # Iterative fixing state
    current_code: str = ""  # Code being iteratively improved
    original_code: str = ""  # Always preserve original
    max_fix_iterations: int = 3  # Maximum fix attempts
    current_iteration: int = 0  # Current iteration number
    enable_auto_fix: bool = True  # Whether to enable iterative fixing
    
    # Validation results (current iteration)
    validation_results: Dict[str, Any] = {}  # Raw ansible-lint output
    issues_found: List[ValidationIssue] = []
    validation_summary: Optional[ValidationSummary] = None
    
    # Iterative fixing tracking
    iteration_history: List[Dict[str, Any]] = []  # History of each iteration
    fixes_applied: List[str] = []  # List of fixes applied
    progress_stalled: bool = False  # Whether progress has stalled
    
    # LLM analysis and suggestions
    llm_analysis: str = ""
    suggested_fixes: List[str] = []
    
    # Process control
    validation_complete: bool = False


def get_user_id_from_config(config: RunnableConfig) -> str:
    """Extract user ID from config, with fallback to anonymous"""
    if not config:
        return "anonymous"
    return config.get("configurable", {}).get("user_id", "anonymous")


def should_continue_fixing(state: ValidationState) -> bool:
    """Determine if iterative fixing should continue"""
    return (
        state.enable_auto_fix and
        state.current_iteration < state.max_fix_iterations and
        state.issues_found and
        not state.progress_stalled and
        not state.validation_complete
    )


def has_critical_errors(state: ValidationState) -> bool:
    """Check if there are critical errors that prevent continuing"""
    if not state.issues_found:
        return False
    
    critical_errors = [issue for issue in state.issues_found if issue.severity == "error"]
    return len(critical_errors) > 0


def calculate_quality_score(state: ValidationState) -> float:
    """Calculate code quality score based on issues"""
    if not state.validation_summary:
        return 0.0
    
    total_issues = state.validation_summary.total_issues
    errors = state.validation_summary.errors
    warnings = state.validation_summary.warnings
    
    # Base score starts at 100
    score = 100.0
    
    # Deduct points for issues
    score -= errors * 20  # 20 points per error
    score -= warnings * 5  # 5 points per warning
    score -= (total_issues - errors - warnings) * 1  # 1 point per info issue
    
    # Ensure score doesn't go below 0
    return max(0.0, score)


def log_validation_attempt(store: BaseStore, user_id: str, state: ValidationState) -> None:
    """Log validation attempt for learning (if store available)"""
    if not store:
        return
        
    try:
        import uuid
        from datetime import datetime
        
        validation_namespace = (user_id, "validation_attempts")
        attempt_log = {
            "iteration": state.current_iteration,
            "total_issues": len(state.issues_found),
            "errors": len([i for i in state.issues_found if i.severity == "error"]),
            "warnings": len([i for i in state.issues_found if i.severity == "warning"]),
            "code_length": len(state.current_code),
            "validation_level": state.validation_level,
            "timestamp": datetime.now().isoformat(),
            "auto_fix_enabled": state.enable_auto_fix
        }
        store.put(validation_namespace, str(uuid.uuid4()), attempt_log)
    except Exception as e:
        print(f"⚠️ Validation logging error: {e}")


def save_successful_validation(store: BaseStore, user_id: str, state: ValidationState) -> None:
    """Save successful validation for learning (if store available)"""
    if not store:
        return
        
    try:
        import uuid
        import hashlib
        from datetime import datetime
        
        # Save successful validation pattern
        success_namespace = (user_id, "successful_validations")
        success_data = {
            "total_iterations": state.current_iteration,
            "final_quality_score": calculate_quality_score(state),
            "fixes_applied_count": len(state.fixes_applied),
            "original_code_hash": hashlib.sha256(state.original_code.encode()).hexdigest()[:12],
            "final_code_length": len(state.current_code),
            "validation_level": state.validation_level,
            "timestamp": datetime.now().isoformat(),
            "auto_fix_used": state.enable_auto_fix and state.current_iteration > 0
        }
        store.put(success_namespace, str(uuid.uuid4()), success_data)
        
        # Update user validation preferences
        user_namespace = (user_id, "validation_preferences")
        prefs = {
            "preferred_validation_level": state.validation_level,
            "uses_auto_fix": state.enable_auto_fix,
            "total_validations": getattr(store.search(user_namespace), 'total_validations', 0) + 1,
            "last_activity": datetime.now().isoformat()
        }
        store.put(user_namespace, "profile", prefs)
        
    except Exception as e:
        print(f"⚠️ Success save error: {e}")