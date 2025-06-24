import logging
import os
import json
import uuid
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from routes.admin import router as admin_router
from routes.chef import router as chef_router
from routes.bladelogic import router as bladelogic_router
from routes.shell import router as shell_router
from routes.salt import router as salt_router
from routes.context import router as context_router
from routes.files import router as files_router
from routes.generate import router as generate_router
from routes.validate import router as validate_router
from routes.vector_db import router as vector_db_router

from agents.agent import AgentManager
from config.config import ConfigLoader
from agents.context_agent.context_agent import ContextAgent
from agents.code_generator.code_generator_agent import CodeGeneratorAgent
from agents.validate.validate_agent import ValidationAgent
from routes.files import set_upload_dir
from routes.vector_db import set_vector_db_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("main")

config_loader = ConfigLoader("config.yaml")
llamastack_base_url = config_loader.get_llamastack_base_url()
agents_config = config_loader.get_agents_config()

from llama_stack_client import LlamaStackClient
from llama_stack_client.types.agent_create_params import AgentConfig

class AgentRegistry:
    def __init__(self, client: LlamaStackClient):
        self.client = client
        self.agents = {}
        self.sessions = {}
        self.agent_configs = {}

    def get_existing_agent_by_name(self, agent_name: str) -> str:
        try:
            if hasattr(self.client.agents, "list"):
                response = self.client.agents.list()
                agents_data = response.data if hasattr(response, 'data') else response
            else:
                import httpx
                response = httpx.get(f"{self.client.base_url}/v1/agents", timeout=30)
                response.raise_for_status()
                data = response.json()
                agents_data = data.get("data", [])
            for agent in agents_data:
                agent_config = agent.get("agent_config", {})
                existing_name = agent_config.get("name")
                if existing_name and existing_name == agent_name:
                    agent_id = agent.get("agent_id")
                    logger.info(f"🔍 Found existing agent: {agent_name} with ID: {agent_id}")
                    return agent_id
        except Exception as e:
            logger.warning(f"Error checking existing agents: {e}")
        logger.info(f"🔍 No existing agent found for: {agent_name}")
        return None

    async def get_or_create_agent(self, agent_config_dict: dict) -> str:
        agent_name = agent_config_dict["name"]
        logger.info(f"🔍 Processing agent creation request for: {agent_name}")
        
        # === DEBUG: Log the full config being processed ===
        logger.info(f"🔧 Agent config keys: {list(agent_config_dict.keys())}")
        logger.info(f"🔧 Tools in config: {agent_config_dict.get('tools', [])}")
        logger.info(f"🔧 Toolgroups in config: {agent_config_dict.get('toolgroups', [])}")
        logger.info(f"🔧 Tool config: {agent_config_dict.get('tool_config', {})}")
        
        if not agent_name or agent_name.lower() in ['none', 'null', '']:
            raise ValueError(f"Agent name cannot be None/empty: {agent_name}")
        if agent_name in self.agents:
            logger.info(f"♻️ Reusing locally registered agent: {agent_name}")
            return self.agents[agent_name]
        existing_agent_id = self.get_existing_agent_by_name(agent_name)
        if existing_agent_id:
            self.agents[agent_name] = existing_agent_id
            self.agent_configs[agent_name] = agent_config_dict
            logger.info(f"📝 Registered existing LlamaStack agent: {agent_name}")
            return existing_agent_id
        
        logger.info(f"🆕 Creating new agent: {agent_name}")
        
        # === DEBUG: Log what we're about to pass to AgentConfig ===
        tools_to_pass = agent_config_dict.get("tools", [])
        toolgroups_to_pass = agent_config_dict.get("toolgroups", [])
        tool_config_to_pass = agent_config_dict.get("tool_config", {})
        
        logger.info(f"🔧 Passing to AgentConfig - Tools: {tools_to_pass}")
        logger.info(f"🔧 Passing to AgentConfig - Toolgroups: {toolgroups_to_pass}")
        logger.info(f"🔧 Passing to AgentConfig - Tool config: {tool_config_to_pass}")
        
        agent_config = AgentConfig(
            name=agent_name,
            model=agent_config_dict["model"],
            instructions=agent_config_dict["instructions"],
            sampling_params=agent_config_dict.get("sampling_params"),
            max_infer_iters=agent_config_dict.get("max_infer_iters"),
            toolgroups=toolgroups_to_pass,
            tools=tools_to_pass,
            tool_config=tool_config_to_pass,
            enable_session_persistence=True,
        )
        
        # === DEBUG: Log the AgentConfig object ===
        logger.info(f"🔧 AgentConfig created with tools: {getattr(agent_config, 'tools', 'NOT_SET')}")
        logger.info(f"🔧 AgentConfig created with toolgroups: {getattr(agent_config, 'toolgroups', 'NOT_SET')}")
        
        try:
            response = self.client.agents.create(agent_config=agent_config)
            agent_id = response.agent_id
            self._verify_agent_creation(agent_id, agent_name)
            self.agents[agent_name] = agent_id
            self.agent_configs[agent_name] = agent_config_dict
            logger.info(f" Created and registered new agent: {agent_name} with ID: {agent_id}")
            
            # === DEBUG: Verify the created agent has tools ===
            try:
                import httpx
                verify_response = httpx.get(f"{self.client.base_url}/v1/agents/{agent_id}", timeout=10)
                if verify_response.status_code == 200:
                    agent_data = verify_response.json()
                    actual_tools = agent_data.get("agent_config", {}).get("client_tools", [])
                    actual_toolgroups = agent_data.get("agent_config", {}).get("toolgroups", [])
                    logger.info(f" Verified agent {agent_name} - Tools: {actual_tools}")
                    logger.info(f" Verified agent {agent_name} - Toolgroups: {actual_toolgroups}")
                else:
                    logger.warning(f"⚠️ Could not verify agent {agent_name} - HTTP {verify_response.status_code}")
            except Exception as ve:
                logger.warning(f"⚠️ Could not verify agent {agent_name}: {ve}")
            
            return agent_id
        except Exception as e:
            logger.error(f" Failed to create agent {agent_name}: {e}")
            raise

    def _verify_agent_creation(self, agent_id: str, expected_name: str):
        try:
            if hasattr(self.client.agents, "list"):
                response = self.client.agents.list()
                agents_data = response.data if hasattr(response, 'data') else response
            else:
                import httpx
                response = httpx.get(f"{self.client.base_url}/v1/agents", timeout=30)
                response.raise_for_status()
                data = response.json()
                agents_data = data.get("data", [])
            for agent in agents_data:
                if agent.get("agent_id") == agent_id:
                    actual_name = agent.get("agent_config", {}).get("name")
                    if actual_name == expected_name:
                        logger.info(f" Agent name verified: {expected_name}")
                        return True
                    else:
                        logger.warning(f"⚠️ Agent name mismatch: expected '{expected_name}', got '{actual_name}'")
                        return False
            logger.warning(f"⚠️ Could not find created agent {agent_id} in list")
            return False
        except Exception as e:
            logger.warning(f"⚠️ Could not verify agent creation: {e}")
            return False

    def create_session(self, agent_name: str) -> str:
        if agent_name not in self.agents:
            raise ValueError(f"Agent {agent_name} not registered")
        agent_id = self.agents[agent_name]
        if agent_name in self.sessions:
            logger.info(f"♻️ Reusing existing session for agent: {agent_name}")
            return self.sessions[agent_name]
        try:
            response = self.client.agents.session.create(
                agent_id=agent_id,
                session_name=f"Session-{agent_name}-{uuid.uuid4()}",
            )
            session_id = response.session_id
            self.sessions[agent_name] = session_id
            logger.info(f"📱 Created session {session_id} for agent: {agent_name}")
            return session_id
        except Exception as e:
            logger.error(f" Failed to create session for agent {agent_name}: {e}")
            raise

    def get_agent_id(self, agent_name: str) -> str:
        if agent_name not in self.agents:
            raise ValueError(f"Agent {agent_name} not registered")
        return self.agents[agent_name]

    def get_session_id(self, agent_name: str) -> str:
        if agent_name not in self.sessions:
            return self.create_session(agent_name)
        return self.sessions[agent_name]

    def get_status(self) -> dict:
        return {
            "registered_agents": len(self.agents),
            "active_sessions": len(self.sessions),
            "agents": dict(self.agents),
            "sessions": dict(self.sessions)
        }

