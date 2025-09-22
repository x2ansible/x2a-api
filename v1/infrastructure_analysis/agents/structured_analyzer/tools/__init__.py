"""
Structured Analyzer Tools

LangGraph-compliant focused tools for structured infrastructure analysis.
Each tool has a single responsibility, allowing the agent to intelligently
choose which analyses to perform based on the specific context.

The agent acts as the orchestrator, making intelligent decisions about
which tools to use and in what order, maintaining true agentic behavior.
"""

# Platform Analysis Tools
from .platform_analysis_tools import (
    analyze_chef_infrastructure,
    analyze_puppet_infrastructure,
    analyze_terraform_infrastructure,
    analyze_generic_infrastructure
)

# Specialized Analysis Tools
from .complexity_analysis_tool import calculate_infrastructure_complexity
from .security_analysis_tool import generate_security_considerations
from .migration_analysis_tool import generate_migration_recommendations


__all__ = [
    # Platform Analysis Tools
    "analyze_chef_infrastructure",
    "analyze_puppet_infrastructure", 
    "analyze_terraform_infrastructure",
    "analyze_generic_infrastructure",
    
    # Specialized Analysis Tools
    "calculate_infrastructure_complexity",
    "generate_security_considerations", 
    "generate_migration_recommendations"
]