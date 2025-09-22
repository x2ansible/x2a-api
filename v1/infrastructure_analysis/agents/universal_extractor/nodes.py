#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Universal Extraction Node

LangGraph node function for the universal extraction agent that intelligently
detects platforms and extracts facts from any infrastructure code type.
"""

from langchain_core.messages import HumanMessage

from ...state import WorkerState
from ...state_helpers import (
    create_worker_result,
    create_metadata_with_timing,
    create_error_worker_result
)
from .agent import create_universal_extraction_agent


async def universal_extraction_node(state: WorkerState) -> WorkerState:
    """
    Universal extraction worker node that intelligently detects platforms
    and extracts facts using the most appropriate tools.
    
    This replaces separate platform_detector and platform-specific extractor nodes
    with one intelligent agent that makes the decisions.
    """
    
    task = state["task"]
    input_code = state["input_code"]
    
    print(f"🌍 Universal Extraction Agent executing task {task.task_id}")
    
    try:
        agent = await create_universal_extraction_agent()
        
        # Let the agent intelligently analyze the code
        code_preview = input_code[:3000] + ("..." if len(input_code) > 3000 else "")
        extraction_request = f"""
Analyze this infrastructure code and extract structured facts:

```
{code_preview}
```

Instructions:
1. First detect what platform(s) this code uses (Chef, Puppet, Terraform, etc.)
2. Use the appropriate extraction tool(s) based on what you detect
3. If you detect multiple platforms, extract from each one
4. Provide comprehensive structured facts for all detected infrastructure

Please be thorough and use your available tools intelligently!
"""
        
        from datetime import datetime
        start_time = datetime.now()
        result = await agent.ainvoke({
            "messages": [HumanMessage(content=extraction_request)]
        })
        processing_time = (datetime.now() - start_time).total_seconds()
        
        # Parse the agent's results
        final_message = result["messages"][-1]
        agent_output = final_message.content
        
        # Extract information from the conversation
        detected_platforms = []
        extracted_facts = {}
        confidence = 0.5
        
        # Parse tool call results from the conversation
        for message in result["messages"]:
            if hasattr(message, 'content') and isinstance(message.content, str):
                content = message.content
                
                # Look for platform detection results
                if "detected_platform" in content.lower() or "platform" in content.lower():
                    # Try to extract platform information
                    for platform in ["chef", "puppet", "terraform", "ansible", "bladelogic", "salt"]:
                        if platform in content.lower():
                            if platform not in detected_platforms:
                                detected_platforms.append(platform)
                
                # Look for extraction results
                if any(word in content.lower() for word in ["facts", "resources", "extraction", "analysis"]):
                    try:
                        import json
                        import re
                        
                        # Look for JSON structures in the content
                        json_matches = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content)
                        for match in json_matches:
                            try:
                                parsed = json.loads(match)
                                if isinstance(parsed, dict) and len(parsed) > 2:
                                    extracted_facts.update(parsed)
                                    confidence = 0.8
                            except:
                                continue
                    except:
                        pass
        
        # Determine primary platform
        primary_platform = detected_platforms[0] if detected_platforms else "unknown"
        
        # If no structured facts found, create summary from agent output
        if not extracted_facts:
            extracted_facts = {
                "agent_analysis": agent_output[:1000],
                "detected_platforms": detected_platforms,
                "analysis_method": "universal_agent",
                "raw_output_length": len(agent_output)
            }
        
        worker_result = create_worker_result(
            task_id=task.task_id,
            worker_type="universal_extractor",
            platform=primary_platform,
            success=bool(detected_platforms or extracted_facts),
            processing_time=processing_time,
            confidence=confidence,
            extracted_facts=extracted_facts,
            metadata=create_metadata_with_timing(
                warnings=[] if detected_platforms else ["No clear platform detected"],
                detected_platforms=detected_platforms,
                fact_categories_count=len(extracted_facts)
            )
        )
        
        platform_list = ", ".join(detected_platforms) if detected_platforms else "unknown"
        print(f" Universal Extraction completed in {processing_time:.2f}s")
        print(f"🎯 Detected platforms: {platform_list}")
        print(f"📊 Extracted {len(extracted_facts)} fact categories")
        
        return {
            **state,
            "worker_results": [worker_result]
        }
        
    except Exception as e:
        print(f" Universal Extraction failed: {e}")
        
        worker_result = create_error_worker_result(
            task_id=task.task_id,
            worker_type="universal_extractor",
            error_message=str(e),
            platform="unknown"
        )
        
        return {
            **state,
            "worker_results": [worker_result]
        }
