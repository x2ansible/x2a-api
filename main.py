import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from routes.chef import router as chef_router
from routes.context import router as context_router
from routes.generate import router as generate_router
from agents.agent import AgentManager
from config.config import ConfigLoader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

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

app = FastAPI(title="X2A Agents API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict for prod!
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(chef_router)
app.include_router(context_router)
app.include_router(generate_router)


@app.get("/")
async def root():
    return {"status": "ok", "agents": list(agent_manager.registered_agents.keys())}
