import os
import tempfile
import subprocess
import json
import asyncio
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, TypedDict, Annotated, Generator, Dict, Any
import httpx

from langchain_core.messages import BaseMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langchain_core.prompts import ChatPromptTemplate

# ---- LLM Configuration ----
def get_llm_config(config_loader=None):
    """Get LLM configuration from config or environment variables."""
    if config_loader:
        try:
            # Try to get from config first - use separate LLM config, not llamastack
            base_url = config_loader.get_llm_api_base()
            model = config_loader.get_llm_model()
            return base_url, model
        except Exception as e:
            print(f"Warning: Could not get LLM config from config_loader: {e}")
    
    # Fallback to environment variables
    base_url = os.getenv("LLM_API_BASE", "http://localhost:8000/v1")
    model = os.getenv("LLM_MODEL", "meta-llama/Llama-3.1-8B-Instruct")
    return base_url, model

# Create FastAPI app instance
app = FastAPI()

# ---- Pydantic Models ----
class PlaybookRequest(BaseModel):
    code: str

class LintResult(BaseModel):
    passed: bool
    summary: str
    issues: List[str]

class AgentResponse(BaseModel):
    final_lint_report: LintResult
    agent_steps: List[str] = []

# ---- Tool Definition ----
@tool
def run_ansible_lint(playbook_code: str) -> dict:
    """
    Lints an Ansible playbook and returns a dict with 'passed', 'summary', and 'issues'.
    """
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".yml") as f:
        f.write(playbook_code)
        fname = f.name
    
    try:
        result = subprocess.run(
            ["ansible-lint", fname],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            timeout=180
        )
        output = result.stdout
        passed = result.returncode == 0
        summary = output.strip() if not passed else "No issues found."
        issues = output.strip().splitlines() if not passed else []
        return {"passed": passed, "summary": summary, "issues": issues}
    except subprocess.TimeoutExpired:
        return {"passed": False, "summary": "ansible-lint command timed out.", "issues": ["Timeout error."]}
    except Exception as e:
        return {"passed": False, "summary": f"Error running ansible-lint: {e}", "issues": [str(e)]}
    finally:
        if os.path.exists(fname):
            os.remove(fname)

# Create a simple tool executor function
def execute_tool(tool_call):
    """Execute a tool call directly."""
    tool_name = tool_call.get("name")
    tool_args = tool_call.get("args", {})
    
    if tool_name == "run_ansible_lint":
        return run_ansible_lint.invoke(tool_args)
    else:
        raise ValueError(f"Unknown tool: {tool_name}")

# ---- LangGraph Agent State ----
class AgentState(TypedDict):
    playbook_code: str
    lint_report: Optional[LintResult]
    messages: Annotated[List[BaseMessage], lambda x, y: x + y]
    agent_steps: Annotated[List[str], lambda x, y: x + y]

# ---- LLM Setup ----
# Initialize with default config (will be updated when ValidationAgent is created)
llm_api_base, llm_model = get_llm_config()
print(f"Connecting to LLM at: {llm_api_base}")
print(f"Using model: {llm_model}")

llm = ChatOpenAI(
    model=llm_model,
    base_url=llm_api_base,
    api_key="not-needed",  # Use api_key instead of openai_api_key
    temperature=0.0,
    request_timeout=60,
    max_retries=1
)

# Bind tools to the LLM
tools = [run_ansible_lint]
llm_with_tools = llm.bind_tools(tools)

# ---- LangGraph Nodes ----
async def call_model(state: AgentState):
    """Node that calls the LLM with the current conversation history."""
    messages = state["messages"]
    agent_steps = state.get("agent_steps", [])

    # Create prompt template with explicit instructions
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", "You are an expert Ansible linting assistant. Your ONLY task is to lint Ansible playbooks using the `run_ansible_lint` tool. When given a playbook, you MUST use this tool to lint it. Do not interpret or modify the playbook, just call the tool. CRITICAL: You must pass the EXACT playbook content as the 'playbook_code' parameter. Do NOT use 'content' or any placeholder - use the actual playbook text that was provided to you."),
        ("human", "Here is the Ansible playbook to validate:\n\n{user_input}\n\nCall the run_ansible_lint tool with the playbook_code parameter set to the exact playbook content above."),
        ("placeholder", "{messages}")
    ])

    user_input_message = HumanMessage(content=state["playbook_code"])
    full_prompt = prompt_template.format_messages(
        user_input=user_input_message,
        messages=messages
    )

    response = await llm_with_tools.ainvoke(full_prompt)
    agent_steps.append(f"LLM decided: {getattr(response, 'content', '') or 'tool_calls'}")
    return {"messages": [response], "agent_steps": agent_steps}

