#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Synthesizer Node

LangGraph node function for synthesizer that combines all worker results.
"""

from datetime import datetime
from langchain_core.messages import HumanMessage

from ...state import InfrastructureAnalysisState
from ...utils import get_synthesizer_prompt
from .agent import create_synthesizer_agent


async def synthesizer_node(state: InfrastructureAnalysisState) -> InfrastructureAnalysisState:
    """
    Main synthesizer node that combines all worker results.
    
    This is the final step in the orchestrator-worker workflow that
    creates the unified analysis and comprehensive specification.
    """
    
    print("🔄 Synthesizer combining all worker results...")
    
    worker_results = state.get("worker_results", [])
    if not worker_results:
        return {
            **state,
            "error_messages": ["No worker results available for synthesis"],
            "synthesized_results": {},
            "final_analysis": "Synthesis failed: No worker results"
        }
    
    try:
        # Create synthesizer agent
        synthesizer = await create_synthesizer_agent()
        
        # Prepare synthesis summary
        successful_workers = [r for r in worker_results if r.success]
        failed_workers = [r for r in worker_results if not r.success]
        
        worker_summary = []
        for result in successful_workers:
            summary_info = f"- {result.worker_type} ({result.platform}): "
            if result.extracted_facts:
                summary_info += f"extracted {len(result.extracted_facts)} fact categories, "
            if result.structured_analysis:
                summary_info += f"analysis with {len(result.structured_analysis)} components, "
            if result.natural_spec:
                summary_info += f"specification ({len(result.natural_spec)} chars), "
            summary_info += f"confidence: {result.confidence:.2f}"
            worker_summary.append(summary_info)
        
        # Prepare explicit synthesis request that guides agent through tool workflow
        synthesis_request = f"""Please synthesize the infrastructure analysis results using your tools systematically:

1. **First, use analyze_worker_results** to comprehensively analyze all worker outputs
2. **Then, use synthesize_unified_analysis** to create unified analysis from the results  
3. **Finally, use create_comprehensive_specification** to generate a detailed, platform-specific specification

## Worker Results Summary:
- Total workers: {len(worker_results)}
- Successful workers: {len(successful_workers)}
- Failed workers: {len(failed_workers)}

## Worker Details:
{chr(10).join(worker_summary)}

