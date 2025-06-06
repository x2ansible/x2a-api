import logging
import re
import uuid
from typing import Optional, Dict, Any

from llama_stack_client import LlamaStackClient
from llama_stack_client.types import UserMessage

logger = logging.getLogger("CodeGeneratorAgent")

def _clean_playbook_output(output: str) -> str:
    """Clean and normalize playbook output"""
    output = re.sub(r"(?m)^(```+|~~~+)[\w\-]*\n?", '', output)
    output = output.strip()
    if output.startswith("'''") and output.endswith("'''"):
        output = output[3:-3].strip()
    elif output.startswith('"""') and output.endswith('"""'):
        output = output[3:-3].strip()
    elif output.startswith("'") and output.endswith("'") and output.count('\n') > 1:
        output = output[1:-1].strip()
    elif output.startswith('"') and output.endswith('"') and output.count('\n') > 1:
        output = output[1:-1].strip()
    output = output.replace('\\n', '\n').replace('\\t', '\t')
    output = re.sub(r"^('?-{3,}'?\n)+", '', output)
    output = '---\n' + output.lstrip()
    output = output.rstrip() + '\n'
    return output

class CodeGeneratorAgent:
    """
    CodeGeneratorAgent following Meta's pattern - Direct LlamaStack API calls only
    """
    def __init__(self, client: LlamaStackClient, agent_id: str, session_id: str, timeout: int = 60):
        self.client = client
        self.agent_id = agent_id
        self.session_id = session_id  # Default session
        self.timeout = timeout
        self.logger = logger
        self.logger.info(f"🔧 CodeGeneratorAgent initialized with agent_id: {agent_id}")

    def create_new_session(self, correlation_id: str) -> str:
        """Create a new session for this specific generation request"""
        try:
            response = self.client.agents.session.create(
                agent_id=self.agent_id,
                session_name=f"code-generation-{correlation_id}-{uuid.uuid4()}",
            )
            session_id = response.session_id
            self.logger.info(f" Created new session: {session_id} for correlation: {correlation_id}")
            return session_id
        except Exception as e:
            self.logger.error(f" Failed to create session: {e}")
            # Fallback to default session
            self.logger.info(f"↩️  Falling back to default session: {self.session_id}")
            return self.session_id

    async def generate(self, input_code: str, context: Optional[str] = "", correlation_id: Optional[str] = None) -> str:
        """Generate Ansible playbook from input code and context"""
        correlation_id = correlation_id or str(uuid.uuid4())
        
        prompt = (
            f"[CONTEXT]\n{context or ''}\n\n"
            f"[INPUT CODE]\n{input_code}\n\n"
            "Convert the above into a single production-quality Ansible playbook. "
            "Output only the YAML (no Markdown, no code fences, no extra document markers). "
            "Start with '---'."
        )
        
        self.logger.info(f"🔧 Generating playbook for: {repr(input_code)[:100]}...")
        
        try:
            # Create dedicated session for this generation
            generation_session_id = self.create_new_session(correlation_id)

            # Direct API call following Meta's pattern
            messages = [UserMessage(role="user", content=prompt)]
            
            generator = self.client.agents.turn.create(
                agent_id=self.agent_id,
                session_id=generation_session_id,
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
                raise RuntimeError("No turn completed in generation")

            # Log steps for debugging
            self.logger.info(f" Turn completed with {len(turn.steps)} steps")
            for i, step in enumerate(turn.steps):
                self.logger.info(f"📋 Step {i+1}: {step.step_type}")

            # Extract output
            output = turn.output_message.content
            
            if not output:
                self.logger.error(" LLM returned empty output")
                raise RuntimeError("LLM returned empty output")
            
            # Clean and format the playbook
            cleaned_output = _clean_playbook_output(output)
            
            self.logger.info(f" Generated playbook: {len(cleaned_output)} chars")
            return cleaned_output
            
        except Exception as e:
            self.logger.error(f" Playbook generation failed: {str(e)}")
            raise RuntimeError(f"Playbook generation failed: {str(e)}")

    async def generate_stream(self, input_code: str, context: Optional[str] = "", correlation_id: Optional[str] = None):
        """Generate playbook with streaming updates"""
        correlation_id = correlation_id or str(uuid.uuid4())
        
        try:
            yield {
                "type": "progress",
                "status": "processing",
                "message": "🔧 Code generation started",
                "agent_info": {
                    "agent_id": self.agent_id,
                    "correlation_id": correlation_id
                }
            }

            result = await self.generate(input_code, context, correlation_id)
            
            yield {
                "type": "final_playbook",
                "data": {
                    "playbook": result,
                    "correlation_id": correlation_id,
                    "session_info": {
                        "agent_id": self.agent_id
                    }
                }
            }
        except Exception as e:
            yield {
                "type": "error",
                "error": str(e),
                "correlation_id": correlation_id
            }

    def get_status(self) -> Dict[str, Any]:
        """Get current status of the code generator agent"""
        return {
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "client_base_url": self.client.base_url,
            "timeout": self.timeout,
            "status": "ready",
            "pattern": "Meta Direct API"
        }

    async def health_check(self) -> bool:
        """Perform a health check on the code generator agent"""
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
            
            self.logger.info(" Code generator health check passed")
            return True
        except Exception as e:
            self.logger.error(f" Code generator health check failed: {e}")
            return False