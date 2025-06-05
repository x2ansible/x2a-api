import logging
import re
from typing import Optional

from llama_stack_client import Agent, LlamaStackClient
from llama_stack_client.types import UserMessage
from config.config import ConfigLoader

logger = logging.getLogger("CodeGeneratorAgent")

def _clean_playbook_output(output: str) -> str:
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
    LlamaStack-based agent for Ansible playbook generation.
    Loads its instructions from config, hot-reloads on config change, and
    robustly parses/cleans LLM output to always return usable playbook.
    """
    def __init__(
        self, 
        config_loader: ConfigLoader, 
        agent_id: str = "generate",  # matches your config.yaml!
        timeout: int = 60
    ):
        self.config_loader = config_loader
        self.agent_id = agent_id
        all_agents = self.config_loader.get_agents_config()
        agent_cfg = next((a for a in all_agents if a.get("name") == self.agent_id), {})
        self.base_url = self.config_loader.get_llamastack_base_url()
        self.model_id = agent_cfg.get("model") or "meta-llama/Llama-3.1-8B-Instruct"
        self.timeout = timeout
        self._last_instructions_hash = None
        self.agent = None
        self._initialize_agent()
        logger.info(f"CodeGeneratorAgent initialized with model: {self.model_id}")

    def _get_current_instructions(self):
        instructions = self.config_loader.get_agent_instructions(self.agent_id)
        if not instructions:
            logger.warning("No codegen instructions found, using fallback.")
            return (
                "You are an expert in Ansible. "
                "Given INPUT CODE and CONTEXT, generate a single, production-ready Ansible playbook. "
                "Use YAML comments for any essential explanation. "
                "Output only the playbook and YAML comments—"
                "do NOT use Markdown code blocks or code fences (e.g., no triple backticks). "
                "Your response must start with '---' and contain no extra blank lines at the start or end."
            )
        return instructions

    def _initialize_agent(self):
        current_instructions = self._get_current_instructions()
        self.client = LlamaStackClient(base_url=self.base_url)
        self.agent = Agent(
            client=self.client,
            model=self.model_id,
            instructions=current_instructions,
        )
        self._last_instructions_hash = hash(current_instructions)

    def _check_and_reload_config(self):
        try:
            current_instructions = self._get_current_instructions()
            current_hash = hash(current_instructions)
            if current_hash != self._last_instructions_hash:
                logger.info("CodeGeneratorAgent instructions changed, reloading agent.")
                self._initialize_agent()
        except Exception as e:
            logger.error(f"Failed to check/reload codegen agent config: {e}")

    async def generate(self, input_code: str, context: Optional[str] = "") -> str:
        self._check_and_reload_config()
        prompt = (
            f"[CONTEXT]\n{context}\n\n"
            f"[INPUT CODE]\n{input_code}\n\n"
            "Convert the above into a single production-quality Ansible playbook. "
            "Output only the YAML (no Markdown, no code fences, no extra document markers). "
            "Start with '---'."
        )
        try:
            session_id = self.agent.create_session("code_generation")
            turn = self.agent.create_turn(
                session_id=session_id,
                messages=[UserMessage(role="user", content=prompt)],
                stream=False,
            )
            output = None
            if hasattr(turn, 'output_message') and hasattr(turn.output_message, 'content'):
                output = turn.output_message.content
            elif hasattr(turn, 'content'):
                output = turn.content
            elif isinstance(turn, str):
                output = turn
            else:
                output = ""
                if hasattr(turn, 'steps') and turn.steps:
                    for step in turn.steps:
                        if hasattr(step, 'content'):
                            output += str(step.content)
                        elif hasattr(step, 'output'):
                            output += str(step.output)
                if not output.strip():
                    output = str(turn)
            output = _clean_playbook_output(str(output))
            if not output:
                raise RuntimeError("LLM returned empty output")
            return output
        except Exception as e:
            logger.exception(f"Error in CodeGeneratorAgent.generate: {e}")
            raise RuntimeError(f"Playbook generation failed: {str(e)}")


def create_codegen_agent(config_loader: Optional[ConfigLoader] = None):
    if config_loader is None:
        config_loader = ConfigLoader("config.yaml")
    return CodeGeneratorAgent(config_loader)
