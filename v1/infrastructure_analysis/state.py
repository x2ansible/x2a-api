"""
Orchestrator-Worker State Management for Infrastructure Analysis

This implements the true orchestrator-worker pattern with:
- Dynamic worker assignment using LangGraph Send API
- Independent worker state management  
- Result synthesis and coordination
"""

from typing import Dict, List, Any, Optional, Union
from typing_extensions import TypedDict, Annotated
from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages, MessagesState
from pydantic import BaseModel, Field
import operator

# Note: We define our own state structures specifically for orchestrator-worker pattern
# This is separate from the existing state.py to maintain modularity


class WorkerTask(BaseModel):
    """Task assigned to a worker by orchestrator"""
    
    task_id: str = Field(description="Unique task identifier")
    worker_type: str = Field(description="Type of worker needed")
    platform: str = Field(description="Platform to analyze")
    code_section: str = Field(description="Code section to process")
    requirements: Dict[str, Any] = Field(description="Specific task requirements")
    priority: int = Field(description="Task priority (1=highest)")


class WorkerResult(BaseModel):
    """Result from a worker execution"""
    
    task_id: str = Field(description="Original task ID")
    worker_type: str = Field(description="Worker that produced result")
    platform: str = Field(description="Platform analyzed")
    success: bool = Field(description="Whether task succeeded")
    
    # Results
    extracted_facts: Dict[str, Any] = Field(default_factory=dict)
    structured_analysis: Dict[str, Any] = Field(default_factory=dict) 
    natural_spec: str = Field(default="")
    confidence: float = Field(default=0.0)
    
    # Metadata
    processing_time: float = Field(default=0.0)
    error_message: str = Field(default="")
    warnings: List[str] = Field(default_factory=list)


class OrchestratorDecision(BaseModel):
    """Decision made by orchestrator"""
    
    detected_platforms: List[str] = Field(description="Platforms detected in code")
    complexity_assessment: str = Field(description="Overall complexity assessment")
    worker_assignments: List[WorkerTask] = Field(description="Tasks assigned to workers")
    processing_strategy: str = Field(description="Overall processing strategy")
    estimated_duration: int = Field(description="Estimated processing time")
    confidence: float = Field(default=0.8, description="Confidence in the orchestrator decision")


# Infrastructure Analysis State (following code_gen pattern exactly)
class InfrastructureAnalysisState(MessagesState):
    """
    State for infrastructure analysis workflow.
    Extends MessagesState for LangGraph Studio compatibility.
    """
    
    # Core workflow data (with defaults like code_gen)
    input_code: str = ""
    analysis_requirements: dict = {}
    
    # Orchestrator state (internal, with defaults)
    orchestrator_decision: dict = {}
    worker_assignments: list = []
    
    # Worker state (internal, with defaults)  
    worker_results: list = []
    active_workers: list = []
    completed_workers: list = []
    failed_workers: list = []
    
    # Synthesis state (internal, with defaults)
    synthesized_results: dict = {}
    final_analysis: str = ""
    final_specification: str = ""
    storage_result: str = ""
    
    # Metadata (internal, with defaults)
    session_id: str = ""
    start_time: str = ""
    total_processing_time: float = 0.0
    error_messages: list = []
    warnings: list = []


# Worker-specific state for independent execution
class WorkerState(TypedDict, total=False):
    """
    Independent state for each worker.
    
    Each worker gets its own state instance for independent execution.
    """
    
    # Task assignment
    task: WorkerTask                                   # Assigned task
    input_code: str                                    # Code to analyze
    
    # Worker execution
    worker_results: Annotated[List[WorkerResult], operator.add]  # This worker's results
    
    # For result aggregation back to main state
    session_id: str                                    # Parent session
