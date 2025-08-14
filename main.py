import logging
import uuid
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from routes.chef import router as chef_router
from routes.context import router as context_router
from routes.generate import router as generate_router
from routes.vector_db import router as vector_db_router
from routes.files import router as files_router
from routes.validate import router as validate_router

from agents.agent import AgentManager
from config.config import ConfigLoader
from agents.context_agent.context_agent import ContextAgent
from agents.code_generator.code_generator_agent import CodeGeneratorAgent

from routes.files import set_upload_dir
from routes.vector_db import set_vector_db_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("main")

# Initialize config loader with error handling
try:
    config_loader = ConfigLoader("config.yaml")
    llamastack_base_url = config_loader.get_llamastack_base_url()
    agents_config = config_loader.get_agents_config()
except Exception as e:
    logger.error(f"Failed to load configuration: {e}")
    raise RuntimeError(f"Configuration loading failed: {e}")

from llama_stack_client import LlamaStackClient, RAGDocument
from llama_stack_client.types.agent_create_params import AgentConfig
from pathlib import Path
import os

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
                    logger.info(f"Found existing agent: {agent_name} with ID: {agent_id}")
                    return agent_id
        except Exception as e:
            logger.warning(f"Error checking existing agents: {e}")
        logger.info(f"No existing agent found for: {agent_name}")
        return None

    async def get_or_create_agent(self, agent_config_dict: dict) -> str:
        agent_name = agent_config_dict["name"]
        logger.info(f"Processing agent creation request for: {agent_name}")
        
        # === DEBUG: Log the full config being processed ===
        logger.info(f"Agent config keys: {list(agent_config_dict.keys())}")
        logger.info(f"Tools in config: {agent_config_dict.get('tools', [])}")
        logger.info(f"Toolgroups in config: {agent_config_dict.get('toolgroups', [])}")
        logger.info(f"Tool config: {agent_config_dict.get('tool_config', {})}")
        
        if not agent_name or agent_name.lower() in ['none', 'null', '']:
            raise ValueError(f"Agent name cannot be None/empty: {agent_name}")
        if agent_name in self.agents:
            logger.info(f"Reusing locally registered agent: {agent_name}")
            return self.agents[agent_name]
        existing_agent_id = self.get_existing_agent_by_name(agent_name)
        if existing_agent_id:
            self.agents[agent_name] = existing_agent_id
            self.agent_configs[agent_name] = agent_config_dict
            logger.info(f"Registered existing LlamaStack agent: {agent_name}")
            return existing_agent_id
        
        logger.info(f"Creating new agent: {agent_name}")
        
        # === DEBUG: Log what we're about to pass to AgentConfig ===
        tools_to_pass = agent_config_dict.get("tools", [])
        toolgroups_to_pass = agent_config_dict.get("toolgroups", [])
        tool_config_to_pass = agent_config_dict.get("tool_config", {})
        
        logger.info(f"Passing to AgentConfig - Tools: {tools_to_pass}")
        logger.info(f"Passing to AgentConfig - Toolgroups: {toolgroups_to_pass}")
        logger.info(f"Passing to AgentConfig - Tool config: {tool_config_to_pass}")
        
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
        logger.info(f"AgentConfig created with tools: {getattr(agent_config, 'tools', 'NOT_SET')}")
        logger.info(f"AgentConfig created with toolgroups: {getattr(agent_config, 'toolgroups', 'NOT_SET')}")
        
        try:
            response = self.client.agents.create(agent_config=agent_config)
            agent_id = response.agent_id
            self._verify_agent_creation(agent_id, agent_name)
            self.agents[agent_name] = agent_id
            self.agent_configs[agent_name] = agent_config_dict
            logger.info(f"Created and registered new agent: {agent_name} with ID: {agent_id}")
            
            # === DEBUG: Verify the created agent has tools ===
            try:
                import httpx
                verify_response = httpx.get(f"{self.client.base_url}/v1/agents/{agent_id}", timeout=10)
                if verify_response.status_code == 200:
                    agent_data = verify_response.json()
                    actual_tools = agent_data.get("agent_config", {}).get("client_tools", [])
                    actual_toolgroups = agent_data.get("agent_config", {}).get("toolgroups", [])
                    logger.info(f"Verified agent {agent_name} - Tools: {actual_tools}")
                    logger.info(f"Verified agent {agent_name} - Toolgroups: {actual_toolgroups}")
                else:
                    logger.warning(f"Could not verify agent {agent_name} - HTTP {verify_response.status_code}")
            except Exception as ve:
                logger.warning(f"Could not verify agent {agent_name}: {ve}")
            
            return agent_id
        except Exception as e:
            logger.error(f"Failed to create agent {agent_name}: {e}")
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
                        logger.info(f"Agent name verified: {expected_name}")
                        return True
                    else:
                        logger.warning(f"Agent name mismatch: expected '{expected_name}', got '{actual_name}'")
                        return False
            logger.warning(f"Could not find created agent {agent_id} in list")
            return False
        except Exception as e:
            logger.warning(f"Could not verify agent creation: {e}")
            return False

    def create_session(self, agent_name: str) -> str:
        if agent_name not in self.agents:
            raise ValueError(f"Agent {agent_name} not registered")
        agent_id = self.agents[agent_name]
        if agent_name in self.sessions:
            logger.info(f"Reusing existing session for agent: {agent_name}")
            return self.sessions[agent_name]
        try:
            response = self.client.agents.session.create(
                agent_id=agent_id,
                session_name=f"Session-{agent_name}-{uuid.uuid4()}",
            )
            session_id = response.session_id
            self.sessions[agent_name] = session_id
            logger.info(f"Created session {session_id} for agent: {agent_name}")
            return session_id
        except Exception as e:
            logger.error(f"Failed to create session for agent {agent_name}: {e}")
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

