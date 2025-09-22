"""
Code Generation Agent - Clean LangGraph Definition

Production-grade Code Generation Agent following AlphaCodium pattern.
Pure graph definition with components split into logical modules.
"""

from langgraph.graph import StateGraph, START, END
from langchain_core.runnables import RunnableConfig
from typing import Any

from code_gen.state import CodeGenState
from code_gen.nodes import (
    extract_source_code_from_messages,
    analyze_infrastructure_code,
    get_best_practices,
    generate_ansible_code,
    validate_code,
    reflect_on_errors,
    should_reflect_on_errors,
    should_continue_generation
)


# ============================================================================
# GRAPH DEFINITION
# ============================================================================

def create_code_generation_graph():
    """Create the Code Generation Agent graph with AlphaCodium structure"""
    
    # Create the state graph
    workflow = StateGraph(CodeGenState)
    
    # Add all nodes
    workflow.add_node("extract_source_code", extract_source_code_from_messages)
    workflow.add_node("analyze_infrastructure", analyze_infrastructure_code)
    workflow.add_node("get_best_practices", get_best_practices)
    workflow.add_node("generate_ansible", generate_ansible_code)
    workflow.add_node("validate_code", validate_code)
    workflow.add_node("reflect", reflect_on_errors)
    
    # Define the AlphaCodium workflow edges
    workflow.add_edge(START, "extract_source_code")
    workflow.add_edge("extract_source_code", "analyze_infrastructure")
    workflow.add_edge("analyze_infrastructure", "get_best_practices")
    workflow.add_edge("get_best_practices", "generate_ansible")
    workflow.add_edge("generate_ansible", "validate_code")
    
    # Conditional routing based on validation results (AlphaCodium pattern)
    workflow.add_conditional_edges(
        "validate_code",
        should_reflect_on_errors,
        {
            "reflect": "reflect",      # Use reflection on errors
            "generate": "generate_ansible",  # Direct retry
            "end": END                 # Validation passed or max iterations
        }
    )
    
    # After reflection, go back to generation
    workflow.add_edge("reflect", "generate_ansible")
    
    # Compile the graph
    # LangGraph API handles persistence automatically when deployed
    return workflow.compile()


# Create the application
app = create_code_generation_graph()


if __name__ == "__main__":
    print("🚀 Code Generation Agent Ready - Clean Structure Implementation")
    print("AlphaCodium pattern with organized codebase and agent-to-agent communication")