def extract_vector_db_id(agent_config: dict, default: str = "iac") -> str:
    """
    Extract vector DB ID from agent config, supporting both tools and toolgroups.
    Falls back to default if not found.
    """
    # Try tools first (legacy format)
    tools = agent_config.get("tools", [])
    for tool in tools:
        if isinstance(tool, dict):
            tool_name = tool.get("name", "")
            if "rag" in tool_name:
                args = tool.get("args", {})
                vector_db_ids = args.get("vector_db_ids", [])
                if vector_db_ids:
                    return vector_db_ids[0]
    
    # For toolgroups (new format), use default since toolgroups handle config internally
    toolgroups = agent_config.get("toolgroups", [])
    for toolgroup in toolgroups:
        if "rag" in toolgroup:
            # Toolgroups don't expose vector_db_ids in config, use default
            return default
    
    # Fallback to default
    return default

agent_registry = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent_registry
    logger.info("🚀 Starting X2A Agents API ...")

    client = LlamaStackClient(base_url=llamastack_base_url)
    agent_registry = AgentRegistry(client)
    app.state.client = client
    app.state.agent_registry = agent_registry
    app.state.config_loader = config_loader

    logger.info(f"🔗 Connected to LlamaStack: {llamastack_base_url}")
    
    # === DEBUG SECTION - Add this to see what's happening ===
    logger.info("🤖 Loading agent configurations...")
    agents_config = config_loader.get_agents_config()
    logger.info(f"📊 Total agents found in config.yaml: {len(agents_config)}")
    
    for i, agent_config in enumerate(agents_config):
        agent_name = agent_config.get("name", "UNNAMED")
        logger.info(f"📝 Agent {i+1}/{len(agents_config)}: {agent_name}")
    
    logger.info("🤖 Starting agent registration...")

    # Verify LlamaStack before registration
    logger.info("🔍 Checking existing agents in LlamaStack...")
    try:
        if hasattr(client.agents, "list"):
            response = client.agents.list()
            agents_data = response.data if hasattr(response, 'data') else response
        else:
            import httpx
            response = httpx.get(f"{client.base_url}/v1/agents", timeout=30)
            response.raise_for_status()
            data = response.json()
            agents_data = data.get("data", [])
        
        logger.info(f"🌐 Existing agents in LlamaStack: {len(agents_data)}")
        for agent in agents_data:
            agent_config = agent.get("agent_config", {})
            agent_name = agent_config.get("name", "UNNAMED")
            agent_id = agent.get("agent_id", "NO_ID")
            logger.info(f"   🔸 Existing: {agent_name} (ID: {agent_id[:8]}...)")
            
    except Exception as e:
        logger.warning(f"⚠️ Could not check existing LlamaStack agents: {e}")

    registered_agents = {}

    for i, agent_config in enumerate(agents_config):
        agent_name = agent_config["name"]
        logger.info(f"🔧 Setting up agent {i+1}/{len(agents_config)}: {agent_name}...")
        try:
            agent_id = await agent_registry.get_or_create_agent(agent_config)
            session_id = agent_registry.create_session(agent_name)
            registered_agents[agent_name] = {
                "agent_id": agent_id,
                "session_id": session_id,
                "config": agent_config
            }
            logger.info(f" Agent {i+1}/{len(agents_config)} ready: {agent_name} (ID: {agent_id})")
        except Exception as e:
            logger.error(f" Failed to setup agent {i+1}/{len(agents_config)}: {agent_name} - {e}")
            raise

    # === FINAL VERIFICATION ===
    logger.info(f"📋 Registration Summary:")
    logger.info(f"   Agents in config: {len(agents_config)}")
    logger.info(f"   Agents registered: {len(registered_agents)}")
    logger.info(f"   Registered agent names: {list(registered_agents.keys())}")
    
    # Check LlamaStack again after registration
    logger.info("🔍 Final verification - agents in LlamaStack...")
    try:
        if hasattr(client.agents, "list"):
            response = client.agents.list()
            agents_data = response.data if hasattr(response, 'data') else response
        else:
            import httpx
            response = httpx.get(f"{client.base_url}/v1/agents", timeout=30)
            response.raise_for_status()
            data = response.json()
            agents_data = data.get("data", [])
        
        logger.info(f"🌐 Total agents in LlamaStack after registration: {len(agents_data)}")
        for agent in agents_data:
            agent_config = agent.get("agent_config", {})
            agent_name = agent_config.get("name", "UNNAMED")
            agent_id = agent.get("agent_id", "NO_ID")
            created_by = "US" if agent_name in registered_agents else "OTHER"
            logger.info(f"   🔸 {created_by}: {agent_name} (ID: {agent_id[:8]}...)")
            
    except Exception as e:
        logger.warning(f"⚠️ Could not verify final LlamaStack agents: {e}")

    app.state.registered_agents = registered_agents
    agent_manager = AgentManager(llamastack_base_url)
    app.state.agent_manager = agent_manager

    # === Setup ChefAnalysisAgent with prompt template ===
    chef_agent_name = None
    if "chef_analysis" in registered_agents:
        chef_agent_name = "chef_analysis"
    elif "chef_analysis_chaining" in registered_agents:
        chef_agent_name = "chef_analysis_chaining"

    if chef_agent_name:
        from agents.chef_analysis.agent import ChefAnalysisAgent
        chef_info = registered_agents[chef_agent_name]
        chef_prompt_template = config_loader.config.get("prompts", {}).get("chef_analysis_enhanced")
        chef_instructions = config_loader.config.get("agent_instructions", {}).get("chef_analysis")
        if not chef_prompt_template or not chef_instructions:
            logger.error(" ChefAnalysisAgent requires both prompt template and instructions in config.yaml!")
            raise RuntimeError("ChefAnalysisAgent requires both prompt template and instructions in config.yaml!")
        chef_agent = ChefAnalysisAgent(
            client=client,
            agent_id=chef_info["agent_id"],
            session_id=chef_info["session_id"],
            instruction=chef_instructions,
            enhanced_prompt_template=chef_prompt_template,
        )
        app.state.chef_analysis_agent = chef_agent
        logger.info(f"🍳 ChefAnalysisAgent ready: agent_id={chef_info['agent_id']}")
    else:
        logger.warning("⚠️ chef_analysis agent not found in config!")

    # === Setup BladeLogicAnalysisAgent ===
    if "bladelogic_analysis" in registered_agents:
        from agents.bladelogic_analysis.agent import BladeLogicAnalysisAgent
        bladelogic_info = registered_agents["bladelogic_analysis"]
        bladelogic_agent = BladeLogicAnalysisAgent(
            client=client,
            agent_id=bladelogic_info["agent_id"],
            session_id=bladelogic_info["session_id"]
        )
        app.state.bladelogic_analysis_agent = bladelogic_agent
        logger.info(f"🔧 BladeLogicAnalysisAgent ready: agent_id={bladelogic_info['agent_id']}")
    else:
        logger.warning("⚠️ bladelogic_analysis agent not found in config!")

    # === Setup ShellAnalysisAgent ===
    if "shell_analysis" in registered_agents:
        from agents.shell_analysis.agent import ShellAnalysisAgent
        shell_info = registered_agents["shell_analysis"]
        shell_agent = ShellAnalysisAgent(
            client=client,
            agent_id=shell_info["agent_id"],
            session_id=shell_info["session_id"],
            config_loader=config_loader
        )
        app.state.shell_analysis_agent = shell_agent
        logger.info(f"🐚 ShellAnalysisAgent ready: agent_id={shell_info['agent_id']}")
    else:
        logger.warning("⚠️ shell_analysis agent not found in config!")

    # === Setup SaltAnalysisAgent ===
    if "salt_analysis" in registered_agents:
        from agents.salt_analysis.agent import SaltAnalysisAgent
        salt_info = registered_agents["salt_analysis"]
        salt_agent = SaltAnalysisAgent(
            client=client,
            agent_id=salt_info["agent_id"],
            session_id=salt_info["session_id"],
            config_loader=config_loader
        )
        app.state.salt_analysis_agent = salt_agent
        logger.info(f"🧂 SaltAnalysisAgent ready: agent_id={salt_info['agent_id']}")
    else:
        logger.warning("⚠️ salt_analysis agent not found in config!")

    # === Setup ContextAgent - FIXED FOR TOOLGROUPS ===
    if "context" in registered_agents:
        context_info = registered_agents["context"]
        context_config = context_info["config"]
        
        # Extract vector DB ID with support for both tools and toolgroups
        vector_db_id = extract_vector_db_id(context_config, default="iac")
        
        logger.info(f"🔍 Context agent using vector DB: {vector_db_id}")
        logger.info(f"🔍 Context agent toolgroups: {context_config.get('toolgroups', [])}")
        logger.info(f"🔍 Context agent tools: {context_config.get('tools', [])}")
        
        # Use the registered agent with extracted vector DB ID
        app.state.context_agent = ContextAgent(
            client=client,
            agent_id=context_info["agent_id"],
            session_id=context_info["session_id"],
            vector_db_id=vector_db_id
        )
        logger.info(f"🔍 ContextAgent ready: agent_id={context_info['agent_id']}")
    else:
        logger.warning("⚠️ context agent not found in config!")

    # === Setup CodeGeneratorAgent with prompt/instructions from config ===
    if "generate" in registered_agents:
        codegen_info = registered_agents["generate"]
        codegen_prompt = config_loader.config.get("prompts", {}).get("generate")
        codegen_instructions = config_loader.config.get("agent_instructions", {}).get("generate")
        if not codegen_prompt or not codegen_instructions:
            logger.error(" CodeGeneratorAgent requires both prompt template and instructions in config.yaml!")
            raise RuntimeError("CodeGeneratorAgent requires both prompt template and instructions in config.yaml!")
        app.state.codegen_agent = CodeGeneratorAgent(
            client=client,
            agent_id=codegen_info["agent_id"],
            session_id=codegen_info["session_id"],
            config_loader=config_loader
        )
        logger.info(f"🔧 CodeGeneratorAgent ready: agent_id={codegen_info['agent_id']}")
    else:
        logger.warning("⚠️ generate agent not found in config!")

    # === Setup ValidationAgent with enhanced error handling and validation ===
    if "validate" in registered_agents:
        validation_info = registered_agents["validate"]
        validation_prompt = config_loader.config.get("prompts", {}).get("validate")
        validation_instructions = config_loader.config.get("agent_instructions", {}).get("validate")
        
        if not validation_prompt:
            logger.error(" ValidationAgent missing 'prompts.validate' in config.yaml!")
            raise RuntimeError("ValidationAgent requires 'prompts.validate' template in config.yaml!")
        
        if not validation_instructions:
            logger.error(" ValidationAgent missing 'agent_instructions.validate' in config.yaml!")
            raise RuntimeError("ValidationAgent requires 'agent_instructions.validate' in config.yaml!")
        
        agent_config = validation_info.get("config", {})
        toolgroups = agent_config.get("toolgroups", [])
        if "mcp::ansible_lint" not in toolgroups:
            logger.warning("⚠️ ValidationAgent missing 'mcp::ansible_lint' toolgroup - tool calling may not work!")
        
        logger.info(f"🔧 ValidationAgent toolgroups: {toolgroups}")
        
        try:
            app.state.validation_agent = ValidationAgent(
                client=client,
                agent_id=validation_info["agent_id"],
                session_id=validation_info["session_id"],
                prompt_template=validation_prompt,
                instruction=validation_instructions,
                verbose_logging=True,
                timeout=120
            )
            logger.info(f"🔍 ValidationAgent ready: agent_id={validation_info['agent_id']}")
            
        except Exception as e:
            logger.error(f" Failed to initialize ValidationAgent: {e}")
            raise RuntimeError(f"ValidationAgent initialization failed: {e}")
            
    else:
        logger.error(" validate agent not found in config!")
        raise RuntimeError("ValidationAgent configuration missing from config.yaml!")

    # --- File upload directory setup ---
    upload_dir = os.getenv("UPLOAD_DIR")
    if not upload_dir:
        try:
            file_config = config_loader.config.get("file_storage", {})
            upload_dir = file_config.get("upload_dir", "./uploads")
        except Exception as e:
            logger.warning(f"Could not read file_storage config: {e}")
            upload_dir = "./uploads"
    upload_dir = os.path.abspath(upload_dir)
    os.makedirs(upload_dir, exist_ok=True)
    set_upload_dir(upload_dir)
    logger.info(f"📁 File upload directory: {upload_dir}")

    # --- Vector DB client setup ---
    try:
        vector_config = config_loader.config.get("vector_db", {})
        default_db_id = vector_config.get("default_db_id")
        default_chunk_size = vector_config.get("default_chunk_size", 512)
        set_vector_db_client(
            injected_client=client,
            default_vector_db_id=default_db_id,
            default_chunk_size=default_chunk_size
        )
        logger.info(f"🗄️ Vector DB ready: {default_db_id}")
    except Exception as e:
        logger.warning(f"⚠️ Vector DB setup failed: {e}")

    logger.info(" X2A Agents API startup complete")

    yield

    logger.info("🛑 Shutting down X2A Agents API")