def _vector_db_exists(client: LlamaStackClient, vector_db_id: str) -> bool:
    """Check if vector DB exists - following agentic RAG pattern"""
    try:
        if hasattr(client.vector_dbs, "get"):
            client.vector_dbs.get(vector_db_id=vector_db_id)
            return True
        lst = client.vector_dbs.list()
        items = lst.get("data", lst) if isinstance(lst, dict) else lst
        if isinstance(items, list):
            for it in items:
                if isinstance(it, dict):
                    vid = it.get("vector_db_id") or it.get("id") or it.get("identifier")
                    if vid == vector_db_id:
                        return True
            return False
        return False
    except Exception as e:
        msg = str(e).lower()
        if "404" in msg or "not found" in msg:
            return False
        logger.warning("Vector DB existence check inconclusive: %s", e)
        return False

def _ensure_vector_db(client: LlamaStackClient, vector_db_id: str = "iac"):
    """Ensure vector DB exists - following agentic RAG pattern"""
    try:
        # Try to register vector DB - LlamaStack will handle if it exists
        payload = {
            "vector_db_id": vector_db_id,
            "embedding_model": "all-MiniLM-L6-v2",  # Default embedding model
            "embedding_dimension": 384,  # Default dimension for all-MiniLM-L6-v2
            "provider_id": "faiss",  # Use faiss provider instead
        }
        
        client.vector_dbs.register(**payload)
        logger.info("Vector DB '%s' registered successfully", vector_db_id)
        return True
        
    except Exception as e:
        # Check if it's just because it already exists
        if "already exists" in str(e).lower() or "conflict" in str(e).lower():
            logger.info("Vector DB '%s' already exists", vector_db_id)
            return True
        else:
            logger.error("Failed to register Vector DB '%s': %s", vector_db_id, e)
            return False

