"""
Orchestrator-Worker Graph Implementation

Prod-grade infrastructure analysis workflow using the orchestrator-worker pattern.
Uses sequential execution for compatibility while maintaining modular architecture.

Key Features:
- Dynamic orchestrator-driven task planning
- Specialized worker agents with dedicated tools
- GitHub Spec Kit methodology for specifications
- Comprehensive synthesis and quality assurance
- Neo4j storage with deduplication
- Configuration-based prompts for maintainability
"""

from typing import Any
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from infrastructure_analysis.state_helpers import generate_analysis_id, generate_timestamp

# Import our orchestrator-worker components  
from infrastructure_analysis.state import (
    InfrastructureAnalysisState, 
    WorkerState, 
    WorkerTask
)
from infrastructure_analysis.nodes import (
    orchestrator_node,
    synthesizer_node,
    universal_extraction_node,
    structured_analysis_worker_node,
    specification_generation_worker_node,
    storage_management_worker_node
)


# ============================================================================
# LANGGRAPH-NATIVE CHAT INPUT HANDLING
# ============================================================================

def extract_input_code_from_messages(state: InfrastructureAnalysisState) -> InfrastructureAnalysisState:
    """
    Extract infrastructure code from chat messages (pure LangGraph pattern).
    
    Follows the exact pattern from working code_gen agent.
    """
    print("📝 Extracting infrastructure code from messages...")
    
    messages = state.get("messages", [])
    input_code = ""
    
    # Find the most recent human message with code (like code_gen does)
    for message in reversed(messages):
        if hasattr(message, 'content') and message.content:
            content = message.content
            # Any content from user becomes our input_code
            input_code = str(content)
            break
    
    # Initialize state fields (simple like code_gen)
    return {
        **state,
        "input_code": input_code,
        "analysis_requirements": state.get("analysis_requirements", {}),
        "orchestrator_decision": state.get("orchestrator_decision", {}),
        "worker_assignments": state.get("worker_assignments", []),
        "worker_results": state.get("worker_results", []),
        "active_workers": state.get("active_workers", []),
        "completed_workers": state.get("completed_workers", []),
        "failed_workers": state.get("failed_workers", []),
        "synthesized_results": state.get("synthesized_results", {}),
        "final_analysis": state.get("final_analysis", ""),
        "storage_result": state.get("storage_result", ""),
        "session_id": state.get("session_id", generate_analysis_id()),
        "start_time": state.get("start_time", generate_timestamp()),
        "total_processing_time": state.get("total_processing_time", 0.0),
        "error_messages": state.get("error_messages", []),
        "warnings": state.get("warnings", [])
    }


# ============================================================================
# CHAT RESPONSE FUNCTION
# ============================================================================

