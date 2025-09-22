"""
Validation Agent - Clean LangGraph Definition

Production-grade Ansible validation agent with ReAct pattern and iterative fixing.
Pure graph definition with components split into logical modules.
"""

from langgraph.graph import StateGraph, START, END
from langgraph.store.base import BaseStore
from langchain_core.runnables import RunnableConfig

from validation.state import ValidationState
from validation.nodes import (
    extract_ansible_code,
    validate_and_analyze,
    fix_issues,
    finalize_validation,
    should_continue_validation,
    needs_fixing
)


# ============================================================================
# GRAPH DEFINITION
# ============================================================================

def create_validation_graph():
    """Create the Validation Agent graph with iterative fixing workflow"""
    
    # Create the state graph
    workflow = StateGraph(ValidationState)
    
    # Add all nodes
    workflow.add_node("extract_code", extract_ansible_code)
    workflow.add_node("validate", validate_and_analyze)
    workflow.add_node("fix", fix_issues)
    workflow.add_node("finalize", finalize_validation)
    
    # Define the workflow edges
    workflow.add_edge(START, "extract_code")
    workflow.add_edge("extract_code", "validate")
    
    # Conditional routing based on validation results
    workflow.add_conditional_edges(
        "validate",
        needs_fixing,
        {
            "fix": "fix",         # Issues found and auto-fix enabled
            "finalize": "finalize"  # No issues, auto-fix disabled, or max iterations
        }
    )
    
    # After fixing, go back to validation
    workflow.add_edge("fix", "validate")
    
    # End after finalization
    workflow.add_edge("finalize", END)
    
    # Compile the graph
    # LangGraph API handles persistence automatically when deployed
    return workflow.compile()


# Create the application
app = create_validation_graph()


if __name__ == "__main__":
    print("🚀 Validation Agent Ready - Clean Structure Implementation")
    print("ReAct pattern with iterative fixing and organized codebase")
