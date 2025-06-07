import logging
import os
import json
import uuid
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from routes.admin import router as admin_router
from routes.chef import router as chef_router
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
    """Complete  Agent Registry - Prevents duplicates for ALL agents"""
    def __init__(self, client: LlamaStackClient):
        self.client = client
        self.agents = {}  # agent_name -> agent_id
        self.sessions = {}  # agent_name -> session_id
        self.agent_configs = {}  # agent_name -> config for comparison
        
    def get_existing_agent_by_name(self, agent_name: str) -> str:
        """Check if agent with this name already exists in LlamaStack"""
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
                
                # Match by actual name, ignore None/null agents
                if existing_name and existing_name == agent_name:
                    agent_id = agent.get("agent_id")
                    logger.info(f" Found existing agent: {agent_name} with ID: {agent_id}")
                    return agent_id
                    
        except Exception as e:
            logger.warning(f"Error checking existing agents: {e}")
        
        logger.info(f"🔍 No existing agent found for: {agent_name}")
        return None
    
    async def get_or_create_agent(self, agent_config_dict: dict) -> str:
        """Get or create agent with proper name handling - NO DUPLICATES"""
        agent_name = agent_config_dict["name"]
        
        # Validate agent name
        if not agent_name or agent_name.lower() in ['none', 'null', '']:
            raise ValueError(f"Agent name cannot be None/empty: {agent_name}")
        
        # Check local registry first
        if agent_name in self.agents:
            logger.info(f"♻️  Reusing locally registered agent: {agent_name}")
            return self.agents[agent_name]
        
        # Check if agent exists in LlamaStack
        existing_agent_id = self.get_existing_agent_by_name(agent_name)
        if existing_agent_id:
            # Register the existing agent locally
            self.agents[agent_name] = existing_agent_id
            self.agent_configs[agent_name] = agent_config_dict
            logger.info(f"📝 Registered existing LlamaStack agent: {agent_name}")
            return existing_agent_id
        
        # Create new agent with explicit name
        logger.info(f"🆕 Creating new agent: {agent_name}")
        
        # Build AgentConfig with explicit name
        agent_config = AgentConfig(
            name=agent_name,  # CRITICAL: Explicit name
            model=agent_config_dict["model"],
            instructions=agent_config_dict["instructions"],
            sampling_params=agent_config_dict.get("sampling_params"),
            max_infer_iters=agent_config_dict.get("max_infer_iters"),
            toolgroups=agent_config_dict.get("toolgroups", []),
            tools=agent_config_dict.get("tools", []),
            enable_session_persistence=True,
        )
        
        try:
            response = self.client.agents.create(agent_config=agent_config)
            agent_id = response.agent_id
            
            # Verify the agent was created properly
            self._verify_agent_creation(agent_id, agent_name)
            
            # Register locally to prevent future duplicates
            self.agents[agent_name] = agent_id
            self.agent_configs[agent_name] = agent_config_dict
            
            logger.info(f" Created and registered new agent: {agent_name} with ID: {agent_id}")
            return agent_id
            
        except Exception as e:
            logger.error(f" Failed to create agent {agent_name}: {e}")
            raise
    
    def _verify_agent_creation(self, agent_id: str, expected_name: str):
        """Verify agent was created with correct name"""
        try:
            # Quick verification by listing all agents and finding this one
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
        """Create session for agent"""
        if agent_name not in self.agents:
            raise ValueError(f"Agent {agent_name} not registered")
            
        agent_id = self.agents[agent_name]
        
        # Check if we already have a session
        if agent_name in self.sessions:
            logger.info(f"♻️  Reusing existing session for agent: {agent_name}")
            return self.sessions[agent_name]
        
        try:
            response = self.client.agents.session.create(
                agent_id=agent_id,
                session_name=f"Session-{agent_name}-{uuid.uuid4()}",
            )
            session_id = response.session_id
            self.sessions[agent_name] = session_id
            
            logger.info(f" Created session {session_id} for agent: {agent_name}")
            return session_id
            
        except Exception as e:
            logger.error(f" Failed to create session for agent {agent_name}: {e}")
            raise
    
    def get_agent_id(self, agent_name: str) -> str:
        """Get agent ID by name"""
        if agent_name not in self.agents:
            raise ValueError(f"Agent {agent_name} not registered")
        return self.agents[agent_name]
    
    def get_session_id(self, agent_name: str) -> str:
        """Get session ID by agent name"""
        if agent_name not in self.sessions:
            return self.create_session(agent_name)
        return self.sessions[agent_name]
    
    def get_status(self) -> dict:
        """Get registry status"""
        return {
            "registered_agents": len(self.agents),
            "active_sessions": len(self.sessions),
            "agents": dict(self.agents),  # Show name -> ID mapping
            "sessions": dict(self.sessions)  # Show name -> session mapping
        }

