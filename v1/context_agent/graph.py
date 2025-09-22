"""
Context Agent - Hybrid Agentic RAG Implementation

Following the LangGraph Agentic RAG tutorial pattern with strategic ReAct agents.
Best of both worlds: predictable workflow + intelligent reasoning where it adds value.
"""

from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.store.base import BaseStore
from langchain_core.runnables import RunnableConfig

from context_agent.nodes import (
    generate_query_or_respond,
    grade_documents,
    rewrite_question,
    generate_answer
)
from context_agent.tools import get_retriever_tool


# ============================================================================
# GRAPH DEFINITION (Tutorial Pattern)
# ============================================================================

def create_context_agent_graph():
    """Create the Context Agent graph following Agentic RAG tutorial pattern"""
    
    # Get the retriever tool for the ToolNode
    retriever_tool = get_retriever_tool()
    
    # Create the state graph (MessagesState as per tutorial)
    workflow = StateGraph(MessagesState)
    
    # Define the nodes we will cycle between (Tutorial Pattern)
    workflow.add_node("generate_query_or_respond", generate_query_or_respond)
    workflow.add_node("retrieve", ToolNode([retriever_tool]))  # ToolNode for retrieval
    workflow.add_node("rewrite_question", rewrite_question)
    workflow.add_node("generate_answer", generate_answer)
    
    # Start with generate_query_or_respond (Tutorial Pattern)
    workflow.add_edge(START, "generate_query_or_respond")
    
    # Decide whether to retrieve (Tutorial Pattern)
    workflow.add_conditional_edges(
        "generate_query_or_respond",
        # Assess LLM decision (call `retriever_tool` or respond to user)
        tools_condition,
        {
            # Translate the condition outputs to nodes in our graph
            "tools": "retrieve",
            END: END,
        },
    )
    
    # After retrieval, grade documents (Tutorial Pattern + ReAct Enhancement)
    workflow.add_conditional_edges(
        "retrieve",
        # Assess document relevance using ReAct agent
        grade_documents,
        {
            "generate_answer": "generate_answer",
            "rewrite_question": "rewrite_question"
        }
    )
    
    # End after generating answer
    workflow.add_edge("generate_answer", END)
    
    # After rewriting question, go back to generate_query_or_respond
    workflow.add_edge("rewrite_question", "generate_query_or_respond")
    
    # Compile the graph
    # LangGraph API handles persistence automatically when deployed
    return workflow.compile()


# Create the application
app = create_context_agent_graph()


if __name__ == "__main__":
    print("🚀 Context Agent Ready - Hybrid Agentic RAG Implementation")
    print("Tutorial pattern workflow with strategic ReAct agents for intelligent reasoning")