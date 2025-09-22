"""
Result Analyzer Tool for Synthesizer

Analyzes all worker results to understand accomplishments and quality.
"""

from typing import Dict, List, Any
from langchain_core.tools import tool


@tool
def analyze_worker_results(worker_results: List[dict]) -> Dict[str, Any]:
    """
    Analyze all worker results to understand what was accomplished.
    
    This tool examines the results from all workers to:
    - Identify successful vs failed workers
    - Extract key findings from each worker
    - Assess overall analysis quality
    - Identify any gaps or inconsistencies
    
    Args:
        worker_results: List of worker result dictionaries
        
    Returns:
        Analysis summary with key findings and quality assessment
    """
    
    if not worker_results:
        return {
            "success": False,
            "message": "No worker results to analyze",
            "summary": {}
        }
    
    # Categorize workers by type and success
    worker_summary = {
        "total_workers": len(worker_results),
        "successful_workers": 0,
        "failed_workers": 0,
        "worker_types_completed": [],
        "key_findings": {},
        "extracted_data": {},
        "quality_indicators": {}
    }
    
    for result in worker_results:
        worker_type = result.get("worker_type", "unknown")
        success = result.get("success", False)
        
        if success:
            worker_summary["successful_workers"] += 1
            worker_summary["worker_types_completed"].append(worker_type)
            
            # Extract key findings by worker type
            if worker_type == "platform_detector":
                worker_summary["key_findings"]["platform_detection"] = {
                    "platforms_found": result.get("extracted_facts", {}).get("platforms_found", []),
                    "primary_platform": result.get("extracted_facts", {}).get("primary_platform", "unknown"),
                    "confidence": result.get("confidence", 0.0)
                }
                
            elif worker_type == "chef_extractor":
                worker_summary["key_findings"]["chef_analysis"] = {
                    "cookbook_analyzed": True,
                    "extraction_method": "chef_facts_extractor",
                    "confidence": result.get("confidence", 0.0)
                }
                
            elif worker_type == "structured_analyzer":
                worker_summary["key_findings"]["structured_analysis"] = {
                    "json_generated": True,
                    "analysis_type": "comprehensive",
                    "confidence": result.get("confidence", 0.0)
                }
                
            elif worker_type == "spec_generator":
                worker_summary["key_findings"]["specification"] = {
                    "spec_generated": True,
                    "spec_length": len(result.get("natural_spec", "")),
                    "confidence": result.get("confidence", 0.0)
                }
                
            elif worker_type == "storage_manager":
                worker_summary["key_findings"]["storage"] = {
                    "stored_successfully": True,
                    "deduplication_applied": True,
                    "confidence": result.get("confidence", 0.0)
                }
        else:
            worker_summary["failed_workers"] += 1
            
        # Store extracted data for synthesis
        worker_summary["extracted_data"][worker_type] = {
            "success": success,
            "extracted_facts": result.get("extracted_facts", {}),
            "structured_analysis": result.get("structured_analysis", {}),
            "natural_spec": result.get("natural_spec", ""),
            "error_message": result.get("error_message", "")
        }
    
    # Calculate quality indicators
    success_rate = worker_summary["successful_workers"] / worker_summary["total_workers"]
    
    worker_summary["quality_indicators"] = {
        "success_rate": success_rate,
        "has_platform_detection": "platform_detector" in worker_summary["worker_types_completed"],
        "has_structured_analysis": "structured_analyzer" in worker_summary["worker_types_completed"],
        "has_specification": "spec_generator" in worker_summary["worker_types_completed"],
        "has_storage": "storage_manager" in worker_summary["worker_types_completed"],
        "minimum_viable_analysis": success_rate >= 0.6 and len(worker_summary["worker_types_completed"]) >= 3
    }
    
    return {
        "success": True,
        "summary": worker_summary,
        "message": f"Analyzed {len(worker_results)} worker results with {success_rate:.1%} success rate"
    }