def create_chat_response(state: InfrastructureAnalysisState) -> InfrastructureAnalysisState:
    """
    Create final AI message response for LangGraph Studio Chat interface.
    
    Extracts and displays the 3 key artifacts: extracted facts, generated spec, analysis summary.
    """
    
    # Extract platform and complexity from synthesized results (primary source) then fallback to orchestrator
    synthesized_results = state.get("synthesized_results", {})
    platform = "unknown"
    complexity = "unknown"
    
    # Use synthesized results first (most accurate) - key fix!
    if synthesized_results and synthesized_results.get("platform"):
        platform = synthesized_results.get("platform", "unknown")
        complexity_info = synthesized_results.get("complexity", {})
        if isinstance(complexity_info, dict):
            complexity = complexity_info.get("level", "unknown")
        else:
            complexity = str(complexity_info)
    
    # Fallback to orchestrator decision if no synthesized results
    if platform == "unknown":
        orchestrator_decision = state.get("orchestrator_decision", {})
        if hasattr(orchestrator_decision, 'detected_platforms'):
            platforms = orchestrator_decision.detected_platforms
            if platforms:
                platform = platforms[0]
                if len(platforms) > 1:
                    platform = f"{platform} (+{len(platforms)-1} others)"
        elif isinstance(orchestrator_decision, dict):
            platforms = orchestrator_decision.get("detected_platforms", [])
            if platforms:
                platform = platforms[0]
                if len(platforms) > 1:
                    platform = f"{platform} (+{len(platforms)-1} others)"
        
        if hasattr(orchestrator_decision, 'complexity_assessment'):
            complexity = orchestrator_decision.complexity_assessment
        elif isinstance(orchestrator_decision, dict):
            complexity = orchestrator_decision.get("complexity_assessment", "unknown")
    
    # Extract the 3 key artifacts from worker results and synthesized results
    worker_results = state.get("worker_results", [])
    extracted_facts = {}
    generated_spec = ""
    analysis_summary = ""
    storage_status = "not processed"
    storage_details = ""
    
    # First check synthesized results for the final specification (key fix!)
    synthesized_results = state.get("synthesized_results", {})
    final_spec = state.get("final_specification", "")
    if final_spec and len(final_spec) > 100:
        generated_spec = final_spec
    
    for result in worker_results:
        worker_type = getattr(result, 'worker_type', '')
        
        if worker_type == "universal_extractor":
            extracted_facts = getattr(result, 'extracted_facts', {})
        elif worker_type == "spec_generator" and not generated_spec:
            # Only use worker spec if no synthesized spec available
            generated_spec = getattr(result, 'natural_spec', '')
        elif worker_type == "structured_analyzer":
            structured_analysis = getattr(result, 'structured_analysis', {})
            if structured_analysis:
                # Create analysis summary from structured analysis
                components = structured_analysis.get("components", [])
                dependencies = structured_analysis.get("dependencies", [])
                if components or dependencies:
                    analysis_summary = f"Found {len(components)} components and {len(dependencies)} dependencies"
                else:
                    analysis_summary = "Structured analysis completed"
        elif worker_type == "storage_manager":
            if getattr(result, 'success', False):
                storage_status = "stored successfully"
                facts = getattr(result, 'extracted_facts', {})
                if isinstance(facts, dict):
                    storage_info = facts.get("storage_details", {})
                    if isinstance(storage_info, dict):
                        agent_decisions = storage_info.get("agent_decisions", [])
                        if agent_decisions:
                            storage_details = f" (Agent: {', '.join(agent_decisions)})"
            else:
                storage_status = "storage skipped"
    
    # Fallback to state storage_result if no worker result found
    if storage_status == "not processed":
        storage_status = state.get("storage_result", "not processed")
    
    # Build the response with the 3 key artifacts
    response_parts = [
        f"🔍 **Infrastructure Analysis Complete**",
        f"",
        f"**Platform Detected:** {platform.title()}",
        f"**Complexity Level:** {complexity.title()}",
        f"**Storage Status:** {storage_status}{storage_details}",
    ]
    
    # Artifact 1: Extracted Structured Facts
    if extracted_facts:
        response_parts.extend([
            f"",
            f"## 📊 **Extracted Structured Facts**",
        ])
        
        # Display key fact categories
        for category, facts in extracted_facts.items():
            if facts and category != "storage_details":  # Skip storage metadata
                if isinstance(facts, dict):
                    fact_count = len(facts)
                    response_parts.append(f"- **{category.replace('_', ' ').title()}**: {fact_count} items")
                elif isinstance(facts, list):
                    response_parts.append(f"- **{category.replace('_', ' ').title()}**: {len(facts)} items")
                else:
                    response_parts.append(f"- **{category.replace('_', ' ').title()}**: {facts}")
    
    # Artifact 2: Generated Specification (show full content for real specifications)
    if generated_spec:
        # Show more of real specifications, less of generic ones
        if len(generated_spec) > 2000 and any(keyword in generated_spec for keyword in ['package[', 'service[', 'user[', 'template[']):
            # Real Chef specification - show more content
            spec_preview = generated_spec[:1500] + "..." if len(generated_spec) > 1500 else generated_spec
        else:
            # Generic specification - show less
            spec_preview = generated_spec[:400] + "..." if len(generated_spec) > 400 else generated_spec
            
        response_parts.extend([
            f"",
            f"## 📋 **Generated Infrastructure Specification**",
            f"```",
            f"{spec_preview}",
            f"```"
        ])
    
    # Artifact 3: Analysis Summary
    if analysis_summary:
        response_parts.extend([
            f"",
            f"## 🔍 **Analysis Summary**",
            f"{analysis_summary}"
        ])
    
    # If no artifacts were found, provide fallback information
    if not extracted_facts and not generated_spec and not analysis_summary:
        # Get info from synthesized results as fallback
        synthesized = state.get("synthesized_results", {})
        final_analysis = state.get("final_analysis", {})
        
        if synthesized.get("analysis_summary"):
            response_parts.extend([
                f"",
                f"## 🔍 **Analysis Summary**",
                f"{synthesized['analysis_summary']}"
            ])
        
        if synthesized.get("specification_summary"):
            response_parts.extend([
                f"",
                f"## 📋 **Infrastructure Specification**",
                f"{synthesized['specification_summary']}"
            ])
    
    response_content = "\n".join(response_parts)
    
    # Create AI message response
    ai_response = AIMessage(content=response_content)
    
    # Add to messages for chat continuity
    updated_messages = state.get("messages", []) + [ai_response]
    
    return {
        **state,
        "messages": updated_messages
    }


