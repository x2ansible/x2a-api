import uuid
import logging
from llama_stack_client import LlamaStackClient
from llama_stack_client.types import UserMessage

logger = logging.getLogger("ContextAgent")

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
        self.model = "meta-llama/Llama-3.1-8B-Instruct"  # Default model

        logger.info(" ContextAgent initialized with enhanced instructions")
        logger.info(f"🔍 Vector DB: {self.vector_db_id}")
        logger.info(f"🤖 Model: {self.model}")
        logger.info(f"🆔 Using existing agent: {self.agent_id}")

    def create_new_session(self, correlation_id: str) -> str:
        """Create new session for context queries"""
        try:
            session_name = f"context-query-{correlation_id}-{uuid.uuid4()}"
            response = self.client.agents.session.create(
                agent_id=self.agent_id,
                session_name=session_name,
            )
            session_id = response.session_id
            logger.info(f"📱 Created context session: {session_id} for correlation: {correlation_id}")
            return session_id
        except Exception as e:
            logger.error(f" Failed to create session: {e}")
            logger.info(f"↩️ Falling back to default session: {self.session_id}")
            return self.session_id

    async def query_context(self, code, top_k=5, correlation_id=None):
        correlation_id = correlation_id or str(uuid.uuid4())
        
        logger.info(f"📬 Sending query to ContextAgent: {repr(code)[:200]}...")
        logger.info(f"🔍 Using vector DB: {self.vector_db_id}")
        
        # Use the existing agent infrastructure instead of creating new agent
        session_id = self.create_new_session(correlation_id)
        
        try:
            logger.info(f"📡 Creating turn with session: {session_id}")
            
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
                            logger.info(f"📡 Turn completed successfully after {chunk_count} chunks")
                            break
                        elif event_type == "step_complete":
                            logger.debug(f"🔄 Step completed: {chunk_count}")
            
            if not turn:
                logger.error(f" No turn completed in response")
                return {
                    "context": [{"text": "No turn completed in response"}],
                    "steps": [],
                    "elapsed_time": 0,
                    "correlation_id": correlation_id
                }
            
            steps = getattr(turn, 'steps', [])
            logger.info(f"📋 Processing {len(steps)} steps")
            
        except Exception as e:
            logger.error(f" Turn creation failed: {e}")
            return {
                "context": [{"text": f"Query failed: {str(e)}"}],
                "steps": [],
                "elapsed_time": 0,
                "correlation_id": correlation_id
            }
        
        # Enhanced content extraction with better debugging
        context_chunks = []
        tool_responses_found = 0
        
        for i, step in enumerate(steps):
            step_type = type(step).__name__
            logger.info(f"📍 Step {i+1}: {step_type}")
            
            tool_responses = getattr(step, "tool_responses", [])
            if tool_responses:
                tool_responses_found += len(tool_responses)
                logger.info(f"🔧 Found {len(tool_responses)} tool responses in step {i+1}")
                
                for j, tool_response in enumerate(tool_responses):
                    content = getattr(tool_response, "content", None)
                    logger.info(f"🔧 Tool response {j+1} content type: {type(content)}")
                    
                    if isinstance(content, list):
                        logger.info(f"📄 Processing list content with {len(content)} items")
                        for item in content:
                            if hasattr(item, "text"):
                                text = item.text.strip()
                                if self._is_valid_context(text):
                                    context_chunks.append(text)
                                    logger.info(f"📄 Added item.text: {len(text)} chars")
                            elif hasattr(item, "content"):
                                text = item.content.strip()
                                if self._is_valid_context(text):
                                    context_chunks.append(text)
                                    logger.info(f"📄 Added item.content: {len(text)} chars")
                            elif isinstance(item, dict) and "content" in item:
                                text = item["content"].strip()
                                if self._is_valid_context(text):
                                    context_chunks.append(text)
                                    logger.info(f"📄 Added dict content: {len(text)} chars")
                    elif isinstance(content, str):
                        text = content.strip()
                        if self._is_valid_context(text):
                            context_chunks.append(text)
                            logger.info(f"📄 Added string content: {len(text)} chars")
        
        logger.info(f"🔧 Total tool responses found: {tool_responses_found}")
        logger.info(f"📄 Extracted {len(context_chunks)} valid chunks")
        
        # As a last resort, append the top-level LLM output if nothing else
        if not context_chunks:
            # Try to get content from turn output message
            if hasattr(turn, 'output_message') and turn.output_message:
                top_content = getattr(turn.output_message, "content", "").strip()
                if top_content:
                    context_chunks.append(top_content)
                    logger.info(f"📄 Using top-level response: {len(top_content)} chars")
                else:
                    logger.warning("⚠️ No content found in output message")
                    context_chunks.append("No relevant patterns found for this input.")
            else:
                logger.warning("⚠️ No output message found in turn")
                context_chunks.append("No relevant patterns found for this input.")
        
        # Output as a list of dicts for UI compatibility
        context_list = [{"text": chunk} for chunk in context_chunks if chunk]
        logger.info(f" ContextAgent returned {len(context_list)} chunks")
        
        return {
            "context": context_list,
            "steps": steps,
            "elapsed_time": 0,  # Add for compatibility
            "correlation_id": correlation_id
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
            "model": self.model,
            "status": "ready",
            "pattern": "Fixed Agent (No Internal Agent Creation)"
        }

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
                logger.info(" ContextAgent health check passed")
                return True
            else:
                logger.error(" ContextAgent health check failed - no response")
                return False
                
        except Exception as e:
            logger.error(f" ContextAgent health check failed: {e}")
            return False