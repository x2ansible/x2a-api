import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from routes.admin import router as admin_router
from routes.chef import router as chef_router
from routes.context import router as context_router
from routes.generate import router as generate_router
from routes.validate import router as validate_router
from agents.agent import AgentManager
from config.config import ConfigLoader

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("main")

# -- ConfigLoader and AgentManager are fully config-driven --
config_loader = ConfigLoader("config.yaml")
llamastack_base_url = config_loader.get_llamastack_base_url()
agents_config = config_loader.get_agents_config()
agent_manager = AgentManager(llamastack_base_url)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Registering agents with LlamaStack server ...")
    await agent_manager.ensure_agents(agents_config)
    app.state.agent_manager = agent_manager
    logger.info(f"Registered agents: {agent_manager.registered_agents}")
    yield

app = FastAPI(
    title="X2A Agents API",
    version="1.0.0",
    description="Multi-agent IaC API (Chef, Context, Generate, Validate).",
    lifespan=lifespan
)

# -- CORS: for prod, lock down origins! --
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict for prod!
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -- Include routers from the agent packages --
app.include_router(admin_router)
app.include_router(chef_router)
app.include_router(context_router)
app.include_router(generate_router)
app.include_router(validate_router)

@app.get("/")
async def root():
    # Show registered agent names from the AgentManager
    return {
        "status": "ok",
        "agents": list(agent_manager.registered_agents.keys()),
        "message": "Welcome to the X2A multi-agent API!"
    }