async def call_tool(state: AgentState):
    """Node that executes the tool suggested by the LLM."""
    messages = state["messages"]
    agent_steps = state.get("agent_steps", [])
    last_message = messages[-1]

    if not hasattr(last_message, 'tool_calls') or not last_message.tool_calls:
        agent_steps.append("No tool calls found in the last LLM message.")
        lint_report_output = LintResult(
            passed=False,
            summary="LLM did not attempt to call the 'run_ansible_lint' tool as expected.",
            issues=["LLM did not trigger the expected tool."]
        )
        return {"lint_report": lint_report_output, "agent_steps": agent_steps}

    tool_messages = []
    lint_report_output = None

    for tool_call in last_message.tool_calls:
        tool_name = tool_call.get("name")
        tool_args = tool_call.get("args", {})
        tool_call_id = tool_call.get("id")
        
        if tool_name == "run_ansible_lint":
            agent_steps.append(f"Calling tool: {tool_name} with input: {tool_args}")
            
            try:
                # Execute the tool directly
                raw_tool_output = execute_tool(tool_call)
                
                if isinstance(raw_tool_output, dict) and all(k in raw_tool_output for k in ["passed", "summary", "issues"]):
                    lint_report_output = LintResult(**raw_tool_output)
                    agent_steps.append(f"Tool output: Passed={lint_report_output.passed}")
                    
                    # Create tool message for conversation history
                    tool_message = ToolMessage(
                        content=f"Linting completed. Passed: {lint_report_output.passed}. Summary: {lint_report_output.summary}",
                        tool_call_id=tool_call_id
                    )
                    tool_messages.append(tool_message)
                else:
                    lint_report_output = LintResult(
                        passed=False,
                        summary=f"Unexpected tool output format: {raw_tool_output}",
                        issues=[str(raw_tool_output)]
                    )
                    agent_steps.append("Tool output error: Unexpected format")
                    
                    tool_message = ToolMessage(
                        content=f"Tool execution error: Unexpected output format",
                        tool_call_id=tool_call_id
                    )
                    tool_messages.append(tool_message)
                
            except Exception as e:
                lint_report_output = LintResult(
                    passed=False,
                    summary=f"Tool execution error: {str(e)}",
                    issues=[str(e)]
                )
                agent_steps.append(f"Tool execution failed: {str(e)}")
                
                tool_message = ToolMessage(
                    content=f"Tool execution failed: {str(e)}",
                    tool_call_id=tool_call_id
                )
                tool_messages.append(tool_message)
        else:
            agent_steps.append(f"Unexpected tool call: {tool_name}")
            lint_report_output = LintResult(
                passed=False,
                summary=f"LLM called an unexpected tool: {tool_name}",
                issues=[f"Unexpected tool: {tool_name}"]
            )
            
            tool_message = ToolMessage(
                content=f"Error: Unexpected tool call: {tool_name}",
                tool_call_id=tool_call_id
            )
            tool_messages.append(tool_message)

    return {
        "lint_report": lint_report_output,
        "agent_steps": agent_steps,
        "messages": tool_messages
    }

# ---- LangGraph Graph Definition ----
graph_builder = StateGraph(AgentState)
graph_builder.add_node("call_model", call_model)
graph_builder.add_node("call_tool", call_tool)
graph_builder.set_entry_point("call_model")

def should_call_tool(state: AgentState) -> str:
    """Determine if we should call a tool based on the last message."""
    last_message = state["messages"][-1]
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "call_tool"
    return "no_tool_call"

graph_builder.add_conditional_edges(
    "call_model",
    should_call_tool,
    {"call_tool": "call_tool", "no_tool_call": END}
)
graph_builder.add_edge("call_tool", END)
graph = graph_builder.compile()

