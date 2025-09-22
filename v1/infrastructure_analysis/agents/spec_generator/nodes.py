#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Spec Generator Node

LangGraph node function for specification generation worker.
"""

from langchain_core.messages import HumanMessage

from ...state import WorkerState
from ...state_helpers import (
    create_worker_result,
    create_metadata_with_timing,
    create_error_worker_result
)
from ...utils import get_worker_prompt
from .agent import create_specification_generation_worker


async def specification_generation_worker_node(state: WorkerState) -> WorkerState:
    """Prod-grade specification generation worker execution node"""
    
    task = state["task"]
    input_code = state["input_code"]
    
    print(f"📝 Prod-Grade Specification Generation Worker executing task {task.task_id}")
    
    try:
        worker = await create_specification_generation_worker()
        
        # Get extracted facts and platform from previous workers (key fix!)
        worker_results = state.get("worker_results", [])
        extracted_facts = {}
        detected_platform = task.platform or "unknown"
        
        # Find extracted facts from previous worker results
        for result in worker_results:
            if result.worker_type in ["universal_extractor", "chef_extractor", "puppet_extractor", "terraform_extractor", "platform_detector"]:
                if result.extracted_facts:
                    extracted_facts.update(result.extracted_facts)
                if hasattr(result, 'platform') and result.platform and result.platform != "unknown":
                    detected_platform = result.platform
        
        # Generate specification request with real extracted facts
        spec_request = get_worker_prompt(
            "spec_generator",
            "generation_prompt",
            platform=detected_platform,
            code_length=len(input_code)
        )
        
        # Add extracted facts to the request for the tool
        if extracted_facts:
            import json
            facts_preview = {}
            # Include key facts for the tool
            for key, value in list(extracted_facts.items())[:10]:  # Limit for prompt size
                if isinstance(value, (str, int, float, bool, list)):
                    facts_preview[key] = value
                elif isinstance(value, dict):
                    facts_preview[key] = str(value)[:200]  # Truncate long dicts
                    
            spec_request += f"\n\nExtracted Facts Available: {json.dumps(facts_preview, indent=2)[:800]}"
            spec_request += f"\n\nCall generate_spec_kit_specification with these real extracted facts."
        
        from datetime import datetime
        start_time = datetime.now()
        result = await worker.ainvoke({
            "messages": [HumanMessage(content=spec_request)]
        })
        processing_time = (datetime.now() - start_time).total_seconds()
        
        # Extract specification from agent result by parsing tool call results
        final_message = result["messages"][-1]
        spec_output = final_message.content
        quality_metrics = {}
        
        # Parse agent's tool call results properly (key fix!)
        try:
            # Check for tool call results in messages
            for message in result["messages"]:
                # Look for ToolMessage (LangGraph stores tool results here)
                if hasattr(message, 'type') and message.type == "tool":
                    if hasattr(message, 'content'):
                        try:
                            import json
                            # Tool content is usually JSON string
                            tool_result = json.loads(message.content) if isinstance(message.content, str) else message.content
                            if isinstance(tool_result, dict) and tool_result.get("success"):
                                actual_spec = tool_result.get("spec_kit_specification", "")
                                if actual_spec and len(actual_spec) > 100:  # Valid specification
                                    spec_output = actual_spec
                                    quality_metrics = tool_result.get("quality_metrics", {})
                                    print(f"✅ Extracted real specification from tool result: {len(actual_spec)} chars")
                                    break
                        except (json.JSONDecodeError, TypeError):
                            continue
                            
                # Fallback: check for tool results in AI message content
                elif hasattr(message, 'content') and isinstance(message.content, str):
                    if "spec_kit_specification" in message.content and "{" in message.content:
                        try:
                            import json
                            import re
                            # Look for JSON tool result in content
                            json_match = re.search(r'\{[^}]*"spec_kit_specification"[^}]*\}', message.content, re.DOTALL)
                            if json_match:
                                tool_result = json.loads(json_match.group())
                                if tool_result.get("success"):
                                    actual_spec = tool_result.get("spec_kit_specification", "")
                                    if actual_spec and len(actual_spec) > 100:
                                        spec_output = actual_spec
                                        quality_metrics = tool_result.get("quality_metrics", {})
                                        print(f"✅ Extracted real specification from message content: {len(actual_spec)} chars")
                                        break
                        except (json.JSONDecodeError, ValueError):
                            continue
            
            # If no tool result found, use agent's final output
            if not quality_metrics:
                print(f"⚠️ No tool result found, using agent output: {len(spec_output)} chars")
                quality_metrics = {
                    "agent_generated": True,
                    "word_count": len(spec_output.split()),
                    "contains_sections": any(marker in spec_output for marker in ["##", "**", "###"]),
                    "length_adequate": len(spec_output) > 500,
                    "tool_extraction_failed": True
                }
                
        except Exception as parse_error:
            print(f"⚠️ Failed to parse specification output: {parse_error}")
            quality_metrics = {
                "parsing_error": str(parse_error),
                "fallback_used": True
            }
        
        worker_result = create_worker_result(
            task_id=task.task_id,
            worker_type="spec_generator",
            platform=detected_platform,  # Use detected platform instead of task platform
            success=True,
            processing_time=processing_time,
            confidence=0.90,  # High confidence with Spec Kit methodology
            natural_language_spec=spec_output,
            extracted_facts={
                "specification_method": "spec_kit_integrated",
                "quality_metrics": quality_metrics,
                "word_count": len(spec_output.split()),
                "includes_checklists": "- [ ]" in spec_output,
                "platform_detected": detected_platform,
                "facts_used": len(extracted_facts)
            },
            metadata=create_metadata_with_timing(
                spec_word_count=len(spec_output.split()),
                generation_method="spec_kit_integrated",
                platform_detected=detected_platform
            )
        )
        
        print(f" Prod-Grade Specification Generation Worker completed in {processing_time:.2f}s")
        print(f"📊 Generated specification: {len(spec_output.split())} words with Spec Kit integration")
        
        return {**state, "worker_results": [worker_result]}
        
    except Exception as e:
        print(f" Prod-Grade Specification Generation Worker failed: {e}")
        
        worker_result = create_error_worker_result(
            task_id=task.task_id,
            worker_type="spec_generator",
            error_message=str(e),
            platform=detected_platform if 'detected_platform' in locals() else (task.platform or "unknown")
        )
        
        return {**state, "worker_results": [worker_result]}


__all__ = ["specification_generation_worker_node"]