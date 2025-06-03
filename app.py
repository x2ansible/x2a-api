from fastapi import FastAPI
from agents.chef_analysis.routes import router as chef_router

app = FastAPI()
app.include_router(chef_router)
