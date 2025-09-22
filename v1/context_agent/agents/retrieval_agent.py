"""
Retrieval Agent Implementation

Specialized ReAct agent for intelligent retrieval strategy selection.
Uses Neo4j tools to find relevant Ansible automation patterns.
"""

from langgraph.prebuilt import create_react_agent
from context_agent.tools import neo4j_vector_search, neo4j_graph_query
from context_agent.utils import get_llm, get_prompt


def create_retrieval_react_agent():
    """
    Create ReAct agent for intelligent retrieval strategy selection.
    
    This agent uses Neo4j tools to intelligently search for Ansible automation patterns.
    It can choose between vector similarity search and graph relationship queries
    based on the user's question context.
    
    Returns:
        ReAct agent configured with Neo4j retrieval tools
    """
    
    # Get LLM instance
    llm = get_llm()
    
    # Configure tools for retrieval strategies
    tools = [neo4j_vector_search, neo4j_graph_query]
    
    # Load system prompt from configuration
    retrieval_system_prompt = get_prompt('retrieval_system')

    # Create and return the ReAct agent with prompt parameter (works in venv)
    return create_react_agent(llm, tools, prompt=retrieval_system_prompt)