# ============================================================================
# WORKFLOW ROUTING FUNCTIONS
# ============================================================================

def orchestrator_routing(state: InfrastructureAnalysisState) -> str:
    """
    Route from orchestrator to first worker.
    
    Simplified workflow with universal extraction agent.
    """
    
    worker_assignments = state.get("worker_assignments", [])
    orchestrator_decision = state.get("orchestrator_decision")
    
    if worker_assignments and orchestrator_decision:
        print(f"📋 Orchestrator completed: {len(worker_assignments)} workers assigned")
        return "universal_extraction_worker"
    else:
        print("⚠️ Orchestrator failed - routing to synthesizer")
        return "synthesizer"


def worker_routing(state: InfrastructureAnalysisState) -> str:
    """Simplified sequential routing through workers with recursion protection"""
    
    worker_results = state.get("worker_results", [])
    
    # Count completed workers by type (success OR failure counts as completed)
    completed_workers = {result.worker_type for result in worker_results}
    
    # Recursion protection - if we have results but no successes, move to synthesizer
    if len(worker_results) >= 4 and len(completed_workers) >= 3:
        print("⚠️ Recursion protection: Moving to synthesizer with available results")
        return "synthesizer"
    
    # Simplified sequential execution order
    if "universal_extractor" not in completed_workers:
        return "universal_extraction_worker"
    elif "structured_analyzer" not in completed_workers:
        return "structured_analysis_worker"
    elif "spec_generator" not in completed_workers:
        return "specification_generation_worker"
    elif "storage_manager" not in completed_workers:
        return "storage_management_worker"
    else:
        return "synthesizer"


# ============================================================================
# WORKER ADAPTER FUNCTIONS
# ============================================================================

async def universal_extraction_adapter(state: InfrastructureAnalysisState) -> InfrastructureAnalysisState:
    """Adapter to run universal extraction worker with orchestrator state"""
    
    # Create worker state from orchestrator state
    worker_assignments = state.get("worker_assignments", [])
    extraction_task = None
    
    # Look for extraction-related task assignments
    for assignment in worker_assignments:
        if assignment.worker_type in ["universal_extractor", "platform_detector", "chef_extractor", "puppet_extractor", "terraform_extractor"]:
            extraction_task = assignment
            break
    
    if not extraction_task:
        # Create default universal extraction task
        extraction_task = WorkerTask(
            task_id="extraction_001",
            worker_type="universal_extractor",
            platform="all",
            code_section=state["input_code"],
            requirements={"analysis_type": "comprehensive", "multi_platform": True},
            priority=1
        )
    
    worker_state = WorkerState(
        task=extraction_task,
        input_code=state["input_code"],
        worker_results=[]
    )
    
    # Execute universal extraction worker
    result_state = await universal_extraction_node(worker_state)
    
    # Merge results back to orchestrator state
    new_results = result_state.get("worker_results", [])
    return {
        **state,
        "worker_results": state.get("worker_results", []) + new_results
    }


async def structured_analysis_adapter(state: InfrastructureAnalysisState) -> InfrastructureAnalysisState:
    """Adapter to run structured analysis worker"""
    
    worker_assignments = state.get("worker_assignments", [])
    analysis_task = None
    
    for assignment in worker_assignments:
        if assignment.worker_type == "structured_analyzer":
            analysis_task = assignment
            break
    
    if not analysis_task:
        analysis_task = WorkerTask(
            task_id="analysis_001",
            worker_type="structured_analyzer",
            platform="all",
            code_section=state["input_code"],
            requirements={"analysis_depth": "standard"},
            priority=3
        )
    
    worker_state = WorkerState(
        task=analysis_task,
        input_code=state["input_code"],
        worker_results=[]
    )
    
    result_state = await structured_analysis_worker_node(worker_state)
    new_results = result_state.get("worker_results", [])
    
    return {
        **state,
        "worker_results": state.get("worker_results", []) + new_results
    }


