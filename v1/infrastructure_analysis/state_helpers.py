"""
Infrastructure Analysis State Helpers

LangGraph-native state management utilities that support nodes
without being nodes themselves. These helpers create and format
state objects to maintain clean separation of concerns.
"""

import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from functools import wraps

from infrastructure_analysis.state import WorkerResult


def create_worker_result(
    task_id: str, 
    worker_type: str, 
    platform: str, 
    success: bool, 
    **kwargs
) -> WorkerResult:
    """
    Create standardized WorkerResult state objects.
    
    LangGraph-native state factory that ensures consistent
    WorkerResult creation across all worker nodes.
    """
    return WorkerResult(
        task_id=task_id,
        worker_type=worker_type,
        platform=platform,
        success=success,
        processing_time=kwargs.get("processing_time", 0.0),
        confidence=kwargs.get("confidence", 0.0),
        extracted_facts=kwargs.get("extracted_facts", {}),
        structured_analysis=kwargs.get("structured_analysis", {}),
        natural_spec=kwargs.get("natural_language_spec", ""),
        storage_result=kwargs.get("storage_result", ""),
        error_message=kwargs.get("error_message", ""),
        metadata=kwargs.get("metadata", {})
    )


def generate_timestamp() -> str:
    """Generate ISO format timestamp for state objects."""
    return datetime.now().isoformat()


def generate_task_id() -> str:
    """Generate unique task ID for worker assignments."""
    return str(uuid.uuid4())[:8]


def generate_analysis_id() -> str:
    """Generate unique analysis ID for storage operations."""
    return str(uuid.uuid4())


def measure_node_execution(node_func):
    """
    Decorator to measure node execution time.
    
    LangGraph-native timing measurement that preserves
    node function signatures and behavior.
    """
    @wraps(node_func)
    async def wrapper(*args, **kwargs):
        start_time = datetime.now()
        result = await node_func(*args, **kwargs)
        processing_time = (datetime.now() - start_time).total_seconds()
        
        # Add timing to result if it's a state dict
        if isinstance(result, dict) and "metadata" in result:
            if not result["metadata"]:
                result["metadata"] = {}
            result["metadata"]["processing_time"] = processing_time
        
        return result
    
    return wrapper


def create_metadata_with_timing(
    additional_metadata: Optional[Dict[str, Any]] = None,
    **timing_kwargs
) -> Dict[str, Any]:
    """
    Create metadata dict with timing information.
    
    Helper for nodes to create consistent metadata
    with timing and additional context.
    """
    metadata = {
        "timestamp": generate_timestamp(),
        **timing_kwargs
    }
    
    if additional_metadata:
        metadata.update(additional_metadata)
    
    return metadata


def format_agent_request(prompt_template: str, **variables) -> str:
    """
    Format agent request with variables.
    
    LangGraph-native helper for consistent agent
    request formatting across nodes.
    """
    try:
        return prompt_template.format(**variables)
    except KeyError as e:
        # Graceful handling of missing variables
        return prompt_template + f"\n\nNote: Missing variable {e}"


def extract_platform_from_facts(extracted_facts: Dict[str, Any]) -> str:
    """
    Extract platform information from extracted facts.
    
    State helper to consistently determine platform
    from fact extraction results.
    """
    if not extracted_facts:
        return "unknown"
    
    # Check for platform indicators in facts
    if "schema" in extracted_facts:
        schema = extracted_facts["schema"]
        if "chef-facts" in schema:
            return "chef"
        elif "puppet-facts" in schema:
            return "puppet"
        elif "terraform-facts" in schema:
            return "terraform"
    
    # Check for platform-specific keys
    if "cookbook" in extracted_facts:
        return "chef"
    elif "manifests" in extracted_facts:
        return "puppet"
    elif "resources" in extracted_facts and "provider" in str(extracted_facts):
        return "terraform"
    elif "playbooks" in extracted_facts:
        return "ansible"
    
    return "unknown"


def create_error_worker_result(
    task_id: str,
    worker_type: str,
    error_message: str,
    platform: str = "unknown"
) -> WorkerResult:
    """
    Create WorkerResult for error cases.
    
    LangGraph-native error state factory for
    consistent error handling across nodes.
    """
    return create_worker_result(
        task_id=task_id,
        worker_type=worker_type,
        platform=platform,
        success=False,
        error_message=error_message,
        metadata=create_metadata_with_timing()
    )


def validate_state_update(state_update: Dict[str, Any], required_keys: list) -> bool:
    """
    Validate state update contains required keys.
    
    LangGraph-native state validation helper to ensure
    nodes return properly formatted state updates.
    """
    return all(key in state_update for key in required_keys)
