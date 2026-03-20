"""
Main FastAPI application entry point.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import routes
from app.routes import health, game, negotiation, config

# Import services to initialize them
from app.services.ai_client import openai_client, deepseek_client, ai_provider
from app.services.config_service import load_negotiation_config

app = FastAPI(title="Fashion Supply Chain", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(health.router)
app.include_router(game.router)
app.include_router(negotiation.router)
app.include_router(config.router)

# Load config on startup
load_negotiation_config()
    