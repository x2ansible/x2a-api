import os
import tempfile
import subprocess
import json
import asyncio
from typing import List, Optional, TypedDict, Annotated, Generator, Dict, Any
import logging

from langchain_core.messages import BaseMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langchain_core.prompts import ChatPromptTemplate

logger = logging.getLogger(__name__)

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
            logger.warning(f"Could not get LLM config from config_loader: {e}")
    
    # Fallback to environment variables
    base_url = os.getenv("LLM_API_BASE", "http://localhost:8000/v1")
    model = os.getenv("LLM_MODEL", "meta-llama/Llama-3.1-8B-Instruct")
    return base_url, model

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

# ---- LangGraph Agent State ----
class AgentState(TypedDict):
    playbook_code: str
    lint_report: Optional[Dict]
    messages: Annotated[List[BaseMessage], lambda x, y: x + y]
    agent_steps: Annotated[List[str], lambda x, y: x + y]

# ---- Pure LangGraph ValidationAgent ----
class ValidationAgent:
    """Pure LangGraph ValidationAgent - no fallbacks, clean agent design."""
    
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
        
        # Initialize LLM and graph
        self._initialize_llm()
        self._build_graph()
        
        if verbose_logging:
            logger.info(f"Pure LangGraph ValidationAgent initialized - Agent ID: {self.agent_id}")
    
    def _initialize_llm(self):
        """Initialize LLM with vLLM-compatible configuration."""
        try:
            llm_api_base, llm_model = get_llm_config(self.config_loader)
            
            if self.verbose_logging:
                logger.info(f"Connecting to LLM at: {llm_api_base}")
                logger.info(f"Using model: {llm_model}")
            
            # Use httpx.Client for proper timeout handling
            import httpx
            http_client = httpx.Client(timeout=120.0)
            
            # Optimized settings for LLM interaction
            self.llm = ChatOpenAI(
                model=llm_model,
                base_url=llm_api_base,
                api_key="not-needed",
                temperature=0.0,
                request_timeout=120,
                max_retries=2,
                timeout=120,
                http_client=http_client,
                model_kwargs={
                    "max_tokens": 500,
                    "top_p": 0.95,
                    "frequency_penalty": 0.1,
                    "stop": ["<|end|>", "<|eot_id|>", "\n\n\n"],
                }
            )
            
            # Bind tools to the LLM
            tools = [run_ansible_lint]
            self.llm_with_tools = self.llm.bind_tools(tools)
            
            if self.verbose_logging:
                logger.info("LLM initialized successfully")
                
        except Exception as e:
            logger.error(f"Failed to initialize LLM: {e}")
            raise RuntimeError(f"LLM initialization failed: {e}")
    
    def _build_graph(self):
        """Build the LangGraph workflow."""
        try:
            graph_builder = StateGraph(AgentState)
            graph_builder.add_node("call_model", self._call_model)
            graph_builder.add_node("call_tool", self._call_tool)
            graph_builder.set_entry_point("call_model")
            
            graph_builder.add_conditional_edges(
                "call_model",
                self._should_call_tool,
                {"call_tool": "call_tool", "no_tool_call": END}
            )
            graph_builder.add_edge("call_tool", END)
            
            self.graph = graph_builder.compile()
            
            if self.verbose_logging:
                logger.info("LangGraph workflow built successfully")
                
        except Exception as e:
            logger.error(f"Failed to build LangGraph: {e}")
            raise RuntimeError(f"Graph building failed: {e}")
    
    async def _call_model(self, state: AgentState):
        """Node that calls the LLM."""
        messages = state["messages"]
        agent_steps = state.get("agent_steps", [])

        prompt_template = ChatPromptTemplate.from_messages([
            ("system", "You are an expert Ansible linting assistant. Your ONLY task is to lint Ansible playbooks using the `run_ansible_lint` tool. When given a playbook, you MUST use this tool to lint it. CRITICAL: Pass the EXACT playbook content as the 'playbook_code' parameter. Do NOT add any wrapper text like 'content=' or quotes around the playbook YAML content."),
            ("human", "Lint this Ansible playbook:\n\n{playbook_content}\n\nCall the run_ansible_lint tool with playbook_code parameter set to the exact YAML content above.")
        ])

        full_prompt = prompt_template.format_messages(
            playbook_content=state["playbook_code"]
        )

        response = await self.llm_with_tools.ainvoke(full_prompt)
        agent_steps.append(f"LLM decided: {getattr(response, 'content', '') or 'tool_calls'}")
        return {"messages": [response], "agent_steps": agent_steps}

    async def _call_tool(self, state: AgentState):
        """Node that executes the tool."""
        messages = state["messages"]
        agent_steps = state.get("agent_steps", [])
        last_message = messages[-1]

        if not hasattr(last_message, 'tool_calls') or not last_message.tool_calls:
            agent_steps.append("No tool calls found in the last LLM message.")
            lint_report_output = {
                "passed": False,
                "summary": "LLM did not attempt to call the 'run_ansible_lint' tool as expected.",
                "issues": ["LLM did not trigger the expected tool."]
            }
            return {"lint_report": lint_report_output, "agent_steps": agent_steps}

        tool_messages = []
        lint_report_output = None

        for tool_call in last_message.tool_calls:
            tool_name = tool_call.get("name")
            tool_args = tool_call.get("args", {})
            tool_call_id = tool_call.get("id")
            
            if tool_name == "run_ansible_lint":
                agent_steps.append(f"Calling tool: {tool_name} with input: {tool_args}")
                
                # Execute the tool directly
                raw_tool_output = run_ansible_lint.invoke(tool_args)
                
                if isinstance(raw_tool_output, dict) and all(k in raw_tool_output for k in ["passed", "summary", "issues"]):
                    lint_report_output = raw_tool_output
                    agent_steps.append(f"Tool output: Passed={lint_report_output['passed']}")
                    
                    tool_message = ToolMessage(
                        content=f"Linting completed. Passed: {lint_report_output['passed']}. Summary: {lint_report_output['summary']}",
                        tool_call_id=tool_call_id
                    )
                    tool_messages.append(tool_message)
                else:
                    # Tool execution failed - let it bubble up as an error
                    raise RuntimeError(f"Tool execution failed: Unexpected output format: {raw_tool_output}")
            else:
                agent_steps.append(f"Unexpected tool call: {tool_name}")
                raise RuntimeError(f"LLM called an unexpected tool: {tool_name}")

        return {
            "lint_report": lint_report_output,
            "agent_steps": agent_steps,
            "messages": tool_messages
        }

    def _should_call_tool(self, state: AgentState) -> str:
        """Determine if we should call a tool based on the last message."""
        last_message = state["messages"][-1]
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return "call_tool"
        return "no_tool_call"
    
    def get_supported_profiles(self) -> List[str]:
        """Return supported validation profiles."""
        return ["basic", "production"]
    
    async def validate_playbook(self, playbook_content: str, profile: Optional[str] = None) -> dict:
        """Validate a playbook using the pure LangGraph agent."""
        initial_state = AgentState(
            playbook_code=playbook_content,
            lint_report=None,
            messages=[HumanMessage(content=playbook_content)],
            agent_steps=["Agent initialized with playbook code."]
        )
        
        # Execute with timeout - let errors bubble up naturally
        final_state = await asyncio.wait_for(
            self.graph.ainvoke(initial_state),
            timeout=self.timeout
        )
        
        if final_state.get("lint_report"):
            lint_report = final_state["lint_report"]
            return {
                "passed": lint_report["passed"],
                "summary": lint_report["summary"],
                "issues": lint_report["issues"],
                "issues_count": len(lint_report["issues"]),
                "formatted_issues": lint_report["summary"],
                "agent_steps": final_state["agent_steps"],
                "agent_id": self.agent_id,
                "elapsed_time": 0,
                "timeout": False
            }
        else:
            raise RuntimeError("Agent completed but no lint report found")
    
    def validate_playbook_stream(self, playbook_content: str, profile: Optional[str] = None) -> Generator[str, None, None]:
        """Stream validation results as Server-Sent Events."""
        try:
            yield f"data: {json.dumps({'type': 'start', 'message': 'Starting LangGraph validation...'})}\n\n"
            
            async def run_async_validation():
                return await self.validate_playbook(playbook_content, profile)
            
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            lambda: asyncio.run(run_async_validation())
                        )
                        result = future.result(timeout=self.timeout + 10)
                else:
                    result = loop.run_until_complete(run_async_validation())
            except RuntimeError:
                result = asyncio.run(run_async_validation())
            
            yield f"data: {json.dumps({'type': 'progress', 'message': 'LangGraph validation completed'})}\n\n"
            yield f"data: {json.dumps({'type': 'result', 'data': result})}\n\n"
            yield f"data: {json.dumps({'type': 'end', 'message': 'Validation finished'})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
    
    async def validate_multiple_files(self, files: dict, profile: Optional[str] = None) -> dict:
        """Validate multiple files."""
        results = {}
        for filename, content in files.items():
            results[filename] = await self.validate_playbook(content, profile)
        return results
    
    async def validate_syntax(self, playbook_content: str) -> dict:
        """Validate syntax."""
        return await self.validate_playbook(playbook_content, "basic")
    
    async def production_validate(self, playbook_content: str) -> dict:
        """Production validation."""
        return await self.validate_playbook(playbook_content, "production")
    
    async def health_check(self) -> bool:
        """Health check for the agent."""
        test_playbook = """---
- name: Test playbook
  hosts: localhost
  tasks:
    - name: Echo message
      debug:
        msg: "Health check"
"""
        try:
            result = await self.validate_playbook(test_playbook, "basic")
            return result.get("passed", False)
        except Exception as e:
            if self.verbose_logging:
                logger.error(f"Health check failed: {e}")
            return False
    
    def get_status(self) -> dict:
        """Get agent status."""
        return {
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "status": "ready",
            "type": "Pure LangGraph Validation Agent"
        }

# Production-ready ValidationAgent - no test functions needed