# Global registry instance
agent_registry = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent_registry
    
    logger.info("🚀 Starting X2A Agents API...")
    
    # Initialize single client and registry
    client = LlamaStackClient(base_url=llamastack_base_url)
    agent_registry = AgentRegistry(client)
    app.state.client = client
    app.state.agent_registry = agent_registry
    
    logger.info(f"🔗 Connected to LlamaStack: {llamastack_base_url}")

    # === Register ALL agents through AgentRegistry () ===
    logger.info("🤖 Registering all agents ...")
    
    registered_agents = {}
    
    for agent_config in agents_config:
        agent_name = agent_config["name"]
        logger.info(f"🔧 Setting up {agent_name} agent...")
        
        try:
            # Register agent through registry (prevents duplicates)
            agent_id = await agent_registry.get_or_create_agent(agent_config)
            session_id = agent_registry.create_session(agent_name)
            
            registered_agents[agent_name] = {
                "agent_id": agent_id,
                "session_id": session_id,
                "config": agent_config
            }
            
            logger.info(f" {agent_name} agent ready: agent_id={agent_id}")
            
        except Exception as e:
            logger.error(f" Failed to setup {agent_name} agent: {e}")
            raise

    # Store registered agents for routes to access
    app.state.registered_agents = registered_agents
    
    # Keep AgentManager for backward compatibility (but don't use it for registration)
    agent_manager = AgentManager(llamastack_base_url)
    app.state.agent_manager = agent_manager

    # === Setup ChefAnalysisAgent ===
    if "chef_analysis" in registered_agents:
        from agents.chef_analysis.agent import ChefAnalysisAgent
        
        chef_info = registered_agents["chef_analysis"]
        app.state.chef_analysis_agent = ChefAnalysisAgent(
            client=client,
            agent_id=chef_info["agent_id"],
            session_id=chef_info["session_id"]
        )
        logger.info(f"🍳 ChefAnalysisAgent ready: agent_id={chef_info['agent_id']}")
    else:
        logger.error(" chef_analysis agent not found in config!")

    # === Setup ContextAgent ===
    if "context" in registered_agents:
        
        context_info = registered_agents["context"]
        context_config = context_info["config"]
        
        # Extract vector DB ID from context agent tools
        vector_db_id = "iac"  # default fallback
        for tool in context_config.get("tools", []):
            if tool["name"] == "builtin::rag":
                vector_db_ids = tool["args"]["vector_db_ids"]
                vector_db_id = vector_db_ids[0] if vector_db_ids else "iac"
                break
        
        app.state.context_agent = ContextAgent(
            client=client,
            agent_id=context_info["agent_id"],
            session_id=context_info["session_id"],
            vector_db_id=vector_db_id
        )
        logger.info(f"🔍 ContextAgent ready: agent_id={context_info['agent_id']}")
    else:
        logger.warning("⚠️ context agent not found in config!")

    # === Setup CodeGeneratorAgent ===
    if "generate" in registered_agents:
        
        codegen_info = registered_agents["generate"]
        app.state.codegen_agent = CodeGeneratorAgent(
            client=client,
            agent_id=codegen_info["agent_id"],
            session_id=codegen_info["session_id"]
        )
        logger.info(f"🔧 CodeGeneratorAgent ready: agent_id={codegen_info['agent_id']}")
    else:
        logger.warning("⚠️ generate agent not found in config!")

    # === Setup ValidationAgent ===
    if "validate" in registered_agents:
        
        
        validation_info = registered_agents["validate"]
        app.state.validation_agent = ValidationAgent(
            client=client,
            agent_id=validation_info["agent_id"],
            session_id=validation_info["session_id"]
        )
        logger.info(f"🔍 ValidationAgent ready: agent_id={validation_info['agent_id']}")
    else:
        logger.warning("⚠️ validate agent not found in config!")

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

    logger.info(" X2A Agents API startup complete!")
    
    yield
    
    # Cleanup on shutdown
    logger.info("🛑 Shutting down X2A Agents API")

