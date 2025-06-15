import time
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional, AsyncGenerator
import logging
import uuid
from pathlib import Path

from llama_stack_client import LlamaStackClient
from llama_stack_client.types import UserMessage

try:
    from rich.pretty import pprint
    from termcolor import cprint
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

logger = logging.getLogger("ContextAgent")

def step_printer_context(steps, correlation_id: str = ""):
    """
    Print the steps of a context agent's response in a formatted way.
    """
    if not RICH_AVAILABLE:
        logger.info(f"📋 Processing {len(steps)} context steps for correlation: {correlation_id}")
        for i, step in enumerate(steps):
            step_type = type(step).__name__
            logger.info(f"📍 Step {i+1}: {step_type}")
        return
    
    print(f"\n{'=' * 20} CONTEXT STEP ANALYSIS (correlation: {correlation_id}) {'=' * 20}")
    
    for i, step in enumerate(steps):
        step_type = type(step).__name__
        print("\n"+"-" * 10, f"📍 Step {i+1}: {step_type}","-" * 10)
        
        if step_type == "ToolExecutionStep":
            print("🔧 Executing RAG tool...")
            try:
                if hasattr(step, 'tool_responses') and step.tool_responses:
                    for j, tool_response in enumerate(step.tool_responses):
                        print(f"   Tool Response {j+1}:")
                        content = getattr(tool_response, "content", None)
                        if isinstance(content, str):
                            try:
                                parsed_content = json.loads(content)
                                pprint(parsed_content)
                            except:
                                # Show preview of content
                                preview = content[:500] + "..." if len(content) > 500 else content
                                cprint(preview, "cyan")
                        else:
                            pprint(content)
                else:
                    print("No tool responses found")
            except Exception as e:
                print(f"Error processing tool response: {e}")
                
        else:
            if hasattr(step, 'api_model_response') and step.api_model_response:
                if hasattr(step.api_model_response, 'content') and step.api_model_response.content:
                    print("🤖 Model Response:")
                    content_preview = step.api_model_response.content[:300] + "..." if len(step.api_model_response.content) > 300 else step.api_model_response.content
                    cprint(f"{content_preview}\n", "magenta")
    
    print("="*20, "Context query processing completed","="*20,"\n")

