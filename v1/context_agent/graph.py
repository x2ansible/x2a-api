"""
Context Agent - Configuration-Driven Agentic RAG Implementation

Clean LangGraph workflow with intelligent ReAct agents for document retrieval and grading.
- Predictable workflow orchestration
- Intelligent reasoning via specialized ReAct agents
- Full configuration externalization for maintainability
- Optimized routing based on document relevance assessment
"""

from langgraph.graph import StateGraph, START, END, MessagesState

from context_agent.nodes import (
    generate_query_or_respond,
    grade_documents,
    route_after_grading,
    rewrite_question,
    generate_answer
)


# ============================================================================
# GRAPH DEFINITION - ReAct Agent Architecture
# ============================================================================

def create_context_agent_graph():
    """
    Create Context Agent graph with clean ReAct agent architecture.
    
    Workflow:
    1. generate_query_or_respond: Uses ReAct agent for intelligent retrieval
    2. grade_documents: Uses ReAct agent for document relevance assessment  
    3. Route to generate_answer (relevant) or rewrite_question (not relevant)
    4. Loop back for improved retrieval if needed
    
    Returns:
        Compiled LangGraph workflow optimized for context retrieval tasks
    """
    
    # Create the state graph using MessagesState for LangGraph Studio compatibility
    workflow = StateGraph(MessagesState)
    
    # Add workflow nodes - each handles specific aspect of context retrieval
    workflow.add_node("generate_query_or_respond", generate_query_or_respond)
    workflow.add_node("grade_documents", grade_documents)
    workflow.add_node("rewrite_question", rewrite_question)
    workflow.add_node("generate_answer", generate_answer)
    
    # Define workflow edges - clean linear flow with intelligent routing
    workflow.add_edge(START, "generate_query_or_respond")
    
    # After retrieval, always grade documents for relevance
    workflow.add_edge("generate_query_or_respond", "grade_documents")
    
    # Route based on document relevance assessment (uses separate routing function)
    workflow.add_conditional_edges(
        "grade_documents",
        route_after_grading,  # Separate routing function reads decision from state
        {
            "generate_answer": "generate_answer",      # Documents are relevant
            "rewrite_question": "rewrite_question"     # Documents need better retrieval
        }
    )
    
    # Terminal states and loops
    workflow.add_edge("generate_answer", END)                          # End after successful answer
    workflow.add_edge("rewrite_question", "generate_query_or_respond") # Loop back for better retrieval
    
    # Compile the graph with LangGraph Studio support
    return workflow.compile()


# ============================================================================
# APPLICATION INSTANCE
# ============================================================================

# Create the compiled application instance
app = create_context_agent_graph()


# ============================================================================
# DEVELOPMENT & DEBUG
# ============================================================================

if __name__ == "__main__":
    print("🚀 Context Agent Ready - Configuration-Driven Agentic RAG")
    print("📋 Clean LangGraph workflow with intelligent ReAct agents")
    print("⚙️ All prompts externalized to v1/config.yaml")
    print("🔍 Optimized for Ansible automation pattern retrieval")
    
    # Display graph structure for debugging
    try:
        from langgraph.graph.graph import CompiledGraph
        if isinstance(app, CompiledGraph):
            print(f"\n📊 Graph Structure:")
            print(f"   Nodes: {len(app.get_graph().nodes)} total")
            print(f"   Workflow: START → query/respond → grade → answer/rewrite → END")
            print(f"   ReAct Agents: 2 specialized (retrieval + grading)")
    except Exception as e:
        print(f"⚠️ Graph introspection unavailable: {e}")
    
    print("\n✨ Ready for LangGraph Studio and production deployment!")