def _ingest_startup_documents(client: LlamaStackClient, vector_db_id: str = "iac"):
    """Ingest documents from uploads directory at startup - following agentic RAG pattern"""
    try:
        upload_dir = Path("uploads")
        if not upload_dir.exists():
            logger.info("No uploads directory found, skipping document ingestion")
            return
        
        documents = []
        
        # Find and process documents from uploads
        for file_path in upload_dir.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in ['.rb', '.yml', '.yaml', '.json', '.tf', '.pp', '.py', '.md', '.txt']:
                try:
                    content = file_path.read_text(encoding='utf-8')
                    if content.strip():  # Only add non-empty files
                        relative_path = str(file_path.relative_to(upload_dir))
                        documents.append({
                            "document_id": f"startup-{relative_path.replace('/', '-')}",
                            "content": content,
                            "mime_type": "text/plain",
                            "metadata": {
                                "file_path": relative_path,
                                "file_name": file_path.name,
                                "file_extension": file_path.suffix,
                                "source": "startup_ingestion",
                                "upload_directory": str(upload_dir)
                            }
                        })
                        logger.info(f"Prepared for ingestion: {relative_path}")
                except Exception as e:
                    logger.warning(f"Could not read {file_path}: {e}")
        
        if not documents:
            logger.info("No documents found for ingestion")
            return
        
        # Convert to RAGDocument format
        rag_documents = []
        for doc in documents:
            rag_doc = RAGDocument(
                document_id=doc["document_id"],
                content=doc["content"],
                mime_type=doc["mime_type"],
                metadata=doc["metadata"]
            )
            rag_documents.append(rag_doc)
        
        # Ingest using RAG tool
        client.tool_runtime.rag_tool.insert(
            documents=rag_documents,
            vector_db_id=vector_db_id,
            chunk_size_in_tokens=512
        )
        
        logger.info(f"Successfully ingested {len(rag_documents)} documents into vector DB '{vector_db_id}'")
        
    except Exception as e:
        logger.error(f"Document ingestion failed: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent_registry
    logger.info("Starting X2A Agents API ...")

    try:
        client = LlamaStackClient(base_url=llamastack_base_url)
        agent_registry = AgentRegistry(client)
        app.state.client = client
        app.state.agent_registry = agent_registry
        app.state.config_loader = config_loader

        logger.info(f"Connected to LlamaStack: {llamastack_base_url}")
    except Exception as e:
        logger.error(f"Failed to connect to LlamaStack: {e}")
        raise RuntimeError(f"LlamaStack connection failed: {e}")
    
    # === DEBUG SECTION - Add this to see what's happening ===
    logger.info("Loading agent configurations...")
    agents_config = config_loader.get_agents_config()
    logger.info(f"Total agents found in config.yaml: {len(agents_config)}")
    
    for i, agent_config in enumerate(agents_config):
        agent_name = agent_config.get("name", "UNNAMED")
        logger.info(f"Agent {i+1}/{len(agents_config)}: {agent_name}")
        
    logger.info("Starting agent registration...")
    
    # Verify LlamaStack before registration
    logger.info("Checking existing agents in LlamaStack...")
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
        
        logger.info(f"Existing agents in LlamaStack: {len(agents_data)}")
        for agent in agents_data:
            agent_config = agent.get("agent_config", {})
            agent_name = agent_config.get("name", "UNNAMED")
            agent_id = agent.get("agent_id", "NO_ID")
            logger.info(f"   Existing: {agent_name} (ID: {agent_id[:8]}...)")
            
    except Exception as e:
        logger.warning(f"Could not check existing LlamaStack agents: {e}")

    registered_agents = {}

    # Register LlamaStack agents with error handling
    for i, agent_config in enumerate(agents_config):
        agent_name = agent_config["name"]
        logger.info(f"Setting up agent {i+1}/{len(agents_config)}: {agent_name}...")
        try:
            agent_id = await agent_registry.get_or_create_agent(agent_config)
            session_id = agent_registry.create_session(agent_name)
            registered_agents[agent_name] = {
                "agent_id": agent_id,
                "session_id": session_id,
                "config": agent_config
            }
            logger.info(f"Agent {i+1}/{len(agents_config)} ready: {agent_name} (ID: {agent_id})")
        except Exception as e:
            logger.error(f"Failed to setup agent {i+1}/{len(agents_config)}: {agent_name} - {e}")
            # Don't raise here - continue with other agents
            continue

    # === FINAL VERIFICATION ===
    logger.info(f"Registration Summary:")
    logger.info(f"   Agents in config: {len(agents_config)}")
    logger.info(f"   Agents registered: {len(registered_agents)}")
    logger.info(f"   Registered agent names: {list(registered_agents.keys())}")
    
    # Check LlamaStack again after registration
    logger.info("Final verification - agents in LlamaStack...")
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
        
        logger.info(f"Total agents in LlamaStack after registration: {len(agents_data)}")
        for agent in agents_data:
            agent_config = agent.get("agent_config", {})
            agent_name = agent_config.get("name", "UNNAMED")
            agent_id = agent.get("agent_id", "NO_ID")
            created_by = "US" if agent_name in registered_agents else "OTHER"
            logger.info(f"   {created_by}: {agent_name} (ID: {agent_id[:8]}...)")
        
    except Exception as e:
        logger.warning(f"Could not verify final LlamaStack agents: {e}")

    app.state.registered_agents = registered_agents
    
    # Initialize AgentManager with error handling
    try:
        agent_manager = AgentManager(llamastack_base_url)
        app.state.agent_manager = agent_manager
    except Exception as e:
        logger.warning(f"Failed to initialize AgentManager: {e}")
        app.state.agent_manager = None

    # === Setup ChefAnalysisAgent with prompt template ===
    chef_agent_name = None
    if "chef_analysis" in registered_agents:
        chef_agent_name = "chef_analysis"
    elif "chef_analysis_chaining" in registered_agents:
        chef_agent_name = "chef_analysis_chaining"

    if chef_agent_name:
        try:
            from agents.chef_analysis.agent import ChefAnalysisAgent
            chef_info = registered_agents[chef_agent_name]
            chef_prompt_template = config_loader.config.get("prompts", {}).get("chef_analysis_enhanced")
            chef_instructions = config_loader.config.get("agent_instructions", {}).get("chef_analysis")
            
            if not chef_prompt_template or not chef_instructions:
                logger.warning("ChefAnalysisAgent missing prompt template or instructions in config.yaml - skipping")
                app.state.chef_analysis_agent = None
            else:
                chef_agent = ChefAnalysisAgent(
                    client=client,
                    agent_id=chef_info["agent_id"],
                    session_id=chef_info["session_id"],
                    instruction=chef_instructions,
                    enhanced_prompt_template=chef_prompt_template,
                )
                app.state.chef_analysis_agent = chef_agent
                logger.info(f"ChefAnalysisAgent ready: agent_id={chef_info['agent_id']}")
        except Exception as e:
            logger.warning(f"Failed to setup ChefAnalysisAgent: {e}")
            app.state.chef_analysis_agent = None
    else:
        logger.warning("chef_analysis agent not found in config!")
        app.state.chef_analysis_agent = None

    # === Setup ContextAgent - AGENTIC RAG PATTERN ===
    try:
        # Extract vector DB ID from config (fallback to default)
        vector_db_id = "iac"  # Default vector DB ID
        if "context" in registered_agents:
            context_info = registered_agents["context"]
            context_config = context_info["config"]
            vector_db_id = extract_vector_db_id(context_config, default="iac")
            logger.info(f"Using vector DB ID from config: {vector_db_id}")
        else:
            logger.info(f"No context agent in config, using default vector DB: {vector_db_id}")
        
        # Create ContextAgent with own Agent instance (agentic RAG pattern)
        app.state.context_agent = ContextAgent(
            client=client,
            vector_db_id=vector_db_id
        )
        logger.info(f"ContextAgent ready with agentic RAG pattern: vector_db={vector_db_id}")
        
        # === VECTOR DB SETUP AND INGESTION (STARTUP) ===
        logger.info("Setting up vector database and ingesting documents...")
        
        # Ensure vector DB exists
        vector_db_ready = _ensure_vector_db(client, vector_db_id)
        
        if vector_db_ready:
            # Ingest documents from uploads directory
            _ingest_startup_documents(client, vector_db_id)
            logger.info(f"Vector DB setup and ingestion completed for: {vector_db_id}")
        else:
            logger.warning(f"Vector DB setup failed for: {vector_db_id}")
        
    except Exception as e:
        logger.warning(f"Failed to setup ContextAgent: {e}")
        app.state.context_agent = None
    
    # === Setup CodeGeneratorAgent with prompt/instructions from config ===
    if "generate" in registered_agents:
        try:
            codegen_info = registered_agents["generate"]
            codegen_prompt = config_loader.config.get("prompts", {}).get("generate")
            codegen_instructions = config_loader.config.get("agent_instructions", {}).get("generate")
            
            if not codegen_prompt or not codegen_instructions:
                logger.warning("CodeGeneratorAgent missing prompt template or instructions in config.yaml - skipping")
                app.state.codegen_agent = None
            else:
                app.state.codegen_agent = CodeGeneratorAgent(
                    client=client,
                    agent_id=codegen_info["agent_id"],
                    session_id=codegen_info["session_id"],
                    config_loader=config_loader
                )
                logger.info(f"CodeGeneratorAgent ready: agent_id={codegen_info['agent_id']}")
        except Exception as e:
            logger.warning(f"Failed to setup CodeGeneratorAgent: {e}")
            app.state.codegen_agent = None
    else:
        logger.warning("generate agent not found in config!")
        app.state.codegen_agent = None
    

        
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
    logger.info(f"File upload directory: {upload_dir}")

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
        logger.info(f"Vector DB ready: {default_db_id}")
    except Exception as e:
        logger.warning(f"Vector DB setup failed: {e}")

    logger.info("X2A Agents API startup complete")

    yield

    logger.info("Shutting down X2A Agents API")

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

app.include_router(chef_router, prefix="/api")
app.include_router(context_router, prefix="/api")
app.include_router(generate_router, prefix="/api")
app.include_router(vector_db_router, prefix="/api")
app.include_router(files_router, prefix="/api")
app.include_router(validate_router, prefix="/api")

@app.get("/")
async def root():
    registry_status = agent_registry.get_status() if agent_registry else {}
    registered_info = getattr(app.state, 'registered_agents', {})
    
    # Add context agent status for debugging
    context_status = {}
    if hasattr(app.state, 'context_agent'):
        try:
            context_status = app.state.context_agent.get_status()
        except Exception as e:
            context_status = {"error": str(e)}
    
    return {
        "status": "ok",
        "message": "Welcome to X2A multi-agent API",
        "agents": list(registered_info.keys()),
        "registry_status": registry_status,
        "agent_pattern": "Registry-based (Chef, Context, Generate)",
        "context_agent_status": context_status,
    }