# ---- ValidationAgent Class for Route Compatibility ----
class ValidationAgent:
    """ValidationAgent class that wraps the LangGraph functionality for route compatibility."""
    
    def __init__(self, client=None, agent_id="langgraph-validation", session_id="langgraph-session", 
                 instruction="Validate Ansible playbooks using LangGraph agent", config_loader=None, 
                 verbose_logging=False, timeout=120):
        self.client = client
        self.agent_id = agent_id
        self.session_id = session_id
        self.instruction = instruction
        self.config_loader = config_loader
        self.verbose_logging = verbose_logging
        self.timeout = timeout
        
        # Update LLM configuration if config_loader is provided
        if config_loader:
            try:
                llm_api_base, llm_model = get_llm_config(config_loader)
                if llm_api_base and llm_model:
                    # Recreate the global LLM instance with new config
                    global llm
                    llm = ChatOpenAI(
                        model=llm_model,
                        base_url=llm_api_base,
                        api_key="not-needed",
                        temperature=0.0,
                        request_timeout=60,
                        max_retries=1
                    )
                    # Rebind tools to the new LLM instance
                    global llm_with_tools
                    llm_with_tools = llm.bind_tools(tools)
                    print(f"Updated LLM config - Base URL: {llm_api_base}, Model: {llm_model}")
            except Exception as e:
                print(f"Warning: Could not update LLM config: {e}")
    
    def get_supported_profiles(self) -> List[str]:
        """Return supported validation profiles."""
        return ["basic", "production"]
    
    async def validate_playbook(self, playbook_content: str, profile: Optional[str] = None) -> dict:
        """Validate a playbook using the LangGraph agent."""
        try:
            # Try to use the LangGraph agent first
            initial_state = AgentState(
                playbook_code=playbook_content,
                lint_report=None,
                messages=[HumanMessage(content=playbook_content)],
                agent_steps=["Agent initialized with playbook code."]
            )
            
            final_state = await graph.ainvoke(initial_state)
            
            if final_state.get("lint_report"):
                lint_report = final_state["lint_report"]
                return {
                    "passed": lint_report.passed,
                    "summary": lint_report.summary,
                    "issues": lint_report.issues,
                    "issues_count": len(lint_report.issues),
                    "agent_steps": final_state["agent_steps"],
                    "agent_id": self.agent_id,
                    "elapsed_time": 0  # Could add timing if needed
                }
            else:
                return {
                    "passed": False,
                    "summary": "Agent completed but no lint report found",
                    "issues": ["No lint report generated"],
                    "issues_count": 1,
                    "agent_steps": final_state.get("agent_steps", []),
                    "agent_id": self.agent_id,
                    "elapsed_time": 0
                }
        except Exception as e:
            # Fallback to direct ansible-lint if LangGraph fails
            try:
                print(f"LangGraph agent failed: {e}, falling back to direct ansible-lint")
                result = run_ansible_lint(playbook_content)
                return {
                    "passed": result["passed"],
                    "summary": result["summary"],
                    "issues": result["issues"],
                    "issues_count": len(result["issues"]),
                    "agent_steps": ["Used direct ansible-lint fallback"],
                    "agent_id": self.agent_id,
                    "elapsed_time": 0
                }
            except Exception as fallback_error:
                return {
                    "passed": False,
                    "summary": f"Validation error: {str(e)} (fallback also failed: {str(fallback_error)})",
                    "issues": [str(e), str(fallback_error)],
                    "issues_count": 2,
                    "agent_steps": [f"Error: {str(e)}", f"Fallback error: {str(fallback_error)}"],
                    "agent_id": self.agent_id,
                    "elapsed_time": 0
                }
    
    def validate_playbook_stream(self, playbook_content: str, profile: Optional[str] = None) -> Generator[str, None, None]:
        """Stream validation results as Server-Sent Events."""
        import asyncio
        
        # Simple streaming implementation that works in sync context
        try:
            # Send start event
            yield f"data: {json.dumps({'type': 'start', 'message': 'Starting validation...'})}\n\n"
            
            # Run validation in a separate thread to avoid event loop conflicts
            import threading
            import concurrent.futures
            
            def run_validation_in_thread():
                try:
                    # Create a new event loop for this thread
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        return loop.run_until_complete(self.validate_playbook(playbook_content, profile))
                    finally:
                        loop.close()
                except Exception as e:
                    return {"error": str(e)}
            
            # Run validation in thread
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_validation_in_thread)
                result = future.result()
            
            # Send progress event
            yield f"data: {json.dumps({'type': 'progress', 'message': 'Validation completed'})}\n\n"
            
            # Send result event
            yield f"data: {json.dumps({'type': 'result', 'data': result})}\n\n"
            
            # Send end event
            yield f"data: {json.dumps({'type': 'end', 'message': 'Validation finished'})}\n\n"
            
        except Exception as e:
            # Send error event if something goes wrong
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
    
    async def validate_multiple_files(self, files: dict, profile: Optional[str] = None) -> dict:
        """Validate multiple files."""
        results = {}
        for filename, content in files.items():
            results[filename] = await self.validate_playbook(content, profile)
        return results
    
    async def validate_syntax(self, playbook_content: str) -> dict:
        """Validate syntax (same as regular validation for now)."""
        return await self.validate_playbook(playbook_content, "basic")
    
    async def production_validate(self, playbook_content: str) -> dict:
        """Production validation (same as regular validation for now)."""
        return await self.validate_playbook(playbook_content, "production")
    
    async def health_check(self) -> bool:
        """Health check for the agent."""
        try:
            # Test with a simple playbook
            test_playbook = """---
- name: Test playbook
  hosts: localhost
  tasks:
    - name: Echo message
      debug:
        msg: "Health check"
"""
            result = await self.validate_playbook(test_playbook, "basic")
            return result.get("passed", False)
        except Exception:
            return False
    
    def get_status(self) -> dict:
        """Get agent status."""
        return {
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "status": "ready",
            "type": "LangGraph Validation Agent"
        }

