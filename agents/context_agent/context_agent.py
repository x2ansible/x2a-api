import time
from typing import Dict, Any, Optional, AsyncGenerator
import logging
import uuid

from agents.agent import AgentManager  # optional if you use it elsewhere
from config.config import ConfigLoader
from llama_stack_client import Agent, LlamaStackClient
from llama_stack_client.types import UserMessage

logger = logging.getLogger("ContextAgent")

class ContextAgent:
    def __init__(self, client: Any, model: str, instructions: str, vector_db_id: str, timeout: int = 60):
        self.timeout = timeout
        self.client = client
        self.model = model
        self.instructions = instructions
        self.vector_db_id = vector_db_id
        self.logger = logger
        self._initialize_agent()
        self.logger.info(f"Context Agent initialized | Model: {self.model} | Vector DB: {self.vector_db_id}")

    def _initialize_agent(self):
        try:
            self.agent = Agent(
                client=self.client,
                model=self.model,
                instructions=self.instructions,
                sampling_params={"strategy": {"type": "greedy"}, "max_tokens": 4096},
                tools=[{
                    "name": "builtin::rag",
                    "args": {"vector_db_ids": [self.vector_db_id]},
                }],
            )
            self.logger.info("Context Agent: LlamaStack Agent initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize ContextAgent: {e}")
            raise

    async def query_context(
        self,
        code: str,
        top_k: int = 5,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        correlation_id = correlation_id or str(uuid.uuid4())
        logger = self.logger
        start_time = time.time()

        logger.info(f"📬 Sending query to ContextAgent: {repr(code)[:200]}")

        try:
            session_id = self.agent.create_session(f"context_session_{correlation_id}")
            turn = self.agent.create_turn(
                session_id=session_id,
                messages=[UserMessage(role="user", content=code)],
                stream=False
            )
            steps = getattr(turn, "steps", [])
            # Parse out meaningful context chunks from tool responses
            context_chunks = []
            for step in steps:
                for tool_response in getattr(step, "tool_responses", []):
                    content = getattr(tool_response, "content", None)
                    if isinstance(content, list):
                        for item in content:
                            if hasattr(item, "text"):
                                text = item.text.strip()
                                if (
                                    text
                                    and not text.startswith((
                                        "knowledge_search tool found",
                                        "BEGIN", "END", "The above results"
                                    ))
                                ):
                                    context_chunks.append(text)
                    elif isinstance(content, str):
                        text = content.strip()
                        if text:
                            context_chunks.append(text)
            # As a fallback, append top-level LLM output if nothing else
            top_content = getattr(turn, "output_message", None)
            if top_content and hasattr(top_content, "content"):
                output = top_content.content.strip()
                if output and not context_chunks:
                    context_chunks.append(output)
            context_list = [{"text": chunk} for chunk in context_chunks if chunk]
            logger.info(f"ContextAgent returned {len(context_list)} chunks")
            total_time = time.time() - start_time
            return {
                "context": context_list,
                "steps": steps,
                "elapsed_time": total_time,
                "correlation_id": correlation_id
            }
        except Exception as e:
            total_time = time.time() - start_time
            logger.error(f"Context query failed after {total_time:.3f}s: {str(e)}")
            raise

    async def query_context_stream(
        self,
        code: str,
        top_k: int = 5,
        correlation_id: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        correlation_id = correlation_id or str(uuid.uuid4())
        try:
            yield {
                "type": "progress",
                "status": "processing",
                "message": "Context search started"
            }
            result = await self.query_context(code, top_k, correlation_id)
            yield {
                "type": "final_context",
                "data": result,
                "correlation_id": correlation_id
            }
        except Exception as e:
            yield {
                "type": "error",
                "error": str(e),
                "correlation_id": correlation_id
            }

def create_context_agent(config_loader: ConfigLoader) -> ContextAgent:
    base_url = config_loader.get_llamastack_base_url()
    agents_config = config_loader.get_agents_config()
    agent_block = next((a for a in agents_config if a["name"] == "context"), None)
    if not agent_block:
        raise RuntimeError("No agent config found for 'context' in config.yaml")
    model = agent_block["model"]
    instructions = agent_block["instructions"]
    vector_db_id = None
    for tool in agent_block.get("tools", []):
        if tool["name"] == "builtin::rag":
            vector_db_id = tool["args"]["vector_db_ids"][0]
    if not (base_url and model and instructions and vector_db_id):
        raise RuntimeError("Missing required config for context agent")
    client = LlamaStackClient(base_url=base_url.rstrip("/"))
    return ContextAgent(client, model, instructions, vector_db_id)
