"""
Context Agent - Configuration-Driven Agentic RAG

Clean LangGraph workflow with intelligent ReAct agents for document retrieval and grading.
- Predictable workflow orchestration  
- Intelligent reasoning via specialized ReAct agents
- Full configuration externalization for maintainability
- Optimized for Ansible automation pattern retrieval

Note: The app is exported directly from graph.py for LangGraph server compatibility.
"""

# Note: We don't import app here to avoid circular imports when LangGraph loads graph.py directly
# The app is available at context_agent.graph.app

__all__ = []