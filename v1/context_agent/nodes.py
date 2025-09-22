"""
Context Agent Workflow Nodes

Hybrid Agentic RAG implementation with clean configuration-driven architecture.
- Workflow orchestration follows LangGraph tutorial patterns
- Intelligent reasoning handled by specialized ReAct agents from config
- All prompts externalized to v1/config.yaml for maintainability
"""

from typing import Literal, Any
from langgraph.graph import MessagesState
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import AIMessage

# Make BaseStore import optional for compatibility across LangGraph versions
try:
    from langgraph.store.base import BaseStore
except ImportError:
    # Fallback for older LangGraph versions
    BaseStore = Any

from context_agent.state import get_user_id_from_config, log_query_pattern, save_successful_retrieval
from context_agent.tools import get_retriever_tool
from context_agent.utils import get_llm, get_prompt
from context_agent.agents import create_retrieval_react_agent, create_grading_react_agent


# ============================================================================
# WORKFLOW NODES - Configuration-Driven Implementation
# ============================================================================

def generate_query_or_respond(state: MessagesState, config: RunnableConfig = None, *, store: BaseStore = None) -> MessagesState:
    """
    Generate query or respond using configured ReAct retrieval agent.
    
    Uses intelligent retrieval strategy selection based on prompts from config.yaml.
    Handles memory logging and graceful fallback if agent fails.
    """
    print("🤖 Generating query or response with ReAct agent...")
    
    # Handle memory logging before processing
    if store and config:
        try:
            user_id = get_user_id_from_config(config)
            # Ensure user_id is not empty to avoid namespace error
            if user_id and user_id.strip():
                human_msg = state["messages"][-1]
                log_query_pattern(store, user_id, human_msg.content)
        except Exception as e:
            print(f"⚠️ Memory error (continuing): {e}")
    
    # Get the user's question
    user_question = state["messages"][-1].content
    
    # Create ReAct agent with embedded system prompt
    retrieval_agent = create_retrieval_react_agent()
    
    # Use configured prompt template for retrieval request
    retrieval_request = get_prompt('retrieval_request').format(user_question=user_question)
    
    retrieval_messages = [{"role": "user", "content": retrieval_request}]
    result = retrieval_agent.invoke({"messages": retrieval_messages})
    
    # Extract the final response from ReAct agent
    if result.get("messages"):
        final_message = result["messages"][-1]
        response_content = final_message.content if hasattr(final_message, 'content') else str(final_message)
        
        # Create AI message with retrieved content
        ai_response = AIMessage(content=response_content)
        return {"messages": [ai_response]}
    
    # Fallback to simple LLM response if agent fails
    llm = get_llm()
    retriever_tool = get_retriever_tool()
    response = llm.bind_tools([retriever_tool]).invoke(state["messages"])
    return {"messages": [response]}


def grade_documents(state: MessagesState, config: RunnableConfig = None, *, store: BaseStore = None) -> Literal["generate_answer", "rewrite_question"]:
    """
    Determine document relevance using configured ReAct grading agent.
    
    Routes workflow based on intelligent document evaluation:
    - 'generate_answer' if documents are relevant
    - 'rewrite_question' if documents need better retrieval
    """
    print("📊 Grading documents with ReAct agent...")
    
    question = state["messages"][0].content
    context = state["messages"][-1].content
    
    # Create ReAct agent with config-based prompts
    grading_agent = create_grading_react_agent()
    
    # Use configured prompt template for grading request
    grading_request = get_prompt('grading_request').format(question=question, context=context)

    grading_messages = [{"role": "user", "content": grading_request}]
    result = grading_agent.invoke({"messages": grading_messages})
    
    # Extract decision from ReAct agent output
    agent_output = ""
    if result.get("messages"):
        for message in result["messages"]:
            if hasattr(message, 'content'):
                agent_output += message.content
    
    # Look for decision in agent output (based on grading_system prompt)
    if "DECISION: relevant" in agent_output:
        print("✅ Documents are relevant")
        decision = "generate_answer"
    else:
        print("🔄 Documents not relevant - rewriting question")
        decision = "rewrite_question"
    
    # Return state update with grading decision stored
    return {"messages": [{"role": "assistant", "content": f"Grading decision: {decision}"}]}


def route_after_grading(state: MessagesState) -> Literal["generate_answer", "rewrite_question"]:
    """
    Route based on document grading decision.
    
    Args:
        state: Current conversation state containing grading decision
        
    Returns:
        Next node to execute: "generate_answer" or "rewrite_question"
    """
    # Look for the grading decision in the latest message
    latest_message = state["messages"][-1]
    
    # Handle both dict and object message formats
    if hasattr(latest_message, 'content'):
        content = latest_message.content
    else:
        content = latest_message.get('content', '')
    
    if "generate_answer" in content:
        return "generate_answer"
    else:
        return "rewrite_question"


def rewrite_question(state: MessagesState, config: RunnableConfig = None, *, store: BaseStore = None) -> MessagesState:
    """
    Rewrite user question for better retrieval using configured prompt.
    
    Transforms original question to be more specific and searchable for
    Ansible automation patterns based on rewrite template from config.yaml.
    """
    print("✏️ Rewriting question...")
    
    messages = state["messages"]
    question = messages[0].content
    
    # Use configured prompt template for question rewriting
    prompt = get_prompt('rewrite').format(question=question)
    llm = get_llm()
    response = llm.invoke([{"role": "user", "content": prompt}])
    return {"messages": [{"role": "user", "content": response.content}]}


def generate_answer(state: MessagesState, config: RunnableConfig = None, *, store: BaseStore = None) -> MessagesState:
    """
    Generate final answer using retrieved context and configured prompt.
    
    Creates actionable Ansible automation guidance based on the generate
    template from config.yaml. Saves successful patterns to memory for learning.
    """
    print("💬 Generating final answer...")
    
    question = state["messages"][0].content
    context = state["messages"][-1].content
    
    # Use configured prompt template for answer generation
    prompt = get_prompt('generate').format(question=question, context=context)
    llm = get_llm()
    response = llm.invoke([{"role": "user", "content": prompt}])
    
    # Save successful retrieval pattern to memory for learning
    if store and config:
        try:
            user_id = get_user_id_from_config(config)
            # Ensure user_id is not empty to avoid namespace error
            if user_id and user_id.strip():
                save_successful_retrieval(store, user_id, question, response.content)
                print(f"💾 Saved successful retrieval to memory for user {user_id}")
        except Exception as e:
            print(f"⚠️ Memory save error (continuing): {e}")
    
    return {"messages": [response]}