app = FastAPI(
    title="X2A Agents API",
    version="1.0.0", 
    description="Multi-agent IaC API - Complete  (No Duplicates for ALL agents)",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict for prod!
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin_router, prefix="/api")
app.include_router(chef_router, prefix="/api")
app.include_router(context_router, prefix="/api")
app.include_router(files_router, prefix="/api")
app.include_router(generate_router, prefix="/api")
app.include_router(validate_router, prefix="/api")
app.include_router(vector_db_router, prefix="/api")

@app.get("/")
async def root():
    registry_status = agent_registry.get_status() if agent_registry else {}
    registered_info = getattr(app.state, 'registered_agents', {})
    
    return {
        "status": "ok",
        "message": " Welcome to X2A multi-agent API - Complete !",
        "agents": list(registered_info.keys()),
        "registry_status": registry_status,
        "agent_pattern": "LSS API",
        "duplicate_prevention": "Active for ALL agents",
        "services": [
            "admin - Agent management",
            "chef - Chef cookbook analysis",
            "context - Knowledge search", 
            "files - File upload/management",
            "generate - Code generation",
            "validate - Playbook validation",
            "vector-db - Vector database management"
        ]
    }

@app.get("/api/agents/status")
async def get_agents_status():
    """Get detailed status for ALL agents"""
    if not agent_registry:
        return {"error": "Agent registry not initialized"}
    
    registry_status = agent_registry.get_status()
    registered_info = getattr(app.state, 'registered_agents', {})
    
    # Get individual agent statuses
    agent_details = {}
    for agent_name, info in registered_info.items():
        agent_details[agent_name] = {
            "agent_id": info["agent_id"],
            "session_id": info["session_id"],
            "status": "ready",
            "pattern": "LSS API"
        }
    
    # Add specialized agent info
    specialized_agents = {}
    if hasattr(app.state, 'chef_analysis_agent'):
        specialized_agents["chef_analysis"] = {
            "type": "ChefAnalysisAgent",
            "status": app.state.chef_analysis_agent.get_status()
        }
    
    if hasattr(app.state, 'context_agent'):
        specialized_agents["context"] = {
            "type": "ContextAgent", 
            "status": app.state.context_agent.get_status()
        }
    
    return {
        "registry": registry_status,
        "agents": agent_details,
        "specialized_agents": specialized_agents,
        "llamastack_url": llamastack_base_url,
        "pattern": "Complete ",
        "duplicate_prevention": "Active for ALL agents",
        "summary": {
            "total_agents": len(registry_status["agents"]),
            "active_sessions": len(registry_status["sessions"]),
            "specialized_wrappers": len(specialized_agents)
        }
    }

@app.post("/api/agents/cleanup")
async def cleanup_duplicate_agents():
    """Manually trigger duplicate agent cleanup"""
    try:
        import subprocess
        import os
        
        script_path = os.path.join("shared", "agent_manager.py")
        if os.path.exists(script_path):
            result = subprocess.run([
                "python", script_path, 
                "--delete-duplicates", 
                "--llamastack-url", llamastack_base_url
            ], capture_output=True, text=True)
            
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr if result.returncode != 0 else None,
                "message": "Cleanup completed - restart application to see effects"
            }
        else:
            return {"error": "Cleanup script not found"}
            
    except Exception as e:
        return {"error": f"Cleanup failed: {str(e)}"}