Please follow the systematic tool workflow to create a comprehensive, real infrastructure specification based on the actual worker findings. Focus on creating practical, actionable results that are specific to the detected platforms and extracted facts."""
        
        start_time = datetime.now()
        result = await synthesizer.ainvoke({
            "messages": [HumanMessage(content=synthesis_request)]
        })
        processing_time = (datetime.now() - start_time).total_seconds()
        
        # Extract synthesis from agent result
        final_message = result["messages"][-1]
        synthesis_output = final_message.content
        
        # Extract real specification from spec generator worker (key fix!)
        natural_specification = ""
        for worker_result in successful_workers:
            if worker_result.worker_type == "spec_generator" and hasattr(worker_result, 'natural_spec'):
                if worker_result.natural_spec and len(worker_result.natural_spec) > 100:
                    natural_specification = worker_result.natural_spec
                    print(f"✅ Using real specification from spec generator: {len(natural_specification)} chars")
                    break
        
        # Try to parse synthesis results from agent output
        synthesized_results = {}
        unified_analysis = ""
        
        try:
            for message in result["messages"]:
                if hasattr(message, 'content') and isinstance(message.content, str):
                    content = message.content
                    
                    # Look for structured synthesis results
                    if any(keyword in content for keyword in ["synthesis", "analysis", "specification"]):
                        try:
                            import json
                            import re
                            
                            # Look for JSON synthesis result
                            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content)
                            if json_match:
                                try:
                                    synthesis_data = json.loads(json_match.group())
                                    if isinstance(synthesis_data, dict) and len(synthesis_data) > 1:
                                        synthesized_results = synthesis_data
                                        break
                                except:
                                    continue
                        except:
                            continue
            
            # Extract unified analysis and specification from content
            content_lines = synthesis_output.split('\n')
            current_section = None
            analysis_lines = []
            spec_lines = []
            
            for line in content_lines:
                line = line.strip()
                if 'analysis' in line.lower() and ':' in line:
                    current_section = 'analysis'
                elif 'specification' in line.lower() and ':' in line:
                    current_section = 'specification'
                elif line:
                    if current_section == 'analysis':
                        analysis_lines.append(line)
                    elif current_section == 'specification':
                        spec_lines.append(line)
            
            unified_analysis = '\n'.join(analysis_lines) if analysis_lines else synthesis_output[:1000]
            # Only use synthesis output for specification if no real spec was found from spec generator
            if not natural_specification:
                natural_specification = '\n'.join(spec_lines) if spec_lines else synthesis_output[1000:2000]
                
        except Exception as parse_error:
            print(f"⚠️ Failed to parse synthesis results: {parse_error}")
            # Use raw output as fallback
            unified_analysis = synthesis_output[:len(synthesis_output)//2]
            # Only use synthesis output for specification if no real spec was found from spec generator
            if not natural_specification:
                natural_specification = synthesis_output[len(synthesis_output)//2:]
        
        # Ensure we have some synthesis data
        if not synthesized_results:
            synthesized_results = {
                "synthesis_method": "agent_generated",
                "worker_count": len(worker_results),
                "successful_workers": len(successful_workers),
                "failed_workers": len(failed_workers),
                "processing_time": processing_time,
                "content_generated": bool(synthesis_output),
                "worker_types_processed": [r.worker_type for r in successful_workers]
            }
        
        # Extract platform and complexity from worker results for chat response
        detected_platforms = []
        complexity_level = "unknown"
        
        # Extract from orchestrator decision if available
        orchestrator_decision = state.get("orchestrator_decision", {})
        
        # Handle OrchestratorDecision object (primary case)
        if hasattr(orchestrator_decision, 'detected_platforms'):
            detected_platforms = orchestrator_decision.detected_platforms or []
            complexity_level = getattr(orchestrator_decision, 'complexity_assessment', "unknown")
        elif isinstance(orchestrator_decision, dict):
            detected_platforms = orchestrator_decision.get("detected_platforms", [])
            complexity_level = orchestrator_decision.get("complexity_assessment", "unknown")
        elif isinstance(orchestrator_decision, str):
            # Handle string orchestrator_decision - parse platforms from logs
            orchestrator_decision_text = orchestrator_decision.lower()
            if "chef" in orchestrator_decision_text:
                detected_platforms = ["chef"]
            if "low" in orchestrator_decision_text:
                complexity_level = "low"
            elif "medium" in orchestrator_decision_text:
                complexity_level = "medium"
            elif "high" in orchestrator_decision_text:
                complexity_level = "high"
        
        # Fallback: extract from worker results (ALWAYS use worker results as they're more accurate)
        for result in successful_workers:
            # Extract from worker's platform field (ignore generic values)
            if hasattr(result, 'platform') and result.platform and result.platform not in ["unknown", "all", "mixed"]:
                if result.platform not in detected_platforms:
                    detected_platforms.append(result.platform)
            
            # Extract from extracted_facts detected_platforms
            if hasattr(result, 'extracted_facts') and isinstance(result.extracted_facts, dict):
                worker_platforms = result.extracted_facts.get("detected_platforms", [])
                
                if isinstance(worker_platforms, list):
                    for platform in worker_platforms:
                        if platform and platform not in ["unknown", "all", "mixed"] and platform not in detected_platforms:
                            detected_platforms.append(platform)
                
                # Also check metadata for detected_platforms
                metadata = getattr(result, 'metadata', {})
                if hasattr(metadata, 'get'):
                    metadata_platforms = metadata.get("detected_platforms", [])
                    if isinstance(metadata_platforms, list):
                        for platform in metadata_platforms:
                            if platform and platform not in ["unknown", "all", "mixed"] and platform not in detected_platforms:
                                detected_platforms.append(platform)
                
                # Legacy: check for platform info in other formats
                platform_info = result.extracted_facts.get("platform", {})
                if isinstance(platform_info, dict):
                    platform_name = platform_info.get("name") or platform_info.get("type")
                    if platform_name and platform_name not in ["unknown", "all", "mixed"] and platform_name not in detected_platforms:
                        detected_platforms.append(platform_name)
                
                # Extract complexity if available
                complexity_info = result.extracted_facts.get("complexity", {})
                if isinstance(complexity_info, dict) and complexity_info.get("level"):
                    complexity_level = complexity_info["level"]
        
        # Use primary platform or join multiple
        primary_platform = detected_platforms[0] if detected_platforms else "unknown"
        
        # Update specification header to use correct platform (key fix!)
        if natural_specification and primary_platform != "unknown":
            # Replace "Unknown Analysis" with correct platform
            natural_specification = natural_specification.replace(
                "Infrastructure Specification: Unknown Analysis", 
                f"Infrastructure Specification: {primary_platform.title()} Analysis"
            )
            # Also replace platform in document info table
            natural_specification = natural_specification.replace(
                "| **Platform** | Unknown |",
                f"| **Platform** | {primary_platform.title()} |"
            )
        if len(detected_platforms) > 1:
            primary_platform = f"{primary_platform} (+{len(detected_platforms)-1} others)"
        
        # Create comprehensive final results with extracted info
        final_results = {
            "synthesis_successful": True,
            "platform": primary_platform,
            "complexity": {
                "level": complexity_level,
                "detected_platforms": detected_platforms
            },
            "worker_summary": {
                "total_workers": len(worker_results),
                "successful_workers": len(successful_workers),
                "failed_workers": len(failed_workers),
                "worker_types": [r.worker_type for r in worker_results]
            },
            "synthesized_analysis": {
                "platform": primary_platform,
                "complexity": complexity_level,
                **synthesized_results
            },
            "unified_analysis": unified_analysis,
            "natural_specification": natural_specification,
            "analysis_summary": unified_analysis[:200] + "..." if len(unified_analysis) > 200 else unified_analysis,
            "specification_summary": natural_specification[:200] + "..." if len(natural_specification) > 200 else natural_specification,
            "processing_metadata": {
                "synthesis_time": processing_time,
                "total_output_length": len(synthesis_output),
                "synthesis_timestamp": datetime.now().isoformat()
            }
        }
        
        print(f" Synthesizer completed successfully in {processing_time:.2f}s")
        print(f"📋 Synthesized results from {len(successful_workers)} successful workers")
        print(f"📄 Generated {len(unified_analysis)} chars analysis, {len(natural_specification)} chars specification")
        
        return {
            **state,
            "synthesized_results": final_results,
            "final_analysis": unified_analysis,
            "final_specification": natural_specification,
            "synthesis_complete": True
        }
        
    except Exception as e:
        print(f" Synthesizer failed: {e}")
        
        return {
            **state,
            "error_messages": [f"Synthesis failed: {str(e)}"],
            "synthesized_results": {
                "synthesis_successful": False,
                "error": str(e),
                "worker_count": len(worker_results),
                "attempted_synthesis": True
            },
            "final_analysis": f"Synthesis failed due to error: {str(e)}",
            "synthesis_complete": False
        }


__all__ = ["synthesizer_node"]