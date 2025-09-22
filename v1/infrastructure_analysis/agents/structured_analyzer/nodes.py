#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Structured Analyzer Node

LangGraph node function for structured analysis worker.
"""

from langchain_core.messages import HumanMessage

from ...state import WorkerState
from ...state_helpers import (
    create_worker_result,
    create_metadata_with_timing,
    create_error_worker_result
)
from .agent import create_structured_analysis_worker


async def structured_analysis_worker_node(state: WorkerState) -> WorkerState:
    """Structured analysis worker execution node"""
    
    task = state["task"]
    input_code = state["input_code"]
    
    print(f"🔍 Structured Analysis Worker executing task {task.task_id}")
    
    try:
        worker = await create_structured_analysis_worker()
        
        # Get extracted facts and platform from previous workers
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
        
        # Create analysis request
        analysis_request = f"""
Analyze this infrastructure code and extracted facts to generate comprehensive structured analysis:

Platform: {detected_platform}
Code Length: {len(input_code)} characters
Extracted Facts: {len(extracted_facts)} categories

Facts Summary:
{str(extracted_facts)[:1000]}{'...' if len(str(extracted_facts)) > 1000 else ''}

Use the generate_structured_analysis tool to create a thorough analysis including:
- Resource inventory and dependencies
- Complexity assessment and technical debt
- Security analysis and recommendations  
- Migration planning and effort estimates
- Platform-specific insights

Be comprehensive and actionable in your analysis.
"""
        
        from datetime import datetime
        start_time = datetime.now()
        result = await worker.ainvoke({
            "messages": [HumanMessage(content=analysis_request)]
        })
        processing_time = (datetime.now() - start_time).total_seconds()
        
        # Parse structured analysis from agent result
        final_message = result["messages"][-1]
        analysis_output = final_message.content
        structured_analysis = {}
        
        # Try to extract structured analysis from tool call results
        try:
            for message in result["messages"]:
                if hasattr(message, 'content') and isinstance(message.content, str):
                    content = message.content
                    if any(key in content for key in ["analysis", "complexity", "security", "migration"]):
                        try:
                            import json
                            import re
                            
                            # Look for JSON analysis result
                            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content)
                            if json_match:
                                try:
                                    analysis_data = json.loads(json_match.group())
                                    if isinstance(analysis_data, dict) and len(analysis_data) > 2:
                                        structured_analysis = analysis_data
                                        break
                                except:
                                    continue
                        except:
                            continue
            
            # If no structured data found, create basic structure from text
            if not structured_analysis:
                # Parse key information from the text response
                lines = analysis_output.split('\n')
                
                structured_analysis = {
                    "analysis_method": "agent_text_analysis",
                    "platform": detected_platform,
                    "input_summary": {
                        "code_length": len(input_code),
                        "facts_categories": len(extracted_facts),
                        "processing_time": processing_time
                    },
                    "key_findings": [],
                    "complexity_indicators": {},
                    "recommendations": []
                }
                
                # Extract key findings from agent output
                current_section = None
                for line in lines:
                    line = line.strip()
                    if any(word in line.lower() for word in ["complexity", "security", "migration", "recommendation"]):
                        if line.endswith(':'):
                            current_section = line[:-1].lower()
                        elif line and current_section:
                            if current_section not in structured_analysis:
                                structured_analysis[current_section] = []
                            structured_analysis[current_section].append(line)
                
        except Exception as parse_error:
            print(f"⚠️ Failed to parse structured analysis: {parse_error}")
            structured_analysis = {
                "parsing_error": str(parse_error),
                "raw_output_length": len(analysis_output),
                "fallback_analysis": {
                    "platform": detected_platform,
                    "facts_processed": bool(extracted_facts),
                    "output_generated": bool(analysis_output)
                }
            }
        
        # Ensure we have some analysis data
        if not structured_analysis:
            structured_analysis = {
                "basic_analysis": True,
                "platform": detected_platform,
                "facts_count": len(extracted_facts),
                "code_length": len(input_code),
                "analysis_timestamp": datetime.now().isoformat()
            }
        
        worker_result = create_worker_result(
            task_id=task.task_id,
            worker_type="structured_analyzer",
            platform=detected_platform,
            success=True,
            processing_time=processing_time,
            confidence=0.85,  # High confidence with comprehensive analysis
            structured_analysis=structured_analysis,
            extracted_facts={
                "analysis_method": "structured_analysis_worker",
                "input_facts_count": len(extracted_facts),
                "output_analysis_keys": list(structured_analysis.keys()),
                "platform_detected": detected_platform
            },
            metadata=create_metadata_with_timing(
                analysis_categories=len(structured_analysis),
                input_facts_processed=len(extracted_facts)
            )
        )
        
        print(f" Structured Analysis Worker completed in {processing_time:.2f}s")
        print(f"📊 Generated analysis with {len(structured_analysis)} main categories")
        
        return {**state, "worker_results": [worker_result]}
        
    except Exception as e:
        print(f" Structured Analysis Worker failed: {e}")
        
        worker_result = create_error_worker_result(
            task_id=task.task_id,
            worker_type="structured_analyzer",
            error_message=str(e),
            platform=task.platform or "unknown"
        )
        
        return {**state, "worker_results": [worker_result]}


__all__ = ["structured_analysis_worker_node"]