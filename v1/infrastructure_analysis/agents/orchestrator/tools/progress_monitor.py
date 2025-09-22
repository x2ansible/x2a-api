"""
Progress Monitor Tool for Orchestrator

This tool monitors worker execution and provides progress insights.
"""

from typing import Dict, List, Any, Union
from langchain_core.tools import tool


@tool
def monitor_worker_progress(worker_results: Union[List[dict], str]) -> Dict[str, Any]:
    """
    Monitor the progress of worker execution and identify issues.
    
    Args:
        worker_results: List of worker results received so far
        
    Returns:
        Progress summary and recommendations
    """
    
    # Handle both list and string inputs (LLM tool calling quirk)
    if isinstance(worker_results, str):
        import json
        import ast
        try:
            # Try JSON parsing first
            worker_results = json.loads(worker_results)
        except json.JSONDecodeError:
            try:
                # Fallback to literal_eval for list-like strings
                worker_results = ast.literal_eval(worker_results)
            except (ValueError, SyntaxError):
                # If parsing fails, create empty list
                worker_results = []
    
    # Ensure worker_results is a list
    if not isinstance(worker_results, list):
        worker_results = []
    
    total_workers = len(worker_results) if worker_results else 0
    successful_workers = len([r for r in worker_results if r.get("success", False)])
    failed_workers = len([r for r in worker_results if not r.get("success", True)])
    
    progress_summary = {
        "total_workers_completed": total_workers,
        "successful_workers": successful_workers,
        "failed_workers": failed_workers,
        "completion_rate": successful_workers / max(total_workers, 1),
        "has_critical_failures": failed_workers > 0
    }
    
    # Identify any critical failures
    critical_failures = []
    for result in worker_results:
        if not result.get("success", True) and result.get("worker_type") in ["platform_detector", "structured_analyzer"]:
            critical_failures.append(result.get("worker_type"))
    
    progress_summary["critical_failures"] = critical_failures
    
    recommendations = []
    if failed_workers > 0:
        recommendations.append("Review failed worker results and consider retry")
    if critical_failures:
        recommendations.append("Critical workers failed - may need fallback strategy")
    if successful_workers >= 3:  # Minimum viable results
        recommendations.append("Sufficient results for synthesis")
    
    progress_summary["recommendations"] = recommendations
    
    return progress_summary
