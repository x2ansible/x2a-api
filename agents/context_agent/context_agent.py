import uuid
import json
from typing import Dict, Any, Generator
from llama_stack_client import LlamaStackClient, Agent, AgentEventLogger
from shared.log_utils import create_correlation_logger

class ContextAgent:
    """
    Agentic RAG ContextAgent - Creates own Agent instance with defined instructions and tools
    """
    def __init__(self, client: LlamaStackClient, vector_db_id: str, agent_id: str = None, session_id: str = None, model: str = "llama-4-scout-17b-16e-w4a16"):
        self.client = client
        self.vector_db_id = vector_db_id
        self.model = model
        self.agent_id = agent_id
        self.session_id = session_id
        
        # Use shared logging utilities with correlation ID
        self.logger = create_correlation_logger("context-agent", "context-agent-init")

        # Follow same pattern as ChefAnalysisAgent and CodeGeneratorAgent
        # Use registered agent_id directly with client calls - no Agent() wrapper needed
        if agent_id:
            self.logger.info(f"Using existing registered agent: {agent_id}")
            # No Agent wrapper needed - use client directly like other agents
        else:
            self.logger.warning("No agent_id provided - this should not happen with proper startup!")
            raise ValueError("ContextAgent requires agent_id from registered agent")
        
        self.logger.info("ContextAgent initialized")
        self.logger.info(f"Vector DB: {self.vector_db_id}")
        self.logger.info(f"Model: {self.model}")
        self.logger.info(f"Agent ID: {self.agent_id}")


    def _sse(self, payload: Dict[str, Any]) -> bytes:
        """Server-sent events formatter for streaming responses"""
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")

    def _extract_response_content(self, response) -> str:
        """Extract text content from agent response - enhanced for agentic RAG."""
        # First, try the standard output message
        if hasattr(response, 'output_message'):
            output_msg = response.output_message
            if hasattr(output_msg, 'content') and output_msg.content:
                return output_msg.content
            elif isinstance(output_msg, str):
                return output_msg
        
        # Check for content attribute (handles MockResponse with turn object)
        if hasattr(response, 'content') and response.content:
            content = response.content
            # If content is already a string (from output_message.content), return it
            if isinstance(content, str):
                return content
            # If content is a turn object, extract from its steps like CodeGeneratorAgent
            elif hasattr(content, 'steps') and content.steps:
                # Process steps like CodeGeneratorAgent does
                for step in reversed(content.steps):
                    if hasattr(step, 'step_type') and str(step.step_type) == "StepType.inference":
                        if hasattr(step, 'model_response'):
                            model_resp = step.model_response
                            if hasattr(model_resp, 'content'):
                                return model_resp.content
            # Otherwise try to convert to string
            else:
                return str(content)
        
        # Check message attribute
        if hasattr(response, 'message'):
            msg = response.message
            if hasattr(msg, 'content'):
                return msg.content
            elif isinstance(msg, str):
                return msg
        
        # Check for steps-based responses (tool calling responses)
        if hasattr(response, 'steps') and response.steps:
            # Look for the final step's content
            for step in reversed(response.steps):  # Check from last step
                if hasattr(step, 'step_type') and 'inference' in str(step.step_type).lower():
                    if hasattr(step, 'output') and step.output:
                        if hasattr(step.output, 'content'):
                            return step.output.content
                        elif isinstance(step.output, str):
                            return step.output
                
                # Also check for completion steps
                if hasattr(step, 'completion') and step.completion:
                    if hasattr(step.completion, 'content'):
                        return step.completion.content
                    elif isinstance(step.completion, str):
                        return step.completion
        
        # Fallback to string representation
        if isinstance(response, str):
            return response
        
        # Log response structure for debugging
        self.logger.warning(f"Could not extract content from response. Available attributes: {dir(response) if hasattr(response, '__dict__') else 'No attributes'}")
        
        return str(response) if response else "No response received"

    def _clean_agent_response(self, response_text: str) -> str:
        """Clean agent meta-commentary from response text."""
        if not response_text:
            return response_text
        
        # Remove common agent prefixes
        prefixes_to_remove = [
            "The retrieved content is:",
            "Based on the knowledge_search tool results,",
            "Here are the relevant patterns:",
            "The following patterns were found:",
            "According to the search results,",
            "The search returned the following:",
        ]
        
        cleaned_text = response_text.strip()
        
        for prefix in prefixes_to_remove:
            if cleaned_text.startswith(prefix):
                cleaned_text = cleaned_text[len(prefix):].strip()
        
        # Remove common agent suffixes
        suffixes_to_remove = [
            "These patterns can be used for your Infrastructure as Code needs.",
            "Hope this helps with your conversion.",
            "These are the relevant patterns found.",
        ]
        
        for suffix in suffixes_to_remove:
            if cleaned_text.endswith(suffix):
                cleaned_text = cleaned_text[:-len(suffix)].strip()
        
        return cleaned_text

    def create_new_session(self, correlation_id: str) -> str:
        """Create new session for context queries - using direct client calls like other agents"""
        try:
            session_name = f"context-query-{correlation_id}-{uuid.uuid4()}"
            response = self.client.agents.session.create(
                agent_id=self.agent_id,
                session_name=session_name
            )
            session_id = response.session_id
            
            # Create logger with correlation ID for this session
            session_logger = create_correlation_logger("context-agent", correlation_id)
            session_logger.info(f"Created context session: {session_id} for correlation: {correlation_id}")
            return session_id
        except Exception as e:
            self.logger.error(f"Failed to create session: {e}")
            # Create a fallback session
            fallback_response = self.client.agents.session.create(
                agent_id=self.agent_id,
                session_name=f"fallback-{uuid.uuid4()}"
            )
            fallback_session_id = fallback_response.session_id
            self.logger.info(f"Using fallback session: {fallback_session_id}")
            return fallback_session_id

    async def query_context(self, code, top_k=5, correlation_id=None):
        """Simplified context query using agentic RAG pattern"""
        correlation_id = correlation_id or str(uuid.uuid4())
        query_logger = create_correlation_logger("context-agent", correlation_id)
        
        query_logger.info(f"Context query: {repr(code)[:100]}...")
        
        try:
            # Use direct client calls like ChefAnalysisAgent and CodeGeneratorAgent
            session_id = self.session_id or self.create_new_session(correlation_id)
            
            generator = self.client.agents.turn.create(
                agent_id=self.agent_id,
                session_id=session_id,
                messages=[{"role": "user", "content": code}],
                stream=True
            )
            
            # Process streaming response EXACTLY like CodeGeneratorAgent
            turn = None
            chunk_count = 0
            last_event_type = None
            
            for chunk in generator:
                chunk_count += 1
                if hasattr(chunk, 'event') and chunk.event:
                    event = chunk.event
                    if hasattr(event, 'payload') and event.payload:
                        event_type = getattr(event.payload, 'event_type', None)
                        last_event_type = event_type
                        if event_type == "turn_complete":
                            turn = getattr(event.payload, 'turn', None)
                            break
                        elif event_type == "step_complete":
                            query_logger.debug(f"Step completed: {chunk_count}")
                        elif event_type == "error":
                            error_msg = getattr(event.payload, 'error', 'Unknown error')
                            raise RuntimeError(f"LLM returned error: {error_msg}")
                if chunk_count > 1000:  # Reasonable limit
                    query_logger.warning(f"Too many chunks received ({chunk_count}), breaking")
                    break
            
            query_logger.info(f"Received {chunk_count} chunks from LLM (last event: {last_event_type})")
            
            if not turn:
                error_msg = f"No turn completed in response. Last event type: {last_event_type}, Chunk count: {chunk_count}"
                query_logger.error(error_msg)
                raise RuntimeError(error_msg)
            
            # Create a mock response object for compatibility with existing _extract_response_content
            class MockResponse:
                def __init__(self, turn_obj):
                    self.steps = getattr(turn_obj, 'steps', [])
                    self.output_message = getattr(turn_obj, 'output_message', None)
                    # Extract content like CodeGeneratorAgent does
                    if hasattr(turn_obj, 'output_message') and turn_obj.output_message:
                        if hasattr(turn_obj.output_message, 'content'):
                            self.content = turn_obj.output_message.content
                        else:
                            self.content = str(turn_obj.output_message)
                    else:
                        self.content = "No output message found"
            
            response = MockResponse(turn)
            
            # Extract response content
            # Extract response text directly like CodeGeneratorAgent
            if hasattr(turn, 'output_message') and turn.output_message and hasattr(turn.output_message, 'content'):
                response_text = turn.output_message.content
            else:
                response_text = "No content found in response"
            
            # Clean up agent commentary from response
            if response_text:
                # Remove agent meta-commentary
                response_text = self._clean_agent_response(response_text)
            
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
            # Use direct client calls like ChefAnalysisAgent and CodeGeneratorAgent
            session_id = self.session_id or self.create_new_session(correlation_id)
            
            generator = self.client.agents.turn.create(
                agent_id=self.agent_id,
                session_id=session_id,
                messages=[{"role": "user", "content": question}],
                stream=True
            )
            
            # Process streaming response EXACTLY like CodeGeneratorAgent
            turn = None
            chunk_count = 0
            last_event_type = None
            
            for chunk in generator:
                chunk_count += 1
                if hasattr(chunk, 'event') and chunk.event:
                    event = chunk.event
                    if hasattr(event, 'payload') and event.payload:
                        event_type = getattr(event.payload, 'event_type', None)
                        last_event_type = event_type
                        if event_type == "turn_complete":
                            turn = getattr(event.payload, 'turn', None)
                            break
                        elif event_type == "step_complete":
                            query_logger.debug(f"Step completed: {chunk_count}")
                        elif event_type == "error":
                            error_msg = getattr(event.payload, 'error', 'Unknown error')
                            raise RuntimeError(f"LLM returned error: {error_msg}")
                if chunk_count > 1000:  # Reasonable limit
                    query_logger.warning(f"Too many chunks received ({chunk_count}), breaking")
                    break
            
            query_logger.info(f"Received {chunk_count} chunks from LLM (last event: {last_event_type})")
            
            if not turn:
                error_msg = f"No turn completed in response. Last event type: {last_event_type}, Chunk count: {chunk_count}"
                query_logger.error(error_msg)
                raise RuntimeError(error_msg)
            
            # Create a mock response object for compatibility with existing _extract_response_content
            class MockResponse:
                def __init__(self, turn_obj):
                    self.steps = getattr(turn_obj, 'steps', [])
                    self.output_message = getattr(turn_obj, 'output_message', None)
                    # Extract content like CodeGeneratorAgent does
                    if hasattr(turn_obj, 'output_message') and turn_obj.output_message:
                        if hasattr(turn_obj.output_message, 'content'):
                            self.content = turn_obj.output_message.content
                        else:
                            self.content = str(turn_obj.output_message)
                    else:
                        self.content = "No output message found"
            
            response = MockResponse(turn)
            
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
            
            # Extract response text directly like CodeGeneratorAgent
            if hasattr(turn, 'output_message') and turn.output_message and hasattr(turn.output_message, 'content'):
                response_text = turn.output_message.content
            else:
                response_text = "No content found in response"
            
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
        """Quick health check - using direct client calls like other agents"""
        try:
            return {
                "healthy": True,
                "vector_db": self.vector_db_id,
                "agent": "ready" if self.agent_id else "not_ready",
                "agent_id": self.agent_id,
                "session_id": self.session_id,
                "model": self.model
            }
                
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
                "vector_db": self.vector_db_id,
                "model": self.model
            }