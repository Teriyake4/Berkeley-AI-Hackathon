"""
Consolidated API routes — mirrors app/api/ endpoints.

All routes are defined here and registered in main.py via app.include_router().
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from agents.runtime import ensure_agents_started, stop_all_agents
from bus import get_event_bus
from demo.injector import is_demo_running, run_demo_scenario, stop_demo
from events import EVENT_CHANNELS
from redis_layer.client import is_redis_available, ping_redis
from redis_layer.keys import ENCOUNTER_ID
from redis_layer.state import append_transcript, reset_encounter
from sse.hub import add_sse_client, get_client_count, remove_sse_client

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Status ──────────────────────────────────────────────────────────────────

@router.get("/api/status")
async def status():
    redis_ok = await ping_redis()

    return JSONResponse({
        "ok": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {
            "redis": {
                "configured": is_redis_available(),
                "connected": redis_ok,
                "note": "connected" if redis_ok else "using in-memory fallback",
            },
            "deepgram": {
                "configured": bool(os.environ.get("DEEPGRAM_API_KEY")),
                "note": (
                    "key present — live mic uses Deepgram"
                    if os.environ.get("DEEPGRAM_API_KEY")
                    else "no key — live mic uses Web Speech API fallback"
                ),
            },
            "anthropic": {
                "configured": bool(os.environ.get("ANTHROPIC_API_KEY")),
                "note": (
                    "key present — agents use Claude"
                    if os.environ.get("ANTHROPIC_API_KEY")
                    else "no key — agents use heuristic fallbacks"
                ),
            },
            "browserbase": {
                "configured": bool(os.environ.get("BROWSERBASE_API_KEY")),
                "note": (
                    "key present — research agent active"
                    if os.environ.get("BROWSERBASE_API_KEY")
                    else "no key — research uses mock citations"
                ),
            },
        },
        "sse": {
            "connectedClients": get_client_count(),
        },
    })


# ── Deepgram ────────────────────────────────────────────────────────────────

@router.get("/api/deepgram")
async def get_deepgram_key():
    key = os.environ.get("DEEPGRAM_API_KEY")
    if not key:
        return JSONResponse({"error": "Deepgram not configured"}, status_code=503)
    return JSONResponse({"key": key})


# ── Events (SSE) ───────────────────────────────────────────────────────────

@router.get("/api/events")
async def events():
    await ensure_agents_started()

    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    add_sse_client(queue)

    async def event_generator() -> AsyncGenerator[str, None]:
        yield f"data: {json.dumps({'channel': 'connected', 'payload': {'ok': True}})}\n\n"

        try:
            while True:
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        except asyncio.CancelledError:
            pass
        except GeneratorExit:
            pass
        finally:
            remove_sse_client(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Encounter ───────────────────────────────────────────────────────────────

@router.post("/api/encounter")
async def start_encounter(request: Request):
    await ensure_agents_started()

    try:
        body = await request.json()
    except Exception:
        body = {}

    mode = "live" if body.get("mode") == "live" else "demo"
    encounter_id: str = body.get("encounterId") or ENCOUNTER_ID

    await reset_encounter(encounter_id)
    stop_demo(encounter_id)

    if mode == "demo":
        bus = get_event_bus()
        asyncio.create_task(_run_demo(bus, encounter_id))

    return JSONResponse({"encounterId": encounter_id, "mode": mode, "status": "started"})


async def _run_demo(bus, encounter_id: str) -> None:
    try:
        await run_demo_scenario(bus, encounter_id)
    except Exception as e:
        if str(e) != "aborted":
            logger.error("[encounter] demo error: %s", e)


@router.get("/api/encounter")
async def get_encounter(encounterId: str = ENCOUNTER_ID):
    return JSONResponse({
        "encounterId": encounterId,
        "demoRunning": is_demo_running(encounterId),
    })


@router.delete("/api/encounter")
async def delete_encounter(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    encounter_id: str = body.get("encounterId") or ENCOUNTER_ID
    stop_demo(encounter_id)
    await reset_encounter(encounter_id)
    return JSONResponse({"encounterId": encounter_id, "status": "reset"})


# ── Transcript ──────────────────────────────────────────────────────────────

@router.post("/api/transcript")
async def post_transcript(request: Request):
    await ensure_agents_started()

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    encounter_id: str = body.get("encounterId") or ENCOUNTER_ID
    text: str = body.get("text", "")
    speaker: str = body.get("speaker") or "unknown"

    if not text.strip():
        return JSONResponse({"error": "text required"}, status_code=400)

    timestamp = datetime.now(timezone.utc).isoformat()
    await append_transcript(encounter_id, f"[{speaker}] {text}")

    bus = get_event_bus()
    await bus.publish(EVENT_CHANNELS.TRANSCRIPT_SEGMENT, {
        "encounterId": encounter_id,
        "text": text,
        "speaker": speaker,
        "timestamp": timestamp,
    })

    return JSONResponse({"ok": True})


@router.get("/api/transcript")
async def get_deepgram_key_from_transcript():
    key = os.environ.get("DEEPGRAM_API_KEY")
    if not key:
        return JSONResponse({"error": "Deepgram not configured"}, status_code=503)
    return JSONResponse({"key": key})


# ── Handoff ─────────────────────────────────────────────────────────────────

@router.post("/api/handoff")
async def request_handoff(request: Request):
    await ensure_agents_started()

    try:
        body = await request.json()
    except Exception:
        body = {}

    encounter_id: str = body.get("encounterId") or ENCOUNTER_ID

    bus = get_event_bus()
    await bus.publish(EVENT_CHANNELS.HANDOFF_REQUESTED, {
        "encounterId": encounter_id,
        "requestedAt": datetime.now(timezone.utc).isoformat(),
    })

    return JSONResponse({"encounterId": encounter_id, "status": "handoff_requested"})
