"""
Vision route — live webcam frame ingestion.

POST /api/vision  { "frame_base64": str, "encounterId"?: str }

The browser POSTs a base64 JPEG frame; the vision agent calls Claude vision and
publishes vision.captured for confident identifications. Registered in main.py
via its own app.include_router(vision_router).
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from agents.runtime import ensure_agents_started
from agents.vision import handle_vision_frame
from redis_layer.keys import ENCOUNTER_ID

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/api/vision")
async def scan_frame(request: Request):
    await ensure_agents_started()

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    if not isinstance(body, dict):
        return JSONResponse({"error": "frame_base64 required"}, status_code=400)

    frame_base64 = body.get("frame_base64")
    if not frame_base64 or not isinstance(frame_base64, str):
        return JSONResponse({"error": "frame_base64 required"}, status_code=400)

    encounter_id = body.get("encounterId") or ENCOUNTER_ID

    result = await handle_vision_frame(frame_base64, encounter_id)
    return JSONResponse(result)
