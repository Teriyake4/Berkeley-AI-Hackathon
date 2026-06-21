"""
Nos — Python FastAPI backend.

Replaces the Next.js API routes (app/api/) and lib/ backend logic.
The Next.js frontend proxies all /api/* requests to this server.

Run with:
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""
from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Load .env from the repo root (parent of this backend/ directory)
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(_env_path)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agents.runtime import ensure_agents_started, stop_all_agents
from routes import router as api_router
from routes.vision import router as vision_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start all agents on server boot; stop them on shutdown."""
    await ensure_agents_started()
    logger.info("[main] Nos Python backend ready")
    yield
    await stop_all_agents()
    logger.info("[main] Nos Python backend shutdown")


app = FastAPI(
    title="Nos API",
    description="Real-time prehospital AI assistant backend — scene to hospital handoff",
    version="1.0.0",
    lifespan=lifespan,
)

# Allow the Next.js dev server (port 3000) and any other origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(vision_router)


@app.get("/")
async def root():
    return {"service": "nos-backend", "status": "ok"}
