import time
from typing import Dict, Any, Optional, AsyncGenerator
import logging
import uuid

from llama_stack_client import LlamaStackClient
from llama_stack_client.types import UserMessage

logger = logging.getLogger("ContextAgent")

class ContextAgent:
    """
    ContextAgent following Meta's pattern - Direct LlamaStack API calls only
    """
    def __init__(self, client: LlamaStackClient, agent_id: str, session_id: str, vector_db_id: str, timeout: int = 60):
        self.client = client
        self.agent_id = agent_id
        self.session_id = session_id  # Default session
        self.vector_db_id = vector_db_id
        self.timeout = timeout
        self.logger = logger
        self.logger.info(f"🔍 ContextAgent initialized with agent_id: {agent_id}, vector_db: {vector_db_id}")

    def create_new_session(self, correlation_id: str) -> str:
        """Create a new session for this specific context query"""
        try:
            response = self.client.agents.session.create(
                agent_id=self.agent_id,
                session_name=f"context-query-{correlation_id}-{uuid.uuid4()}",
            )
            session_id = response.session_id
            self.logger.info(f" Created new session: {session_id} for correlation: {correlation_id}")
            return session_id
        except Exception as e:
            self.logger.error(f" Failed to create session: {e}")
            # Fallback to default session
            self.logger.info(f"↩️  Falling back to default session: {self.session_id}")
            return self.session_id

    async def query_context(
        self,
        code: str,
        top_k: int = 5,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        correlation_id = correlation_id or str(uuid.uuid4())
        start_time = time.time()

        self.logger.info(f"📬 Sending query to ContextAgent: {repr(code)[:200]}")

        try:
            # Create dedicated session for this query
            query_session_id = self.create_new_session(correlation_id)

            # Direct API call following Meta's pattern
            messages = [UserMessage(role="user", content=code)]
            
            generator = self.client.agents.turn.create(
                agent_id=self.agent_id,
                session_id=query_session_id,
                messages=messages,
                stream=True,
            )
            
            # Process streaming response
            turn = None
            for chunk in generator:
                event = chunk.event
                event_type = event.payload.event_type
                if event_type == "turn_complete":
                    turn = event.payload.turn
                    break
            
            if not turn:
                self.logger.error(" No turn completed in response")
                raise RuntimeError("No turn completed in context query")

            # Log steps for debugging
            self.logger.info(f" Turn completed with {len(turn.steps)} steps")
            for i, step in enumerate(turn.steps):
                self.logger.info(f"📋 Step {i+1}: {step.step_type}")

            # Extract context chunks from tool responses
            context_chunks = self._extract_context_from_steps(turn.steps)
            
            # Fallback to main output if no tool responses
            if not context_chunks:
                output = turn.output_message.content.strip()
                if output:
                    context_chunks.append(output)

            context_list = [{"text": chunk} for chunk in context_chunks if chunk]
            self.logger.info(f"🔍 ContextAgent returned {len(context_list)} chunks")
            
            total_time = time.time() - start_time
            return {
                "context": context_list,
                "steps": turn.steps,
                "elapsed_time": total_time,
                "correlation_id": correlation_id,
                "session_info": {
                    "agent_id": self.agent_id,
                    "session_id": query_session_id
                }
            }
            
        except Exception as e:
            total_time = time.time() - start_time
            self.logger.error(f" Context query failed after {total_time:.3f}s: {str(e)}")
            raise

    def _extract_context_from_steps(self, steps) -> list:
        """Extract meaningful context chunks from turn steps"""
        context_chunks = []
        
        for step in steps:
            # Handle tool responses
            if hasattr(step, 'tool_responses'):
                for tool_response in step.tool_responses:
                    content = getattr(tool_response, "content", None)
                    
                    if isinstance(content, list):
                        for item in content:
                            if hasattr(item, "text"):
                                text = item.text.strip()
                                if self._is_valid_context_text(text):
                                    context_chunks.append(text)
                    elif isinstance(content, str):
                        text = content.strip()
                        if self._is_valid_context_text(text):
                            context_chunks.append(text)
            
            # Handle memory retrieval steps
            if hasattr(step, 'inserted_context') and step.inserted_context:
                text = step.inserted_context.strip()
                if self._is_valid_context_text(text):
                    context_chunks.append(text)
        
        return context_chunks

    def _is_valid_context_text(self, text: str) -> bool:
        """Filter out non-useful context text"""
        if not text:
            return False
        
        # Filter out common tool artifacts
        skip_patterns = [
            "knowledge_search tool found",
            "BEGIN", "END", "The above results",
            "Retrieved context from vector dbs",
            "START-RETRIEVED-CONTEXT",
            "END-RETRIEVED-CONTEXT"
        ]
        
        return not any(text.startswith(pattern) for pattern in skip_patterns)

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
                "message": "🔍 Context search started",
                "agent_info": {
                    "agent_id": self.agent_id,
                    "correlation_id": correlation_id
                }
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

    def get_status(self) -> Dict[str, Any]:
        """Get current status of the context agent"""
        return {
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "vector_db_id": self.vector_db_id,
            "client_base_url": self.client.base_url,
            "timeout": self.timeout,
            "status": "ready",
            "pattern": "Meta Direct API"
        }

    async def health_check(self) -> bool:
        """Perform a health check on the context agent"""
        try:
            messages = [UserMessage(role="user", content="Health check")]
            generator = self.client.agents.turn.create(
                agent_id=self.agent_id,
                session_id=self.session_id,
                messages=messages,
                stream=True,
            )
            
            # Just check if we can create a turn without errors
            for chunk in generator:
                break  # Just need first chunk to verify connection works
            
            self.logger.info(" Context agent health check passed")
            return True
        except Exception as e:
            self.logger.error(f" Context agent health check failed: {e}")
            return False