import uuid
import logging
from llama_stack_client import LlamaStackClient
from llama_stack_client.types import UserMessage
from shared.log_utils import create_correlation_logger, step_printer
from datetime import datetime

class ContextAgent:
    """
    FIXED ContextAgent - Uses existing LlamaStack agent instead of creating new one
    """
    def __init__(self, client: LlamaStackClient, agent_id: str, session_id: str, vector_db_id: str, timeout: int = 60):
        self.client = client
        self.agent_id = agent_id
        self.session_id = session_id
        self.vector_db_id = vector_db_id
        self.timeout = timeout
        # Model will be determined from agent configuration, not hard-coded
        
        # Use shared logging utilities with correlation ID
        self.logger = create_correlation_logger("context-agent", "context-agent-init")

        self.logger.info("ContextAgent initialized")
        self.logger.info(f"Vector DB: {self.vector_db_id}")
        self.logger.info(f"Agent ID: {self.agent_id}")
        self.logger.info(f"Session ID: {self.session_id}")

    def create_new_session(self, correlation_id: str) -> str:
        """Create new session for context queries"""
        try:
            session_name = f"context-query-{correlation_id}-{uuid.uuid4()}"
            response = self.client.agents.session.create(
                agent_id=self.agent_id,
                session_name=session_name,
            )
            session_id = response.session_id
            # Create logger with correlation ID for this session
            session_logger = create_correlation_logger("context-agent", correlation_id)
            session_logger.info(f"Created context session: {session_id} for correlation: {correlation_id}")
            return session_id
        except Exception as e:
            self.logger.error(f"Failed to create session: {e}")
            self.logger.info(f"Falling back to default session: {self.session_id}")
            return self.session_id

    async def query_context(self, code, top_k=5, correlation_id=None):
        correlation_id = correlation_id or str(uuid.uuid4())
        
        # Create logger with correlation ID for this query
        query_logger = create_correlation_logger("context-agent", correlation_id)
        
        query_logger.info(f"Sending query to ContextAgent: {repr(code)[:200]}...")
        query_logger.info(f"Using vector DB: {self.vector_db_id}")
        
        # Use the existing agent infrastructure instead of creating new agent
        session_id = self.create_new_session(correlation_id)
        
        try:
            query_logger.info(f"Creating turn with session: {session_id}")
            
            # Use the proper LlamaStack client API
            messages = [UserMessage(role="user", content=code)]
            
            generator = self.client.agents.turn.create(
                agent_id=self.agent_id,
                session_id=session_id,
                messages=messages,
                stream=True,
            )
            
            # Process the streaming response
            turn = None
            chunk_count = 0
            
            for chunk in generator:
                chunk_count += 1
                if chunk and hasattr(chunk, 'event') and chunk.event:
                    event = chunk.event
                    if hasattr(event, 'payload') and event.payload:
                        event_type = getattr(event.payload, 'event_type', None)
                        if event_type == "turn_complete":
                            turn = getattr(event.payload, 'turn', None)
                            query_logger.info(f"Turn completed successfully after {chunk_count} chunks")
                            break
                        elif event_type == "step_complete":
                            query_logger.debug(f"Step completed: {chunk_count}")
            
            if not turn:
                query_logger.error(f"No turn completed in response")
                return {
                    "context": [{"text": "No turn completed in response"}],
                    "steps": [],
                    "elapsed_time": 0,
                    "correlation_id": correlation_id
                }
            
            steps = getattr(turn, 'steps', [])
            query_logger.info(f"Processing {len(steps)} steps")
            
            # Use shared step_printer for better logging
            try:
                step_printer(steps, query_logger)
            except AttributeError as e:
                if "console" in str(e):
                    query_logger.info("Step printer console not available, using basic logging")
                    for i, step in enumerate(steps):
                        step_type = type(step).__name__
                        query_logger.info(f"Step {i+1}: {step_type}")
                else:
                    raise e
            
            # Enhanced content extraction with better debugging
        except Exception as e:
            query_logger.error(f"Turn creation failed: {e}")
            return {
                "context": [{"text": f"Query failed: {str(e)}"}],
                "steps": [],
                "elapsed_time": 0,
                "correlation_id": correlation_id
            }
        
        # Enhanced content extraction with better debugging
        context_chunks = []
        tool_responses_found = 0
        vector_db_responses_found = 0
        
        for i, step in enumerate(steps):
            step_type = type(step).__name__
            query_logger.info(f"Step {i+1}: {step_type}")
            
            tool_responses = getattr(step, "tool_responses", [])
            if tool_responses:
                tool_responses_found += len(tool_responses)
                query_logger.info(f"Found {len(tool_responses)} tool responses in step {i+1}")
                
                for j, tool_response in enumerate(tool_responses):
                    content = getattr(tool_response, "content", None)
                    tool_name = getattr(tool_response, "tool_name", "unknown")
                    query_logger.info(f"Tool response {j+1}: {tool_name}, content type: {type(content)}")
                    
                    # Validate that this is a vector DB search response
                    if ("knowledge_search" in tool_name.lower() or 
                        "rag" in tool_name.lower() or 
                        "search" in tool_name.lower() or
                        "builtin::rag/knowledge_search" in tool_name):
                        vector_db_responses_found += 1
                        query_logger.info(f"Vector DB search response found: {tool_name}")
                        
                        # Log RAG-specific response structure
                        if isinstance(content, str):
                            query_logger.info(f"RAG response type: string, length: {len(content)}")
                        elif isinstance(content, list):
                            query_logger.info(f"RAG response type: list, items: {len(content)}")
                            for idx, item in enumerate(content):
                                if hasattr(item, 'content'):
                                    query_logger.info(f"RAG item {idx}: content field present")
                                elif hasattr(item, 'text'):
                                    query_logger.info(f"RAG item {idx}: text field present")
                        else:
                            query_logger.info(f"RAG response type: {type(content)}")
                    
                    if isinstance(content, list):
                        query_logger.info(f"Processing list content with {len(content)} items")
                        for item in content:
                            if hasattr(item, "text"):
                                text = item.text.strip()
                                if self._is_valid_context(text):
                                    context_chunks.append(text)
                                    query_logger.info(f"Added item.text: {len(text)} chars")
                            elif hasattr(item, "content"):
                                text = item.content.strip()
                                if self._is_valid_context(text):
                                    context_chunks.append(text)
                                    query_logger.info(f"Added item.content: {len(text)} chars")
                            elif isinstance(item, dict) and "content" in item:
                                text = item["content"].strip()
                                if self._is_valid_context(text):
                                    context_chunks.append(text)
                                    query_logger.info(f"Added dict content: {len(text)} chars")
                            # RAG-specific: handle chunk.content format
                            elif isinstance(item, dict) and "chunk" in item:
                                chunk = item["chunk"]
                                if isinstance(chunk, dict) and "content" in chunk:
                                    text = chunk["content"].strip()
                                    if self._is_valid_context(text):
                                        context_chunks.append(text)
                                        query_logger.info(f"Added RAG chunk.content: {len(text)} chars")
                                elif hasattr(chunk, "content"):
                                    text = chunk.content.strip()
                                    if self._is_valid_context(text):
                                        context_chunks.append(text)
                                        query_logger.info(f"Added RAG chunk.content: {len(text)} chars")
                            # RAG-specific: handle metadata format
                            elif isinstance(item, dict) and "metadata" in item:
                                metadata = item["metadata"]
                                if isinstance(metadata, dict) and "content" in metadata:
                                    text = metadata["content"].strip()
                                    if self._is_valid_context(text):
                                        context_chunks.append(text)
                                        query_logger.info(f"Added RAG metadata.content: {len(text)} chars")
                    elif isinstance(content, str):
                        text = content.strip()
                        if self._is_valid_context(text):
                            context_chunks.append(text)
                            query_logger.info(f"Added string content: {len(text)} chars")
        
        query_logger.info(f"Total tool responses found: {tool_responses_found}")
        query_logger.info(f"Vector DB search responses found: {vector_db_responses_found}")
        query_logger.info(f"Extracted {len(context_chunks)} valid chunks")
        
        # As a last resort, append the top-level LLM output if no vector DB responses found
        if not context_chunks and vector_db_responses_found == 0:
            query_logger.warning("No vector DB search responses found, checking LLM output as fallback")
            # Try to get content from turn output message
            if hasattr(turn, 'output_message') and turn.output_message:
                top_content = getattr(turn.output_message, "content", "").strip()
                if top_content:
                    context_chunks.append(top_content)
                    query_logger.info(f"Using LLM fallback response: {len(top_content)} chars")
                else:
                    query_logger.warning("No content found in output message")
                    context_chunks.append("No relevant patterns found for this input.")
            else:
                query_logger.warning("No output message found in turn")
                context_chunks.append("No relevant patterns found for this input.")
        elif vector_db_responses_found == 0:
            query_logger.warning("No vector DB search responses found - agent may not be calling vector DB tools")
            context_chunks.append("No vector DB search results found. Please check tool configuration.")
        
        # Output as a list of dicts for UI compatibility
        context_list = [{"text": chunk} for chunk in context_chunks if chunk]
        query_logger.info(f" ContextAgent returned {len(context_list)} chunks")
        
        # Add comprehensive debugging information
        debug_info = {
            "tool_responses_found": tool_responses_found,
            "vector_db_responses_found": vector_db_responses_found,
            "context_chunks_extracted": len(context_chunks),
            "session_id": session_id,
            "correlation_id": correlation_id,
            "vector_db_id": self.vector_db_id,
            "rag_tool_detected": vector_db_responses_found > 0,
            "rag_tool_name": "builtin::rag/knowledge_search",
            "expected_tool_calls": True
        }
        query_logger.info(f"Debug info: {debug_info}")
        
        # Enhanced validation for RAG agent behavior
        if vector_db_responses_found == 0:
            query_logger.warning("RAG agent did not call knowledge_search tool - this may indicate configuration issues")
            query_logger.warning("Expected tool: builtin::rag/knowledge_search")
            query_logger.warning("Check agent configuration and tool setup")
        else:
            query_logger.info(f"RAG agent successfully called knowledge_search tool {vector_db_responses_found} times")
        
        return {
            "context": context_list,
            "steps": steps,
            "elapsed_time": 0,  # Add for compatibility
            "correlation_id": correlation_id,
            "debug_info": debug_info
        }

    async def query_context_stream(self, code, top_k=5, correlation_id=None):
        """Stream context query results for UI compatibility"""
        correlation_id = correlation_id or str(uuid.uuid4())
        
        # Create logger with correlation ID for this query
        query_logger = create_correlation_logger("context-agent", correlation_id)
        
        query_logger.info(f"Starting streaming query: {repr(code)[:200]}...")
        
        # Yield start event
        yield {
            'event': 'start', 
            'timestamp': datetime.now().isoformat(), 
            'msg': 'Context search started'
        }
        
        # Yield progress event
        yield {
            'event': 'progress', 
            'progress': 0.5, 
            'msg': 'Searching knowledge base...', 
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            # Perform the actual query
            result = await self.query_context(code, top_k, correlation_id)
            
            # Yield completion event
            yield {
                'event': 'complete',
                'context': result.get('context', []),
                'correlation_id': result.get('correlation_id', correlation_id),
                'elapsed_time': result.get('elapsed_time', 0),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            query_logger.error(f"Streaming query failed: {e}")
            yield {
                'event': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
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

    def get_status(self):
        """Get current status"""
        return {
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "vector_db_id": self.vector_db_id,
            "model": "Fixed Agent (No Internal Agent Creation)", # This will need to be updated if model is determined from agent config
            "status": "ready",
            "pattern": "Fixed Agent (No Internal Agent Creation)",
            "capabilities": {
                "vector_db_search": True,
                "tool_calling": True,
                "session_management": True
            },
            "configuration": {
                "timeout": self.timeout,
                "vector_db_configured": bool(self.vector_db_id)
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
        """Quick health check"""
        try:
            # Create a simple session for health check
            session_id = self.create_new_session("health-check")
            messages = [UserMessage(role="user", content="health check")]
            
            generator = self.client.agents.turn.create(
                agent_id=self.agent_id,
                session_id=session_id,
                messages=messages,
                stream=True,
            )
            
            # Just check if we get any response
            chunk_received = False
            for chunk in generator:
                chunk_received = True
                break
            
            if chunk_received:
                self.logger.info("ContextAgent health check passed")
                return True
            else:
                self.logger.error("ContextAgent health check failed - no response")
                return False
                
        except Exception as e:
            self.logger.error(f"ContextAgent health check failed: {e}")
            return False