import asyncio
import json

async def stream_agent_events(agent, agent_method_name, input_data, session_info=None):
    """
    Generic event generator for agent streaming analysis.
    Yields events (log, progress, final_analysis, error) as SSE.
    """
    agent_method = getattr(agent, agent_method_name)
    try:
        async for event in agent_method(input_data, **(session_info or {})):
            yield f"data: {json.dumps(event)}\n\n"
            await asyncio.sleep(0.1)
    except Exception as e:
        error_event = {
            "type": "error",
            "error": str(e),
        }
        yield f"data: {json.dumps(error_event)}\n\n"