async def specification_generation_adapter(state: InfrastructureAnalysisState) -> InfrastructureAnalysisState:
    """Adapter to run specification generation worker"""
    
    worker_assignments = state.get("worker_assignments", [])
    spec_task = None
    
    for assignment in worker_assignments:
        if assignment.worker_type == "spec_generator":
            spec_task = assignment
            break
    
    if not spec_task:
        spec_task = WorkerTask(
            task_id="spec_001",
            worker_type="spec_generator",
            platform="all",
            code_section=state["input_code"],
            requirements={"format": "spec_kit_professional"},
            priority=4
        )
    
    worker_state = WorkerState(
        task=spec_task,
        input_code=state["input_code"],
        worker_results=[]
    )
    
    result_state = await specification_generation_worker_node(worker_state)
    new_results = result_state.get("worker_results", [])
    
    return {
        **state,
        "worker_results": state.get("worker_results", []) + new_results
    }


async def storage_management_adapter(state: InfrastructureAnalysisState) -> InfrastructureAnalysisState:
    """Adapter to run storage management worker"""
    
    worker_assignments = state.get("worker_assignments", [])
    storage_task = None
    
    for assignment in worker_assignments:
        if assignment.worker_type == "storage_manager":
            storage_task = assignment
            break
    
    if not storage_task:
        storage_task = WorkerTask(
            task_id="storage_001",
            worker_type="storage_manager",
            platform="all",
            code_section=state["input_code"],
            requirements={"deduplication": True},
            priority=5
        )
    
    worker_state = WorkerState(
        task=storage_task,
        input_code=state["input_code"],
        worker_results=[]
    )
    
    result_state = await storage_management_worker_node(worker_state)
    new_results = result_state.get("worker_results", [])
    
    return {
        **state,
        "worker_results": state.get("worker_results", []) + new_results
    }


# ============================================================================
# MAIN WORKFLOW CREATION
# ============================================================================

def create_infrastructure_analysis_graph():
    """
    Create the infrastructure analysis LangGraph using orchestrator-worker pattern.
    
    Features:
    - Dynamic orchestrator planning with Spec Kit methodology
    - Sequential worker execution for reliability
    - Modular architecture with configuration-based prompts
    - Prod-grade specification generation
    - Comprehensive synthesis and quality assurance
    - LangGraph Studio Chat interface enabled
    
    Returns:
        Compiled LangGraph workflow
    """
    
    # Create StateGraph using pure LangGraph pattern (like working context_agent and code_gen)
    workflow = StateGraph(InfrastructureAnalysisState)
    
    # Add input extraction node (LangGraph pattern for chat input)
    workflow.add_node("extract_input", extract_input_code_from_messages)
    
    # Add orchestrator node
    workflow.add_node("orchestrator", orchestrator_node)
    
    # Add simplified worker adapter nodes
    workflow.add_node("universal_extraction_worker", universal_extraction_adapter)
    workflow.add_node("structured_analysis_worker", structured_analysis_adapter)
    workflow.add_node("specification_generation_worker", specification_generation_adapter)
    workflow.add_node("storage_management_worker", storage_management_adapter)
    
    # Add synthesizer node
    workflow.add_node("synthesizer", synthesizer_node)
    
    # Add chat response node for LangGraph Studio Chat interface
    workflow.add_node("chat_response", create_chat_response)
    
    # Define workflow edges (LangGraph pattern)
    workflow.add_edge(START, "extract_input")
    workflow.add_edge("extract_input", "orchestrator")
    
    # Orchestrator routing
    workflow.add_conditional_edges(
        "orchestrator",
        orchestrator_routing,
        {
            "universal_extraction_worker": "universal_extraction_worker",
            "synthesizer": "synthesizer"
        }
    )
    
    # Simplified sequential worker routing
    workflow.add_conditional_edges(
        "universal_extraction_worker",
        worker_routing,
        {
            "structured_analysis_worker": "structured_analysis_worker",
            "specification_generation_worker": "specification_generation_worker",
            "storage_management_worker": "storage_management_worker",
            "synthesizer": "synthesizer"
        }
    )
    
    workflow.add_conditional_edges(
        "structured_analysis_worker",
        worker_routing,
        {
            "specification_generation_worker": "specification_generation_worker",
            "storage_management_worker": "storage_management_worker",
            "synthesizer": "synthesizer"
        }
    )
    
    workflow.add_conditional_edges(
        "specification_generation_worker",
        worker_routing,
        {
            "storage_management_worker": "storage_management_worker",
            "synthesizer": "synthesizer"
        }
    )
    
    # Storage worker always goes to synthesizer (final step)
    workflow.add_edge("storage_management_worker", "synthesizer")
    
    # Synthesizer goes to chat response, then ends  
    workflow.add_edge("synthesizer", "chat_response")
    workflow.add_edge("chat_response", END)
    
    return workflow.compile()


# Export compiled app for standard LangGraph pattern
app = create_infrastructure_analysis_graph()
