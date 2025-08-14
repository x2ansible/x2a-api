import uuid
import json
from typing import Dict, Any, Generator
from llama_stack_client import LlamaStackClient, Agent, AgentEventLogger
from shared.log_utils import create_correlation_logger

class ContextAgent:
    """
    Agentic RAG ContextAgent - Creates own Agent instance with defined instructions and tools
    """
    def __init__(self, client: LlamaStackClient, vector_db_id: str, model: str = "meta-llama/Llama-3.1-8B-Instruct"):
        self.client = client
        self.vector_db_id = vector_db_id
        self.model = model
        
        # Use shared logging utilities with correlation ID
        self.logger = create_correlation_logger("context-agent", "context-agent-init")

        # Create own Agent instance following agentic RAG pattern
        self.agent = self._create_agent()
        
        self.logger.info("ContextAgent initialized with own Agent instance")
        self.logger.info(f"Vector DB: {self.vector_db_id}")
        self.logger.info(f"Model: {self.model}")

    def _create_agent(self) -> Agent:
        """Create RAG agent with knowledge search capabilities - following agentic RAG pattern."""
        instructions = """You are a RAG retrieval assistant specializing in Infrastructure as Code patterns.

MANDATORY WORKFLOW - FOLLOW EXACTLY:
1. IMMEDIATELY call the knowledge_search tool with the user's exact input as the query parameter.
2. WAIT for the complete tool response with retrieved content.
3. If the tool returns relevant content, return ONLY the retrieved content without any commentary.
4. If no relevant content is found, respond: "No relevant patterns found for this input."

CRITICAL RULES:
- NEVER respond without first calling the knowledge_search tool
- NEVER generate answers from your own knowledge
- ALWAYS use the user's input as the search query
- The knowledge_search tool will access the Infrastructure as Code vector database
- Return ONLY the raw retrieved content, NO introduction text, NO conclusion text
- DO NOT add phrases like "Based on the knowledge_search tool results" or "These patterns can be used"
- Return the pure retrieved patterns/content directly"""

        tools = [
            {
                "name": "builtin::rag/knowledge_search",
                "args": {
                    "vector_db_ids": [self.vector_db_id],
                    "top_k": 3,  # Reduced from 5 to 3 for stability
                },
            }
        ]

        agent = Agent(
            client=self.client,
            model=self.model,
            instructions=instructions,
            tools=tools,
        )
        
        self.logger.info(f"Created RAG agent with model: {self.model}")
        return agent

    def _sse(self, payload: Dict[str, Any]) -> bytes:
        """Server-sent events formatter for streaming responses"""
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")

    def _extract_response_content(self, response) -> str:
        """Extract text content from agent response."""
        if hasattr(response, 'output_message'):
            output_msg = response.output_message
            if hasattr(output_msg, 'content') and output_msg.content:
                return output_msg.content
            elif isinstance(output_msg, str):
                return output_msg
        
        if hasattr(response, 'content') and response.content:
            return response.content
        
        if hasattr(response, 'message'):
            msg = response.message
            if hasattr(msg, 'content'):
                return msg.content
            elif isinstance(msg, str):
                return msg
        
        if isinstance(response, str):
            return response
        
        return str(response) if response else "No response received"

    def create_new_session(self, correlation_id: str) -> str:
        """Create new session for context queries - using agent instance"""
        try:
            session_name = f"context-query-{correlation_id}-{uuid.uuid4()}"
            session_id = self.agent.create_session(session_name)
            # Create logger with correlation ID for this session
            session_logger = create_correlation_logger("context-agent", correlation_id)
            session_logger.info(f"Created context session: {session_id} for correlation: {correlation_id}")
            return session_id
        except Exception as e:
            self.logger.error(f"Failed to create session: {e}")
            # Create a fallback session
            fallback_session_id = self.agent.create_session(f"fallback-{uuid.uuid4()}")
            self.logger.info(f"Using fallback session: {fallback_session_id}")
            return fallback_session_id

    async def query_context(self, code, top_k=5, correlation_id=None):
        """Simplified context query using agentic RAG pattern"""
        correlation_id = correlation_id or str(uuid.uuid4())
        query_logger = create_correlation_logger("context-agent", correlation_id)
        
        query_logger.info(f"Context query: {repr(code)[:100]}...")
        
        try:
            # Use agentic approach - let agent handle the RAG query
            session_id = self.agent.create_session(f"context-{uuid.uuid4()}")
            
            response = self.agent.create_turn(
                messages=[{"role": "user", "content": code}],
                session_id=session_id,
                stream=False
            )
            
            # Extract response content
            response_text = self._extract_response_content(response)
            
            # For UI compatibility, return context chunks format
            context_chunks = []
            if response_text and response_text.strip():
                # Split response into chunks for UI compatibility
                chunks = [chunk.strip() for chunk in response_text.split('\n\n') if chunk.strip()]
                context_chunks = [{"text": chunk} for chunk in chunks]
            
            if not context_chunks:
                context_chunks = [{"text": "No relevant patterns found for this input."}]
            
            query_logger.info(f"Returned {len(context_chunks)} context chunks")
            
            return {
                "context": context_chunks,
                "steps": getattr(response, 'steps', []),
                "elapsed_time": 0,
                "correlation_id": correlation_id,
                "debug_info": {
                    "method": "agentic_rag",
                    "session_id": session_id,
                    "response_length": len(response_text) if response_text else 0
                }
            }
            
        except Exception as e:
            query_logger.error(f"Context query failed: {e}")
            return {
                "context": [{"text": f"Query failed: {str(e)}"}],
                "steps": [],
                "elapsed_time": 0,
                "correlation_id": correlation_id,
                "debug_info": {"error": str(e)}
            }



    def _is_valid_context(self, text):
        """Enhanced content validation"""
        if not text or len(text.strip()) < 10:
            return False
        
        # Less aggressive filtering
        skip_patterns = [
            "knowledge_search tool found",
            "BEGIN", "END",
            "The above results",
            "START-RETRIEVED-CONTEXT",
            "END-RETRIEVED-CONTEXT"
        ]
        
        text_lower = text.lower().strip()
        for pattern in skip_patterns:
            if text_lower.startswith(pattern.lower()):
                return False
        
        return True

    async def ask_question(self, question: str, correlation_id: str = None) -> Dict[str, Any]:
        """Ask a question to the RAG agent - following agentic RAG pattern."""
        correlation_id = correlation_id or str(uuid.uuid4())
        query_logger = create_correlation_logger("context-agent", correlation_id)
        
        query_logger.info(f"Processing question: {question[:100]}...")
        
        try:
            session_id = self.agent.create_session(f"session-{uuid.uuid4()}")
            
            response = self.agent.create_turn(
                messages=[{"role": "user", "content": question}],
                session_id=session_id,
                stream=False
            )
            
            # Use built-in LlamaStack logging to show steps
            query_logger.info("=== Agent Steps for Question: %s ===", question[:50])
            if hasattr(response, 'steps') and response.steps:
                # Log each step to show RAG tool usage
                for i, step in enumerate(response.steps):
                    query_logger.info("Step %d: %s", i+1, getattr(step, 'step_type', 'unknown'))
                    if hasattr(step, 'tool_calls') and step.tool_calls:
                        for tool_call in step.tool_calls:
                            tool_name = getattr(tool_call, 'tool_name', 'unknown')
                            query_logger.info("  → Tool called: %s", tool_name)
                            if hasattr(tool_call, 'result') and tool_call.result:
                                result_preview = str(tool_call.result)[:100] + "..." if len(str(tool_call.result)) > 100 else str(tool_call.result)
                                query_logger.info("  → Tool result preview: %s", result_preview)
            
            response_text = self._extract_response_content(response)
            
            return {
                "question": question,
                "answer": response_text,
                "session_id": session_id,
                "correlation_id": correlation_id,
                "status": "success"
            }
            
        except Exception as e:
            query_logger.error("Question processing error: %s", e, exc_info=True)
            return {
                "question": question,
                "answer": f"Query failed: {str(e)}",
                "session_id": None,
                "correlation_id": correlation_id,
                "status": "error"
            }

    def _iter_stream_with_agent(self, session_id: str, question: str):
        """Stream responses from the agent - following agentic RAG pattern."""
        try:
            response_stream = self.agent.create_turn(
                messages=[{"role": "user", "content": question}],
                session_id=session_id,
                stream=True
            )

            accumulated_text = ""
            event_logger = AgentEventLogger()
            
            for event in event_logger.log(response_stream):
                try:
                    event_content = None
                    if hasattr(event, 'content'):
                        event_content = event.content
                    elif hasattr(event, 'text'):
                        event_content = event.text
                    
                    if event_content and isinstance(event_content, str) and event_content.strip():
                        # Skip tool call JSON, send actual response text
                        if not (event_content.strip().startswith('{') and 'knowledge_search' in event_content):
                            accumulated_text += event_content
                            yield self._sse({"type": "text", "content": event_content})

                    # Check for completion
                    event_type_name = type(event).__name__.lower()
                    if 'turn' in event_type_name and 'complete' in event_type_name:
                        if accumulated_text.strip():
                            yield self._sse({"type": "done", "full_response": accumulated_text.strip()})
                        else:
                            yield self._sse({"type": "done", "full_response": "Response completed"})
                        return

                except Exception as e:
                    self.logger.warning("Error processing event: %s", e)

            # Fallback completion
            if accumulated_text.strip():
                yield self._sse({"type": "done", "full_response": accumulated_text.strip()})
            else:
                yield self._sse({"type": "done", "full_response": "Response completed"})

        except Exception as e:
            self.logger.error("Error in agent streaming: %s", e, exc_info=True)
            yield self._sse({"type": "error", "error": str(e)})

    async def ask_question_stream(self, question: str, correlation_id: str = None) -> Generator[bytes, None, None]:
        """Ask a question to the RAG agent with streaming response - following agentic RAG pattern."""
        correlation_id = correlation_id or str(uuid.uuid4())
        query_logger = create_correlation_logger("context-agent", correlation_id)
        
        query_logger.info(f"Starting streaming question: {question[:100]}...")
        
        try:
            session_id = self.agent.create_session(f"stream-session-{uuid.uuid4()}")
            
            for chunk in self._iter_stream_with_agent(session_id, question):
                yield chunk
                
        except Exception as e:
            query_logger.error("Streaming error: %s", e, exc_info=True)
            yield self._sse({"type": "error", "error": str(e)})

    def get_status(self):
        """Get current status"""
        return {
            "vector_db_id": self.vector_db_id,
            "model": self.model,
            "status": "ready",
            "pattern": "Agentic RAG - Own Agent Instance",
            "capabilities": {
                "vector_db_search": True,
                "tool_calling": True,
                "session_management": True,
                "conversational_interface": True,
                "streaming_responses": True
            },
            "configuration": {
                "vector_db_configured": bool(self.vector_db_id),
                "own_agent_instance": True,
                "instructions_defined": True,
                "tools_configured": True
            },
            "enhanced_features": {
                "ask_question": "Conversational question answering with complete responses",
                "ask_question_stream": "Real-time streaming conversational interface",
                "sse_support": "Server-sent events for streaming",
                "intelligent_synthesis": "Agent synthesizes complete answers from RAG results"
            }
        }

    def verify_vector_db_access(self):
        """Verify that vector DB is accessible (basic check)"""
        try:
            # This is a basic check - in a real implementation you'd test actual connectivity
            if not self.vector_db_id:
                self.logger.warning("No vector DB ID configured")
                return False
            
            self.logger.info(f"Vector DB ID configured: {self.vector_db_id}")
            return True
        except Exception as e:
            self.logger.error(f"Vector DB verification failed: {e}")
            return False

    async def health_check(self):
        """Quick health check - using agent instance"""
        try:
            # Create a simple session for health check
            session_id = self.agent.create_session(f"health-check-{uuid.uuid4()}")
            
            response = self.agent.create_turn(
                messages=[{"role": "user", "content": "health check"}],
                session_id=session_id,
                stream=False
            )
            
            if response:
                self.logger.info("ContextAgent health check passed")
                return True
            else:
                self.logger.error("ContextAgent health check failed - no response")
                return False
                
        except Exception as e:
            self.logger.error(f"ContextAgent health check failed: {e}")
            return False