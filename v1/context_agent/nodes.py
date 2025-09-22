"""
Context Agent Workflow Nodes

Hybrid approach: Tutorial pattern workflow with strategic ReAct agents.
Following the Agentic RAG tutorial but using ReAct where reasoning adds value.
"""

from typing import Literal
from langgraph.graph import MessagesState
from langgraph.store.base import BaseStore
from langgraph.prebuilt import create_react_agent
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from context_agent.state import get_user_id_from_config, log_query_pattern, save_successful_retrieval
from context_agent.tools import get_retriever_tool, neo4j_vector_search, neo4j_graph_query
from context_agent.utils import get_llm, get_prompt


# ============================================================================
# GLOBAL COMPONENTS
# ============================================================================

llm = get_llm()
retriever_tool = get_retriever_tool()


# ============================================================================
# PROMPTS (Loaded from Configuration)
# ============================================================================

# Note: Prompts are now loaded from config.yaml via get_prompt() function


# ============================================================================
# DOCUMENT GRADING TOOLS FOR REACT AGENT
# ============================================================================

class GradeDocuments(BaseModel):
    """Grade documents using a binary score for relevance check."""
    binary_score: str = Field(
        description="Relevance score: 'yes' if relevant, or 'no' if not relevant"
    )


@tool
def grade_document_relevance(question: str, context: str) -> str:
    """Grade the relevance of retrieved context to the user question."""
    
    prompt = get_prompt('grade').format(question=question, context=context)
    response = llm.with_structured_output(GradeDocuments).invoke(
        [{"role": "user", "content": prompt}]
    )
    
    score = response.binary_score
    print(f"📈 Document relevance score: {score}")
    
    return f"Document relevance: {score}. {'Relevant content found.' if score == 'yes' else 'Content not relevant to question.'}"


@tool  
def analyze_question_intent(question: str) -> str:
    """Analyze the user's question to understand what they're really asking about."""
    
    analysis_prompt = f"""Analyze this Ansible automation question to understand the intent:

Question: {question}

What is the user really asking about? Consider:
- Are they asking about best practices?
- Do they need specific implementation guidance?
- Are they looking for troubleshooting help?
- Do they want to understand concepts?

Provide a brief analysis of the question intent."""

    response = llm.invoke([{"role": "user", "content": analysis_prompt}])
    return f"Question analysis: {response.content}"


# ============================================================================
# REACT AGENT FOR RETRIEVAL DECISIONS
# ============================================================================

def create_retrieval_react_agent():
    """Create ReAct agent for intelligent retrieval strategy selection"""
    tools = [neo4j_vector_search, neo4j_graph_query]
    
    retrieval_system_prompt = get_prompt('retrieval_system')

    return create_react_agent(llm, tools, prompt=retrieval_system_prompt)


# ============================================================================
# REACT AGENT FOR DOCUMENT GRADING
# ============================================================================

def create_grading_react_agent():
    """Create ReAct agent for intelligent document grading with reasoning"""
    tools = [grade_document_relevance, analyze_question_intent]
    
    grading_system_prompt = get_prompt('grading_system')

    return create_react_agent(llm, tools, prompt=grading_system_prompt)


# ============================================================================
# WORKFLOW NODES (Tutorial Pattern)
# ============================================================================

def generate_query_or_respond(state: MessagesState, config: RunnableConfig = None, *, store: BaseStore = None) -> MessagesState:
    """Generate query or respond using ReAct agent with Neo4j tools"""
    print("🤖 Generating query or response with ReAct agent...")
    
    # Handle memory logging before processing
    if store and config:
        try:
            user_id = get_user_id_from_config(config)
            human_msg = state["messages"][-1]
            log_query_pattern(store, user_id, human_msg.content)
        except Exception as e:
            print(f"⚠️ Memory error (continuing): {e}")
    
    # Get the user's question
    user_question = state["messages"][-1].content
    
    # Use ReAct agent for intelligent retrieval
    retrieval_agent = create_retrieval_react_agent()
    
    retrieval_request = f"""Please retrieve relevant Ansible automation patterns for this question:

Question: {user_question}

Analyze the question and use the most appropriate retrieval tool(s) to find relevant information."""
    
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
    response = llm.bind_tools([retriever_tool]).invoke(state["messages"])
    return {"messages": [response]}


def grade_documents(state: MessagesState, config: RunnableConfig = None, *, store: BaseStore = None) -> Literal["generate_answer", "rewrite_question"]:
    """Determine whether the retrieved documents are relevant using ReAct agent"""
    print("📊 Grading documents with ReAct agent...")
    
    question = state["messages"][0].content
    context = state["messages"][-1].content
    
    # Use ReAct agent for intelligent grading
    grading_agent = create_grading_react_agent()
    
    grading_request = f"""Please analyze and grade these retrieved documents:

Question: {question}

Retrieved Context: {context}

Determine if the retrieved content is relevant to answering the user's question."""

    grading_messages = [{"role": "user", "content": grading_request}]
    result = grading_agent.invoke({"messages": grading_messages})
    
    # Extract decision from ReAct agent output
    agent_output = ""
    if result.get("messages"):
        for message in result["messages"]:
            if hasattr(message, 'content'):
                agent_output += message.content
    
    # Look for decision in agent output
    if "DECISION: relevant" in agent_output:
        print(" Documents are relevant")
        return "generate_answer"
    else:
        print(" Documents not relevant - rewriting question")
        return "rewrite_question"


def rewrite_question(state: MessagesState, config: RunnableConfig = None, *, store: BaseStore = None) -> MessagesState:
    """Rewrite the original user question (Tutorial Pattern)"""
    print("✏️ Rewriting question...")
    
    messages = state["messages"]
    question = messages[0].content
    prompt = get_prompt('rewrite').format(question=question)
    response = llm.invoke([{"role": "user", "content": prompt}])
    return {"messages": [{"role": "user", "content": response.content}]}


def generate_answer(state: MessagesState, config: RunnableConfig = None, *, store: BaseStore = None) -> MessagesState:
    """Generate an answer using retrieved context (Tutorial Pattern)"""
    print("💬 Generating final answer...")
    
    question = state["messages"][0].content
    context = state["messages"][-1].content
    prompt = get_prompt('generate').format(question=question, context=context)
    response = llm.invoke([{"role": "user", "content": prompt}])
    
    # Save successful retrieval pattern to memory
    if store and config:
        try:
            user_id = get_user_id_from_config(config)
            save_successful_retrieval(store, user_id, question, response.content)
            print(f"💾 Saved successful retrieval to memory for user {user_id}")
        except Exception as e:
            print(f"⚠️ Memory save error (continuing): {e}")
    
    return {"messages": [response]}