# ---- FastAPI Endpoints ----
@app.post("/api/lint-ansible-playbook", response_model=AgentResponse)
async def lint_ansible_playbook_agent(req: PlaybookRequest):
    """
    FastAPI endpoint to lint an Ansible playbook using the LangGraph agent.
    """
    initial_state = AgentState(
        playbook_code=req.code,
        lint_report=None,
        messages=[HumanMessage(content=req.code)],
        agent_steps=["Agent initialized with playbook code."]
    )
    
    try:
        print(f"Starting agent with playbook: {req.code[:100]}...")
        final_state = await graph.ainvoke(initial_state)
        
        if final_state.get("lint_report"):
            return AgentResponse(
                final_lint_report=final_state["lint_report"],
                agent_steps=final_state["agent_steps"]
            )
        else:
            raise HTTPException(
                status_code=500, 
                detail="Agent completed but no lint report found. Check if LLM endpoint is working."
            )
    
    except Exception as e:
        print(f"Agent execution error: {type(e).__name__}: {str(e)}")
        # More detailed error for debugging
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500, 
            detail=f"Agent execution failed: {type(e).__name__}: {str(e)}. Check server logs for details."
        )

@app.get("/api/test-llm")
async def test_llm():
    """Test LLM connectivity."""
    try:
        response = await llm.ainvoke([HumanMessage(content="Hello, are you working?")])
        return {"status": "success", "llm_response": response.content}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.get("/api/healthz")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}

@app.get("/")
async def root():
    """Root endpoint with basic info."""
    return {
        "message": "Ansible Lint Agent API", 
        "endpoints": {
            "health": "/api/healthz",
            "lint": "/api/lint-ansible-playbook"
        }
    }

# Add the streaming endpoint that the route expects
@app.post("/playbook/stream")
async def validate_playbook_stream_endpoint(req: PlaybookRequest):
    """Stream playbook validation results with timeout handling (event-stream)"""
    from fastapi.responses import StreamingResponse
    
    max_size = 50000
    if len(req.code) > max_size:
        def size_error_generator():
            yield f"data: {json.dumps({'type': 'error', 'error': f'Playbook too large ({len(req.code)} chars). Maximum: {max_size} characters'})}\n\n"
        return StreamingResponse(
            size_error_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )
    
    # Create a ValidationAgent instance for this request
    # Try to get config_loader from app state if available
    config_loader = None
    try:
        from config.config import ConfigLoader
        config_loader = ConfigLoader("config.yaml")
    except Exception as e:
        print(f"Warning: Could not load config for streaming endpoint: {e}")
    
    agent = ValidationAgent(
        client=None,
        agent_id="langgraph-validation",
        session_id="langgraph-session",
        instruction="Validate Ansible playbooks using LangGraph agent",
        config_loader=config_loader,
        verbose_logging=True,
        timeout=120
    )
    
    return StreamingResponse(
        agent.validate_playbook_stream(
            playbook_content=req.code,
            profile="basic",
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
