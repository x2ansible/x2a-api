"""
Orchestrator Agent Tests

Centralized orchestrator agent tests using x2a_test_framework.
Migrated from infrastructure_analysis/agents/orchestrator/tests/ for better organization.

Test Modules:
- test_orchestrator_unit: Core orchestrator functionality testing
- test_structured_output: Pydantic schema validation testing  
- test_agent_creation: Agent creation and configuration testing
"""

__all__ = [
    "test_orchestrator_unit",
    "test_structured_output", 
    "test_agent_creation"
]
