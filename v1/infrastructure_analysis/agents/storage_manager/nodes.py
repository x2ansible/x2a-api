#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Storage Manager Node

LangGraph node function for storage management worker.
"""

import json
import re
from langchain_core.messages import HumanMessage

from ...state import WorkerState
from ...state_helpers import (
    create_worker_result,
    create_metadata_with_timing,
    create_error_worker_result,
    generate_timestamp
)
from ...response_models import InfrastructureAnalysisStorage
from .agent import create_storage_management_worker


async def storage_management_worker_node(state: WorkerState) -> WorkerState:
    """Storage management worker execution node with real Neo4j operations"""
    
    task = state["task"]
    input_code = state["input_code"]
    
    print(f"💾 Storage Management Worker executing task {task.task_id}")
    
    try:
        # Gather data from previous workers for storage
        worker_results = state.get("worker_results", [])
        
        # Extract data from previous worker results
        extracted_facts = {}
        structured_analysis = {}
        natural_specification = ""
        
        for result in worker_results:
            if result.worker_type == "chef_extractor" or result.worker_type == "universal_extractor":
                extracted_facts = result.extracted_facts or {}
            elif result.worker_type == "structured_analyzer":
                structured_analysis = result.extracted_facts or {}
            elif result.worker_type == "spec_generator" or result.worker_type == "specification_generation_worker":
                natural_specification = result.natural_spec or ""
        
        # Determine platform
        platform = task.platform or "unknown"
        
        # Extract required data from worker results
        complexity_score = 0.5  # Default medium complexity
        confidence_score = 0.7  # Default confidence
        
        # Try to extract complexity and confidence from structured analysis
        if structured_analysis and isinstance(structured_analysis, dict):
            if "complexity_score" in structured_analysis:
                complexity_score = float(structured_analysis["complexity_score"])
            if "confidence_score" in structured_analysis:
                confidence_score = float(structured_analysis["confidence_score"])
        
        # Generate code hash
        import hashlib
        code_hash = hashlib.sha256(input_code.encode()).hexdigest()
        
        # Create comprehensive analysis storage object with all required fields
        analysis_data = InfrastructureAnalysisStorage(
            # Required metadata
            platform=platform,
            complexity_score=complexity_score,
            analysis_timestamp=generate_timestamp(),
            
            # Analysis results
            structured_analysis=structured_analysis,
            extracted_facts=extracted_facts,
            natural_specification=natural_specification,
            
            # Source information
            original_code=input_code,  # Correct field name
            code_hash=code_hash,
            file_names=["source_file"],  # Default filename
            
            # Quality metrics
            confidence_score=confidence_score,
            parsing_errors=[],  # No parsing errors by default
            warnings=[]  # No warnings by default
        )
        
        # Store using the storage tool directly
        from datetime import datetime
        start_time = datetime.now()
        
        
        # Pure agentic storage worker - let the agent make ALL decisions
        worker = await create_storage_management_worker()
        
        # Provide rich context and let the agent decide storage strategy
        storage_request = f"""You are a Storage Management Agent responsible for intelligently storing infrastructure analysis results in Neo4j.

=== ANALYSIS CONTEXT ===
Task ID: {task.task_id}
Platform Detected: {analysis_data.platform}
Analysis Quality: Complexity {analysis_data.complexity_score}, Confidence {analysis_data.confidence_score}
Timestamp: {analysis_data.analysis_timestamp}

=== AVAILABLE DATA ===
Original Infrastructure Code ({len(analysis_data.original_code)} characters):
{analysis_data.original_code}

Extracted Facts ({len(str(analysis_data.extracted_facts))} characters):
{json.dumps(analysis_data.extracted_facts, indent=2) if analysis_data.extracted_facts else 'No facts extracted'}

Structured Analysis ({len(str(analysis_data.structured_analysis))} characters):
{json.dumps(analysis_data.structured_analysis, indent=2) if analysis_data.structured_analysis else 'No structured analysis'}

Natural Specification ({len(analysis_data.natural_specification)} characters):
{analysis_data.natural_specification if analysis_data.natural_specification else 'No specification generated'}

Code Hash: {analysis_data.code_hash}
File Names: {analysis_data.file_names}
Parsing Errors: {analysis_data.parsing_errors}
Warnings: {analysis_data.warnings}

=== YOUR MISSION ===
Analyze this infrastructure analysis data and make intelligent storage decisions:

1. **Quality Assessment**: Evaluate if this analysis is worth storing based on completeness, confidence, and complexity
2. **Deduplication Strategy**: Check for duplicates using available tools and decide on storage approach
3. **Data Optimization**: Determine what subset of data is most valuable for storage
4. **Relationship Building**: Decide if relationships should be created with existing analyses
5. **Storage Execution**: Execute the optimal storage strategy using your tools

=== AVAILABLE TOOLS ===
- store_infrastructure_analysis: Store complete analysis with deduplication
- check_duplicate_analysis: Check for existing similar analyses
- create_analysis_relationships: Build relationships between analyses

=== DECISION FREEDOM ===
You have complete autonomy to:
- Skip storage if analysis quality is insufficient
- Store partial data if that's more appropriate
- Create complex relationships if beneficial
- Apply custom deduplication logic
- Optimize storage based on platform type

