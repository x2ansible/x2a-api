import asyncio
import json
import time
from typing import Dict, Any, Optional, AsyncGenerator
import aiohttp

from config.config_loader import ConfigLoader
from config.agent_config import get_agent_instructions
from agents.chef_analysis.utils import create_correlation_id
from agents.chef_analysis.processor import extract_and_validate_analysis
from shared.exceptions import (
    LLMServiceError,
    TimeoutError,
    ConfigurationError,
    JSONParseError,
    CookbookAnalysisError
)
from shared.log_utils import create_chef_logger, ChefAnalysisLogger, step_printer

# Try to import LlamaStack client for logging only
try:
    from llama_stack_client import LlamaStackClient, Agent
    from llama_stack_client import AgentEventLogger
    LLAMASTACK_CLIENT_AVAILABLE = True
except ImportError:
    LLAMASTACK_CLIENT_AVAILABLE = False


class ChefAnalysisAgent:
    """
    Core Chef Analysis Agent using LlamaStack server API.
    Handles cookbook analysis with HTTP calls to LlamaStack server.
    No preprocessing—sends all cookbook files raw, relies on LLM instructions.
    """
    def __init__(self, config_loader: ConfigLoader):
        self.config_loader = config_loader
        self.base_url = self._get_base_url()
        self.model = self._get_model()
        self.timeout = self._get_timeout()
        self.max_tokens = self._get_max_tokens()
        self.instructions = get_agent_instructions("chef_analysis")

        self.logger = create_chef_logger("init")
        self.agent_id = None
        self.llama_client = None

        if LLAMASTACK_CLIENT_AVAILABLE:
            try:
                self.llama_client = LlamaStackClient(base_url=self.base_url)
                self.logger.info("LlamaStack client initialized for logging")
            except Exception as e:
                self.logger.warning(f"LlamaStack client init failed, logging features limited: {e}")

        self.logger.info(f"Chef Analysis Agent initialized")
        self.logger.info(f"Base URL: [bold cyan]{self.base_url}[/]")
        self.logger.info(f"Model: [bold green]{self.model}[/]")
        self.logger.info(f"Timeout: [yellow]{self.timeout}s[/]")
        self.logger.info(f"Max Tokens: [yellow]{self.max_tokens}[/]")

        if LLAMASTACK_CLIENT_AVAILABLE:
            try:
                self.agent_event_logger = AgentEventLogger()
                self.logger.info("LlamaStack event logging enabled")
            except Exception:
                self.agent_event_logger = None
                self.logger.warning("LlamaStack event logging not available")
        else:
            self.agent_event_logger = None
            self.logger.warning("LlamaStack client not available, basic logging only")

    def _get_base_url(self) -> str:
        base_url = self.config_loader.get_llamastack_base_url()
        if not base_url:
            raise ConfigurationError("LlamaStack base_url not configured")
        return base_url.rstrip('/')

    def _get_model(self) -> str:
        model = self.config_loader.get_llamastack_model()
        if not model:
            raise ConfigurationError("LlamaStack model not configured")
        return model

    def _get_timeout(self) -> float:
        return self.config_loader.get_value(
            "agents", "chef_analysis", "timeout",
            default=120.0
        )

    def _get_max_tokens(self) -> int:
        return self.config_loader.get_value(
            "agents", "chef_analysis", "max_tokens",
            default=4096
        )

    async def analyze_cookbook(
        self,
        cookbook_data: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze Chef cookbook and return structured analysis.
        No preprocessing—send all files to LLM as-is, relying on instructions.
        """
        correlation_id = correlation_id or create_correlation_id()
        logger = create_chef_logger(correlation_id)
        start_time = time.time()

        cookbook_name = cookbook_data.get("name", "unknown")
        files = cookbook_data.get("files", {})
        file_count = len(files)

        logger.log_cookbook_analysis_start(cookbook_name, file_count)

        try:
            logger.info("Joining all Chef cookbook files for LLM analysis (no preprocessing)")
            if not files:
                raise ValueError("Cookbook must contain at least one file")

            # Join files as plain string, with clear separators.
            llm_input = f"Cookbook: {cookbook_name}\n"
            for filename, content in files.items():
                llm_input += f"\n--- File: {filename} ---\n{content}\n"

            logger.debug("Cookbook joined for LLM", content_length=len(llm_input))

            logger.info("Using LlamaStack agent API for analysis (no preprocessing)")
            analysis_result = await self._analyze_with_server_api(llm_input, correlation_id, logger)

            total_time = time.time() - start_time
            logger.log_analysis_completion(analysis_result, total_time)

            return analysis_result

        except Exception as e:
            total_time = time.time() - start_time
            logger.error(f"Cookbook analysis failed after {total_time:.3f}s: {str(e)}")
            if isinstance(e, (LLMServiceError, TimeoutError, JSONParseError, CookbookAnalysisError)):
                raise
            else:
                raise CookbookAnalysisError(f"Analysis failed: {str(e)}")

    async def analyze_cookbook_stream(
        self,
        cookbook_data: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream cookbook analysis with real-time progress updates.
        Yields a progress message, then the final analysis.
        """
        correlation_id = correlation_id or create_correlation_id()
        logger = create_chef_logger(correlation_id)

        try:
            yield {
                "type": "progress",
                "status": "processing",
                "message": "Chef cookbook analysis started"
            }
            result = await self.analyze_cookbook(cookbook_data, correlation_id)
            yield {
                "type": "final_analysis",
                "data": result,
                "correlation_id": correlation_id
            }
        except Exception as e:
            yield {
                "type": "error",
                "error": str(e),
                "correlation_id": correlation_id
            }

    async def _analyze_with_server_api(self, llm_input: str, correlation_id: str, logger: ChefAnalysisLogger) -> Dict[str, Any]:
        logger.info("Using LlamaStack server agent API")
        try:
            agent_id = await self._get_or_create_agent(logger)
            session_id = await self._create_agent_session(agent_id, correlation_id, logger)
            analysis_result = await self._send_agent_turn(agent_id, session_id, llm_input, logger)
            return analysis_result
        except Exception as e:
            logger.error(f"LlamaStack agent API failed: {str(e)}")
            raise LLMServiceError(f"Analysis failed: {str(e)}")

    async def _get_or_create_agent(self, logger: ChefAnalysisLogger) -> str:
        logger.info("Creating new chef analysis agent with correct model")
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                agent_payload = {
                    "agent_config": {
                        "model": self.model,
                        "instructions": self.instructions,
                        "sampling_params": {
                            "strategy": {
                                "type": "top_p",
                                "temperature": 0.1,
                                "top_p": 0.95
                            },
                            "max_tokens": self.max_tokens,
                            "repetition_penalty": 1,
                            "stop": None
                        },
                        "input_shields": [],
                        "output_shields": [],
                        "toolgroups": [],
                        "client_tools": [],
                        "tool_config": {
                            "tool_choice": "auto",
                            "tool_prompt_format": None,
                            "system_message_behavior": "append"
                        },
                        "max_infer_iters": 10,
                        "name": "chef_analysis_agent",
                        "enable_session_persistence": True,
                        "response_format": None
                    }
                }

                logger.debug(f"Creating agent with model: {self.model}")

                async with session.post(f"{self.base_url}/v1/agents", json=agent_payload) as response:
                    if response.status == 200:
                        agent_result = await response.json()
                        agent_id = agent_result.get("agent_id")
                        logger.info(f"Created new chef agent with correct model: {agent_id}")
                        return agent_id
                    else:
                        error_text = await response.text()
                        raise LLMServiceError(f"Failed to create agent: {response.status} - {error_text}")

        except Exception as e:
            logger.error(f"Failed to create agent: {str(e)}")
            raise LLMServiceError(f"Agent creation failed: {str(e)}")

    async def _create_agent_session(self, agent_id: str, correlation_id: str, logger: ChefAnalysisLogger) -> str:
        session_payload = {
            "session_name": f"chef_analysis_{correlation_id}"
        }
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                async with session.post(f"{self.base_url}/v1/agents/{agent_id}/session", json=session_payload) as response:
                    if response.status == 200:
                        session_result = await response.json()
                        session_id = session_result.get("session_id")
                        logger.info(f"Created session: {session_id}")
                        self.agent_id = agent_id
                        return session_id
                    else:
                        error_text = await response.text()
                        raise LLMServiceError(f"Failed to create session: {response.status} - {error_text}")
        except Exception as e:
            logger.error(f"Failed to create session: {str(e)}")
            raise LLMServiceError(f"Session creation failed: {str(e)}")

    async def _send_agent_turn(self, agent_id: str, session_id: str, llm_input: str, logger: ChefAnalysisLogger) -> Dict[str, Any]:
        turn_payload = {
            "messages": [
                {"role": "user", "content": llm_input}
            ],
            "stream": True
        }
        logger.debug(f"Sending streaming turn to agent {agent_id}, session {session_id}")

        try:
            accumulated_content = ""
            chunk_count = 0

            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(f"{self.base_url}/v1/agents/{agent_id}/session/{session_id}/turn", json=turn_payload) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise LLMServiceError(f"Agent turn failed: {response.status} - {error_text}")

                    logger.debug("Started processing streaming response")

                    async for line in response.content:
                        if not line:
                            continue
                        chunk_count += 1
                        try:
                            line_text = line.decode('utf-8').strip()
                            if not line_text:
                                continue
                            logger.debug(f"Raw chunk {chunk_count}: {line_text[:200]}...")
                            if line_text.startswith('data: '):
                                line_text = line_text[6:]
                            if not line_text or line_text == '[DONE]':
                                continue
                            chunk = json.loads(line_text)
                            logger.debug(f"Parsed chunk {chunk_count} structure: {list(chunk.keys())}")
                            if chunk_count <= 3:
                                logger.debug(f"Full chunk {chunk_count}: {json.dumps(chunk, indent=2)[:500]}...")
                            content = self._extract_content_from_chunk(chunk, logger)
                            if content:
                                accumulated_content += content
                                logger.debug(f"Added content, total length now: {len(accumulated_content)}")
                        except json.JSONDecodeError as e:
                            logger.debug(f"JSON decode error in chunk {chunk_count}: {str(e)}, raw: {line_text[:100]}")
                            continue
                        except Exception as e:
                            logger.debug(f"Error processing chunk {chunk_count}: {str(e)}")
                            continue

                    logger.debug(f"Finished processing {chunk_count} chunks, accumulated content length: {len(accumulated_content)}")
                    if accumulated_content:
                        await self._log_analysis_with_client(accumulated_content, logger)
                        logger.info("Parsing LLM response from streaming turn")
                        analysis_result = extract_and_validate_analysis(accumulated_content, logger.correlation_id)
                        return analysis_result
                    else:
                        logger.warning(f"No content received from streaming agent turn after processing {chunk_count} chunks")
                        raise LLMServiceError("No content received from streaming agent turn")

        except Exception as e:
            logger.error(f"Failed to send streaming agent turn: {str(e)}")
            raise LLMServiceError(f"Streaming agent turn failed: {str(e)}")

    def _extract_content_from_chunk(self, chunk: dict, logger: ChefAnalysisLogger) -> Optional[str]:
        try:
            if "error" in chunk:
                error_msg = chunk["error"].get("message", "Unknown error")
                logger.error(f"LlamaStack server error: {error_msg}")
                raise LLMServiceError(f"LlamaStack error: {error_msg}")
            if "event" in chunk:
                event = chunk["event"]
                if "payload" in event:
                    payload = event["payload"]
                    if payload.get("event_type") == "step_complete" and payload.get("step_type") == "inference":
                        if "step_details" in payload:
                            step_details = payload["step_details"]
                            if "model_response" in step_details:
                                model_resp = step_details["model_response"]
                                content = model_resp.get("content", "")
                                if content:
                                    return content
                    if "turn" in payload:
                        turn = payload["turn"]
                        if "output_message" in turn:
                            msg = turn["output_message"]
                            content = msg.get("content", "")
                            if content:
                                return content
                    if "delta" in payload:
                        delta = payload["delta"]
                        text = delta.get("text", "") or delta.get("content", "")
                        if text:
                            return text
                    if "completion_message" in payload:
                        completion = payload["completion_message"]
                        if isinstance(completion, dict) and "content" in completion:
                            content = completion["content"]
                            if content:
                                return content
            if "completion_message" in chunk:
                completion = chunk["completion_message"]
                if isinstance(completion, dict) and "content" in completion:
                    content = completion["content"]
                    if content:
                        return content
            if "delta" in chunk:
                delta = chunk["delta"]
                if isinstance(delta, dict):
                    content = delta.get("content", "") or delta.get("text", "")
                    if content:
                        return content
            if "content" in chunk:
                content = chunk["content"]
                if isinstance(content, str) and content.strip():
                    return content
            return None
        except Exception as e:
            logger.debug(f"Error extracting content from chunk: {str(e)}")
            return None

    async def _log_analysis_with_client(self, content: str, logger: ChefAnalysisLogger) -> None:
        if not self.llama_client:
            logger.debug("LlamaStack client not available for enhanced logging")
            return
        try:
            agent = Agent(
                client=self.llama_client,
                model=self.model,
                instructions="Logging session for analysis tracking",
                tools=[]
            )
            session_id = agent.create_session(f"logging_{logger.correlation_id}")
            logger.debug(f"Created logging session: {session_id}")
            if self.agent_event_logger:
                self.agent_event_logger.log_event("analysis_completed", {
                    "session_id": session_id,
                    "content_length": len(content),
                    "correlation_id": logger.correlation_id
                })
        except Exception as e:
            logger.debug(f"Enhanced logging failed (non-critical): {str(e)}")


def create_chef_analysis_agent(config_loader: ConfigLoader) -> ChefAnalysisAgent:
    """Factory function to create Chef Analysis Agent."""
    return ChefAnalysisAgent(config_loader=config_loader)
