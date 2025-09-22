"""
Document Grading Agent Implementation

Specialized ReAct agent for intelligent document relevance grading.
Uses structured tools to analyze question intent and grade document relevance.
"""

from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

from context_agent.utils import get_llm, get_prompt


# ============================================================================
# GRADING TOOLS
# ============================================================================

class GradeDocuments(BaseModel):
    """Grade documents using a binary score for relevance check."""
    binary_score: str = Field(
        description="Relevance score: 'yes' if relevant, or 'no' if not relevant"
    )


@tool
def grade_document_relevance(question: str, context: str) -> str:
    """Grade the relevance of retrieved context to the user question."""
    
    llm = get_llm()
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
    
    llm = get_llm()
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
# GRADING AGENT FACTORY
# ============================================================================

def create_grading_react_agent():
    """
    Create ReAct agent for intelligent document grading with reasoning.
    
    This agent evaluates the relevance of retrieved documents to the user's question.
    It uses structured tools to analyze question intent and grade document relevance,
    providing reasoning for its decisions.
    
    Returns:
        ReAct agent configured with document grading tools
    """
    
    # Get LLM instance
    llm = get_llm()
    
    # Configure tools for document grading
    tools = [grade_document_relevance, analyze_question_intent]
    
    # Load system prompt from configuration
    grading_system_prompt = get_prompt('grading_system')

    # Create and return the ReAct agent with prompt parameter (works in venv)
    return create_react_agent(llm, tools, prompt=grading_system_prompt)
