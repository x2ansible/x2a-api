"""
Infrastructure Analysis Agent - LangGraph Implementation

A production-ready infrastructure analysis agent that can analyze Chef, Puppet, Salt, 
and BladeLogic infrastructure code using static analysis tools combined with LLM intelligence.

Features:
- Context window management for large codebases
- Batch processing with checkpointing
- State persistence for long-running analysis
- Configurable via API
- Curl-testable endpoints
"""

__version__ = "1.0.0"

# Import the compiled graph for LangGraph Studio
from .graph import app

__all__ = ["app"]