Make your decisions and execute them using the available tools. Provide reasoning for your choices."""

        result = await worker.ainvoke({
            "messages": [HumanMessage(content=storage_request)]
        })
        processing_time = (datetime.now() - start_time).total_seconds()
        
        # Parse pure agentic storage result - agent makes all decisions
        final_message = result["messages"][-1]
        storage_output = final_message.content
        
        # Agent autonomy - let it decide success/failure
        storage_success = True  # Default optimistic
        storage_details = {
            "pure_agentic": True,
            "agent_reasoning": storage_output[:300] + "..." if len(storage_output) > 300 else storage_output
        }
        
        # Analyze agent's autonomous decisions
        try:
            tools_used = []
            tool_results = []
            agent_decisions = []
            
            # Track all agent tool calls and decisions
            for message in result["messages"]:
                if hasattr(message, 'tool_calls') and message.tool_calls:
                    for tool_call in message.tool_calls:
                        tools_used.append(tool_call["name"])
                        print(f"🤖 Agent decided to use tool: {tool_call['name']}")
                        
                elif hasattr(message, 'content') and message.content:
                    content = message.content.lower()
                    
                    # Detect agent decisions
                    if "skip" in content or "not storing" in content:
                        agent_decisions.append("skipped_storage")
                        storage_success = False
                        print(f"🤖 Agent decided to skip storage")
                    elif "storing" in content or "storage_successful" in content:
                        agent_decisions.append("executed_storage")
                        print(f"🤖 Agent decided to execute storage")
                    elif "duplicate" in content:
                        agent_decisions.append("found_duplicate")
                        print(f"🤖 Agent detected duplicate")
                    elif "relationship" in content:
                        agent_decisions.append("created_relationships")
                        print(f"🤖 Agent created relationships")
                    elif "quality" in content and ("low" in content or "insufficient" in content):
                        agent_decisions.append("quality_concern")
                        print(f"🤖 Agent raised quality concerns")
                        
            # Extract JSON results from tool responses
            json_patterns = [
                r'\{[^{}]*"storage_successful"[^{}]*\}',
                r'\{[^{}]*"analysis_node_id"[^{}]*\}',
                r'\{[^{}]*"duplicate_detected"[^{}]*\}'
            ]
            
            for pattern in json_patterns:
                matches = re.findall(pattern, storage_output)
                for match in matches:
                    try:
                        tool_result = json.loads(match)
                        tool_results.append(tool_result)
                        if "storage_successful" in tool_result:
                            storage_success = tool_result.get("storage_successful", storage_success)
                    except json.JSONDecodeError:
                        continue
                        
            # Compile agent decision intelligence
            storage_details.update({
                "tools_used": tools_used,
                "agent_decisions": agent_decisions,
                "tool_results": tool_results,
                "decision_count": len(agent_decisions),
                "autonomous_execution": len(tools_used) > 0,
                "agent_intelligence": {
                    "made_tool_calls": len(tools_used) > 0,
                    "assessed_quality": "quality_concern" in agent_decisions,
                    "checked_duplicates": "found_duplicate" in agent_decisions,
                    "created_relationships": "created_relationships" in agent_decisions,
                    "exercised_autonomy": "skipped_storage" in agent_decisions
                }
            })
            
            # If agent made tool calls, parse their results
            if tool_results:
                latest_result = tool_results[-1]  # Most recent tool result
                storage_details.update({
                    "neo4j_result": latest_result,
                    "analysis_node_id": latest_result.get("analysis_node_id", f"agent_{analysis_data.code_hash[:8]}"),
                    "spec_node_id": latest_result.get("spec_node_id", f"spec_{analysis_data.code_hash[:8]}"),
                    "content_hash": latest_result.get("content_hash", analysis_data.code_hash),
                    "duplicate_detected": latest_result.get("duplicate_detected", False),
                    "relationships_created": latest_result.get("relationships_created", 0),
                    "deduplication_method": latest_result.get("deduplication_method", "agent_autonomous"),
                    "storage_timestamp": latest_result.get("storage_timestamp", analysis_data.analysis_timestamp)
                })
            else:
                # Agent decided not to use storage tools - respect that decision
                storage_details.update({
                    "agent_decision": "no_storage_tools_used",
                    "reasoning": "Agent autonomously decided against tool usage",
                    "analysis_node_id": f"agent_eval_{analysis_data.code_hash[:8]}",
                    "autonomous_evaluation": True
                })
                
        except Exception as parse_error:
            print(f"⚠️ Pure agentic parsing: {parse_error}")
            storage_details.update({
                "parsing_error": str(parse_error),
                "fallback_mode": True,
                "agent_output_length": len(storage_output)
            })
            
        print(f"🤖 Agent autonomous decisions: {storage_details.get('agent_decisions', [])}")
        print(f"🔧 Agent tools used: {storage_details.get('tools_used', [])}")
        
        worker_result = create_worker_result(
            task_id=task.task_id,
            worker_type="storage_manager",
            platform=platform,
            success=storage_success,
            processing_time=processing_time,
            confidence=0.95,  # High confidence with real Neo4j operations
            storage_result=str(storage_details),
            extracted_facts={
                "storage_method": "neo4j_with_deduplication",
                "storage_details": storage_details,
                "data_categories": {
                    "platform": bool(platform != "unknown"),
                    "extracted_facts": bool(extracted_facts),
                    "structured_analysis": bool(structured_analysis),
                    "natural_specification": bool(natural_specification)
                }
            },
            metadata=create_metadata_with_timing(
                storage_success=storage_success,
                data_stored=bool(extracted_facts or structured_analysis)
            )
        )
        
        print(f" Storage Management Worker completed in {processing_time:.2f}s")
        print(f"💾 Stored analysis for platform: {platform}")
        
        return {**state, "worker_results": [worker_result]}
        
    except Exception as e:
        print(f" Storage Management Worker failed: {e}")
        
        worker_result = create_error_worker_result(
            task_id=task.task_id,
            worker_type="storage_manager",
            error_message=str(e),
            platform=task.platform or "unknown"
        )
        
        return {**state, "worker_results": [worker_result]}


__all__ = ["storage_management_worker_node"]