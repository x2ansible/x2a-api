import os
import tempfile
import subprocess
import traceback
import json
import logging
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any

from langgraph.graph import StateGraph, END

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = FastAPI()

class PlaybookRequest(BaseModel):
    playbook_content: str

class LintState(BaseModel):
    code: str
    lint_summary: str = ""
    passed: bool = False
    issues: List[str] = []

def run_ansible_lint_subprocess(playbook_code: str) -> dict:
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".yml") as f:
        f.write(playbook_code)
        fname = f.name
    try:
        result = subprocess.run(
            ["ansible-lint", fname],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )
        output = result.stdout
        passed = result.returncode == 0
        summary = output.strip() if not passed else "No issues found."
        issues = output.strip().splitlines() if not passed else []
        return {"passed": passed, "summary": summary, "issues": issues}
    finally:
        try:
            os.remove(fname)
        except Exception:
            pass

def lint_node(state: LintState) -> LintState:
    logging.info("[AGENT] Running ansible-lint tool as agent node.")
    lint_result = run_ansible_lint_subprocess(state.code)
    state.lint_summary = lint_result["summary"]
    state.passed = lint_result["passed"]
    state.issues = lint_result["issues"]
    return state

graph = StateGraph(state_schema=LintState)
graph.add_node("lint", lint_node)
graph.set_entry_point("lint")
graph.add_edge("lint", END)
compiled_graph = graph.compile()

@app.post("/api/validate/playbook/stream")
async def validate_playbook_stream(request: PlaybookRequest):
    async def event_stream():
        try:
            initial_state = LintState(code=request.playbook_content)
            # NOTE: For old LangGraph, don't use return_type!
            final_state = await compiled_graph.ainvoke(initial_state)
            # final_state is a dict, not a LintState object
            yield f"data: {json.dumps({'type': 'progress', 'message': 'Lint completed', 'lint_summary': final_state.get('lint_summary', '')[:150]})}\n\n"
            result = {
                "passed": final_state.get('passed', False),
                "lint_summary": final_state.get('lint_summary', ''),
                "issues": final_state.get('issues', []),
                "code": final_state.get('code', ''),
            }
            yield f"data: {json.dumps({'type': 'final_result', 'data': result})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            tb = traceback.format_exc()
            yield f"data: {json.dumps({'type': 'error', 'message': str(e), 'traceback': tb})}\n\n"
    return StreamingResponse(event_stream(), media_type="text/event-stream")