class ContextAgent:
    """
    ContextAgent to retrieve conversion patterns with enhanced logging
    """
    def __init__(self, client: LlamaStackClient, agent_id: str, session_id: str, vector_db_id: str, timeout: int = 60):
        self.client = client
        self.agent_id = agent_id
        self.session_id = session_id  # Default session
        self.vector_db_id = vector_db_id
        self.timeout = timeout
        self.logger = logger
        
        # Logging configuration - DETAILED LOGGING DEFAULT, NO FILE WRITING FOR OPENSHIFT
        self.detailed_logging = os.getenv("DETAILED_CONTEXT_LOGGING", "true").lower() == "true"  # Default: true
        self.save_debug_files = os.getenv("SAVE_CONTEXT_DEBUG", "false").lower() == "true"       # Default: false (OpenShift safe)
        self.step_analysis = os.getenv("ENABLE_CONTEXT_STEP_ANALYSIS", "true").lower() == "true" # Default: true
        self.debug_dir = Path("./debug_logs/context") if self.save_debug_files else None
        
        if self.save_debug_files and self.debug_dir:
            self.debug_dir.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"💾 Context debug file logging enabled - saving to: {self.debug_dir}")
        elif self.save_debug_files:
            self.logger.warning("⚠️ Debug file saving requested but disabled for OpenShift compatibility")
        
        self.logger.info(f"🔍 ContextAgent initialized with agent_id: {agent_id}, vector_db: {vector_db_id}")
        self.logger.info(f"🔍 Detailed logging: {'ENABLED' if self.detailed_logging else 'DISABLED'}")
        self.logger.info(f"🔍 Debug file saving: {'DISABLED (OpenShift safe)' if not self.save_debug_files else 'ENABLED'}")
        self.logger.info(f"🔍 Step analysis: {'ENABLED' if self.step_analysis else 'DISABLED'}")
        self.logger.info(f"🔍 Rich formatting: {'AVAILABLE' if RICH_AVAILABLE else 'NOT AVAILABLE'}")

    def create_new_session(self, correlation_id: str) -> str:
        """Create a new session for this specific context query"""
        try:
            response = self.client.agents.session.create(
                agent_id=self.agent_id,
                session_name=f"context-query-{correlation_id}-{uuid.uuid4()}",
            )
            session_id = response.session_id
            self.logger.info(f"📱 Created new context session: {session_id} for correlation: {correlation_id}")
            return session_id
        except Exception as e:
            self.logger.error(f"Failed to create context session: {e}")
            # Fallback to default session
            self.logger.info(f"↩️ Falling back to default context session: {self.session_id}")
            return self.session_id

    def _log_context_inputs(self, code: str, top_k: int, correlation_id: str):
        """Comprehensive logging of context query inputs"""
        
        # Basic stats logging (always enabled)
        self.logger.info(f"🔍 Starting context query for correlation: {correlation_id}")
        self.logger.info(f"📥 Input code length: {len(code)} characters")
        self.logger.info(f"📥 Top-K requested: {top_k}")
        self.logger.info(f"📥 Vector DB: {self.vector_db_id}")
        
        # Safe preview logging (always enabled)
        self.logger.info(f"📥 Input code preview: {repr(code[:300])}...")
        
        # Query statistics
        query_stats = {
            "correlation_id": correlation_id,
            "timestamp": datetime.utcnow().isoformat(),
            "input_length": len(code),
            "input_lines": code.count('\n'),
            "top_k": top_k,
            "vector_db_id": self.vector_db_id,
            "agent_id": self.agent_id
        }
        
        self.logger.info(f"📊 Context query statistics: {json.dumps(query_stats, indent=2)}")
        
        # Detailed logging (if enabled)
        if self.detailed_logging:
            self.logger.info(f"🔍 === DETAILED CONTEXT QUERY LOG START (correlation: {correlation_id}) ===")
            self.logger.info(f"📥 Full input code being sent to context agent:\n{'-' * 50}\n{code}\n{'-' * 50}")
            self.logger.info(f"🎯 Query parameters:")
            self.logger.info(f"   └─ Top-K: {top_k}")
            self.logger.info(f"   └─ Vector DB: {self.vector_db_id}")
            self.logger.info(f"   └─ Agent ID: {self.agent_id}")
            self.logger.info(f"🔍 === DETAILED CONTEXT QUERY LOG END ===")
        
        # Debug file saving (if enabled)
        if self.save_debug_files and self.debug_dir:
            try:
                # Save input code
                input_file = self.debug_dir / f"input_code_{correlation_id}.txt"
                input_file.write_text(code, encoding='utf-8')
                
                # Save query metadata
                metadata = {
                    **query_stats,
                    "files": {
                        "input_code": str(input_file)
                    }
                }
                metadata_file = self.debug_dir / f"query_metadata_{correlation_id}.json"
                metadata_file.write_text(json.dumps(metadata, indent=2), encoding='utf-8')
                
                self.logger.info(f"💾 Context query debug files saved for {correlation_id}:")
                self.logger.info(f"   📄 Input: {input_file}")
                self.logger.info(f"   📄 Metadata: {metadata_file}")
                
            except Exception as e:
                self.logger.error(f"Failed to save context debug files: {e}")

    def _log_context_results(self, context_chunks: list, steps, correlation_id: str, elapsed_time: float):
        """Log context retrieval results"""
        self.logger.info(f"📤 Context retrieval completed in {elapsed_time:.3f}s")
        self.logger.info(f"📤 Retrieved {len(context_chunks)} context chunks")
        
        # Log chunk previews
        for i, chunk in enumerate(context_chunks[:3]):  # Show first 3 chunks
            preview = chunk[:200] + "..." if len(chunk) > 200 else chunk
            self.logger.info(f"📄 Chunk {i+1} preview: {repr(preview)}")
        
        if len(context_chunks) > 3:
            self.logger.info(f"📄 ... and {len(context_chunks) - 3} more chunks")
        
        # Detailed logging
        if self.detailed_logging:
            self.logger.info(f"🔍 === DETAILED CONTEXT RESULTS (correlation: {correlation_id}) ===")
            for i, chunk in enumerate(context_chunks):
                self.logger.info(f"📄 Full Chunk {i+1}:\n{'-' * 30}\n{chunk}\n{'-' * 30}")
            self.logger.info(f"🔍 === DETAILED CONTEXT RESULTS END ===")
        
        # Step analysis
        if self.step_analysis:
            step_printer_context(steps, correlation_id)
        else:
            # Basic step logging
            for i, step in enumerate(steps):
                step_type = type(step).__name__
                self.logger.info(f"📋 Context Step {i+1}: {step_type}")
                if hasattr(step, 'step_type'):
                    self.logger.info(f"   └─ Step type: {step.step_type}")
                if hasattr(step, 'tool_responses') and step.tool_responses:
                    self.logger.info(f"   └─ Tool responses: {len(step.tool_responses)}")
        
        # Save results to debug files
        if self.save_debug_files and self.debug_dir:
            try:
                # Save retrieved chunks
                chunks_data = {
                    "correlation_id": correlation_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "elapsed_time": elapsed_time,
                    "chunk_count": len(context_chunks),
                    "chunks": [{"index": i, "content": chunk, "length": len(chunk)} for i, chunk in enumerate(context_chunks)]
                }
                chunks_file = self.debug_dir / f"retrieved_chunks_{correlation_id}.json"
                chunks_file.write_text(json.dumps(chunks_data, indent=2), encoding='utf-8')
                
                # Save step analysis
                steps_data = []
                for i, step in enumerate(steps):
                    step_info = {
                        "step_number": i + 1,
                        "step_type": type(step).__name__,
                        "has_tool_responses": hasattr(step, 'tool_responses') and bool(step.tool_responses)
                    }
                    if hasattr(step, 'step_type'):
                        step_info["internal_step_type"] = step.step_type
                    if hasattr(step, 'tool_responses') and step.tool_responses:
                        step_info["tool_response_count"] = len(step.tool_responses)
                    steps_data.append(step_info)
                
                steps_file = self.debug_dir / f"context_steps_{correlation_id}.json"
                steps_file.write_text(json.dumps(steps_data, indent=2), encoding='utf-8')
                
                self.logger.info(f"💾 Context results saved:")
                self.logger.info(f"   📄 Chunks: {chunks_file}")
                self.logger.info(f"   📄 Steps: {steps_file}")
                
            except Exception as e:
                self.logger.error(f"Failed to save context results: {e}")

    async def query_context(
        self,
        code: str,
        top_k: int = 5,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        correlation_id = correlation_id or str(uuid.uuid4())
        start_time = time.time()

        # Log all input details
        self._log_context_inputs(code, top_k, correlation_id)

        try:
            # Create dedicated session for this query
            query_session_id = self.create_new_session(correlation_id)

            # Direct API call - send the code to the context agent with RAG
            messages = [UserMessage(role="user", content=code)]
            
            self.logger.info(f"📡 Sending context query to LLM (agent: {self.agent_id}, session: {query_session_id})")
            
            generator = self.client.agents.turn.create(
                agent_id=self.agent_id,
                session_id=query_session_id,
                messages=messages,
                stream=True,
            )
            
            # Process streaming response
            turn = None
            chunk_count = 0
            for chunk in generator:
                chunk_count += 1
                event = chunk.event
                event_type = event.payload.event_type
                if event_type == "turn_complete":
                    turn = event.payload.turn
                    break
            
            self.logger.info(f"📡 Received {chunk_count} chunks from context LLM")
            
            if not turn:
                self.logger.error("No turn completed in context response")
                raise RuntimeError("No turn completed in context query")

            # Extract context chunks from tool responses
            context_chunks = self._extract_context_from_steps(turn.steps)
            
            # Fallback to main output if no tool responses
            if not context_chunks:
                output = turn.output_message.content.strip()
                if output:
                    context_chunks.append(output)
                    self.logger.info("📄 Using main output as context (no tool responses found)")

            context_list = [{"text": chunk} for chunk in context_chunks if chunk]
            
            total_time = time.time() - start_time
            
            # Log results
            self._log_context_results(context_chunks, turn.steps, correlation_id, total_time)
            
            self.logger.info(f"Context query completed successfully for correlation: {correlation_id}")
            
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
            self.logger.error(f"Context query failed for correlation {correlation_id} after {total_time:.3f}s: {str(e)}")
            
            # Log error details if debug mode is on
            if self.save_debug_files and self.debug_dir:
                try:
                    error_file = self.debug_dir / f"context_error_{correlation_id}.txt"
                    error_details = {
                        "correlation_id": correlation_id,
                        "timestamp": datetime.utcnow().isoformat(),
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "input_code_length": len(code),
                        "top_k": top_k,
                        "elapsed_time": total_time
                    }
                    error_file.write_text(json.dumps(error_details, indent=2), encoding='utf-8')
                    self.logger.info(f"💾 Context error details saved to: {error_file}")
                except Exception as save_error:
                    self.logger.error(f"Failed to save context error details: {save_error}")
            
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
            "pattern": "LSS API",
            "logging_config": {
                "detailed_logging": self.detailed_logging,
                "debug_file_saving": self.save_debug_files,
                "step_analysis": self.step_analysis,
                "rich_formatting": RICH_AVAILABLE,
                "debug_directory": str(self.debug_dir) if self.debug_dir else None
            }
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
            
            self.logger.info("Context agent health check passed")
            return True
        except Exception as e:
            self.logger.error(f"Context agent health check failed: {e}")
            return False