app = FastAPI(
    title="X2A Agents API",
    version="1.0.0",
    description="Multi-agent IaC API",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin_router, prefix="/api")
app.include_router(chef_router, prefix="/api")
app.include_router(bladelogic_router, prefix="/api")
app.include_router(shell_router, prefix="/api")
app.include_router(salt_router, prefix="/api")
app.include_router(context_router, prefix="/api")
app.include_router(files_router, prefix="/api")
app.include_router(generate_router, prefix="/api")
app.include_router(validate_router, prefix="/api")
app.include_router(vector_db_router, prefix="/api")

@app.get("/")
async def root():
    registry_status = agent_registry.get_status() if agent_registry else {}
    registered_info = getattr(app.state, 'registered_agents', {})
    
    # Add validation agent status for debugging
    validation_status = {}
    if hasattr(app.state, 'validation_agent'):
        try:
            validation_status = app.state.validation_agent.get_status()
        except Exception as e:
            validation_status = {"error": str(e)}
    
    # Add shell agent status for debugging
    shell_status = {}
    if hasattr(app.state, 'shell_analysis_agent'):
        try:
            shell_status = app.state.shell_analysis_agent.get_status()
        except Exception as e:
            shell_status = {"error": str(e)}
    
    # Add salt agent status for debugging
    salt_status = {}
    if hasattr(app.state, 'salt_analysis_agent'):
        try:
            salt_status = app.state.salt_analysis_agent.get_status()
        except Exception as e:
            salt_status = {"error": str(e)}
    
    # Add context agent status for debugging
    context_status = {}
    if hasattr(app.state, 'context_agent'):
        try:
            context_status = app.state.context_agent.get_status()
        except Exception as e:
            context_status = {"error": str(e)}
    
    return {
        "status": "ok",
        "message": " Welcome to X2A multi-agent API",
        "agents": list(registered_info.keys()),
        "registry_status": registry_status,
        "agent_pattern": "Registry-based (All agents including Salt and Shell)",
        "validation_agent_status": validation_status,
        "shell_agent_status": shell_status,
        "salt_agent_status": salt_status,
        "context_agent_status": context_status,
    }