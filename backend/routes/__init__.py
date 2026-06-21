"""
Consolidated API routes — mirrors app/api/ endpoints.

All routes are defined here and registered in main.py via app.include_router().
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from agents.runtime import ensure_agents_started
from bus import get_event_bus
from demo.injector import is_demo_running, run_demo_scenario, stop_demo
from events import EVENT_CHANNELS
from redis_layer.client import is_redis_available, ping_redis
from redis_layer.keys import ENCOUNTER_ID
from redis_layer.state import (
    append_transcript_line,
    finalize_active_session,
    finalize_session,
    get_encounter_snapshot,
    list_sessions,
    start_pending_session,
    reset_encounter,
)
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
                    "key present — agents use Claude (NIM fallback if set)"
                    if os.environ.get("ANTHROPIC_API_KEY")
                    else "no key — agents use NIM or heuristic fallbacks"
                ),
            },
            "nvidia_nim": {
                "configured": bool(
                    os.environ.get("NVIDIA_API_KEY") or os.environ.get("NIM_API_KEY")
                ),
                "note": (
                    "key present — fallback LLM via NVIDIA NIM"
                    if os.environ.get("NVIDIA_API_KEY") or os.environ.get("NIM_API_KEY")
                    else "no key — no NIM fallback"
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
    await finalize_active_session()

    encounter_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc).isoformat()

    await start_pending_session(encounter_id, mode)
    await reset_encounter(encounter_id)
    stop_demo(encounter_id)

    if mode == "demo":
        bus = get_event_bus()
        asyncio.create_task(_run_demo(bus, encounter_id))

    return JSONResponse({
        "encounterId": encounter_id,
        "mode": mode,
        "status": "started",
        "startedAt": started_at,
    })


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
    await finalize_session(encounter_id)
    return JSONResponse({"encounterId": encounter_id, "status": "completed"})


# ── Sessions (log history) ──────────────────────────────────────────────────

@router.get("/api/sessions")
async def get_sessions():
    sessions = await list_sessions()
    return JSONResponse({"sessions": sessions})


@router.get("/api/sessions/{encounter_id}")
async def get_session_snapshot(encounter_id: str):
    snapshot = await get_encounter_snapshot(encounter_id)
    if snapshot is None:
        return JSONResponse({"error": "session not found"}, status_code=404)
    return JSONResponse(snapshot)


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
    await append_transcript_line(encounter_id, speaker, text, timestamp)

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


# ── Audio event (manual stub for live mode) ─────────────────────────────────

@router.post("/api/audio-event")
async def post_audio_event(request: Request):
    await ensure_agents_started()

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    encounter_id: str = body.get("encounterId") or ENCOUNTER_ID
    event_type: str = body.get("type", "")
    detail: str | None = body.get("detail")

    if not event_type:
        return JSONResponse({"error": "type required"}, status_code=400)

    bus = get_event_bus()
    await bus.publish(EVENT_CHANNELS.AUDIO_EVENT, {
        "encounterId": encounter_id,
        "type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "detail": detail,
    })

    return JSONResponse({"ok": True})


# ── Telemetry (manual stub for live mode) ───────────────────────────────────

@router.post("/api/telemetry")
async def post_telemetry(request: Request):
    await ensure_agents_started()

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    encounter_id: str = body.get("encounterId") or ENCOUNTER_ID
    event: str = body.get("event", "")
    label: str | None = body.get("label")

    if not event:
        return JSONResponse({"error": "event required"}, status_code=400)

    bus = get_event_bus()
    await bus.publish(EVENT_CHANNELS.TELEMETRY_UPDATED, {
        "encounterId": encounter_id,
        "event": event,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "label": label,
    })

    return JSONResponse({"ok": True})
