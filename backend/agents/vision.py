"""
Vision agent — live webcam path.

A browser POSTs a base64 JPEG frame to /api/vision. This module calls Claude
vision and, for high/medium-confidence identifications, publishes a
vision.captured event to the event bus. The safety agent already subscribes to
vision.captured and performs the cross-check / merge (see agents/safety.py).

If ANTHROPIC_API_KEY is missing or the Claude call fails, we return a graceful
"none" result and DO NOT publish — keeping the demo injector as the source of
truth.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Callable

from bus import InMemoryBus, RedisBus, get_event_bus
from events import (
    EVENT_CHANNELS,
    Medication,
    entities_from_dict,
    to_dict,
)
from llm_parse import parse_json_from_llm_text
from prompts.vision import VISION_PROMPT, to_capture_type
from redis_layer.keys import ENCOUNTER_ID, EncounterKeys
from redis_layer.state import load_json, save_json

logger = logging.getLogger(__name__)

_SAFE_DEFAULT = {
    "identified": False,
    "type": "none",
    "label_text": None,
    "confidence": "low",
}

_DATA_URL_PREFIX = "data:image/jpeg;base64,"

_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            import anthropic
            _client = anthropic.AsyncAnthropic(api_key=api_key)
    return _client


def _strip_data_url(frame_base64: str) -> str:
    if not frame_base64:
        return ""
    stripped = frame_base64.strip()
    if stripped.startswith("data:"):
        comma = stripped.find(",")
        if comma != -1:
            return stripped[comma + 1:]
    return stripped


async def identify_frame(frame_base64: str) -> dict:
    """
    Call Claude vision on a base64 JPEG frame. Returns the parsed JSON dict,
    or a safe default on any failure (never raises).
    """
    client = _get_client()
    if not client:
        return dict(_SAFE_DEFAULT)

    data = _strip_data_url(frame_base64)
    if not data:
        return dict(_SAFE_DEFAULT)

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": data,
                        },
                    },
                    {"type": "text", "text": VISION_PROMPT},
                ],
            }],
        )

        raw = ""
        if response.content and response.content[0].type == "text":
            raw = response.content[0].text.strip()

        parsed = parse_json_from_llm_text(raw)
        if not isinstance(parsed, dict):
            return dict(_SAFE_DEFAULT)

        # Normalize against the safe default so callers always get all keys.
        result = dict(_SAFE_DEFAULT)
        result.update({
            "identified": bool(parsed.get("identified", False)),
            "type": parsed.get("type") or "none",
            "label_text": parsed.get("label_text"),
            "confidence": parsed.get("confidence") or "low",
        })
        return result

    except Exception as e:
        logger.warning("[vision] identify_frame error: %s", e)
        return dict(_SAFE_DEFAULT)


async def handle_vision_frame(frame_base64: str, encounter_id: str) -> dict:
    """
    Identify a frame and, when it is a confident, non-"none" identification,
    publish vision.captured to the event bus (the safety agent stores & cross-
    checks it). Returns the raw identification result dict either way.
    """
    enc = encounter_id or ENCOUNTER_ID
    result = await identify_frame(frame_base64)

    confidence = (result.get("confidence") or "low").lower()
    vtype = (result.get("type") or "none").lower()
    identified_flag = bool(result.get("identified"))

    if identified_flag and vtype != "none" and confidence in ("high", "medium"):
        label_text = result.get("label_text")
        identified_text = label_text if label_text else vtype
        payload = {
            "encounterId": enc,
            "identified": identified_text,
            "captureType": to_capture_type(vtype),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if label_text:
            payload["rawText"] = label_text

        try:
            bus = get_event_bus()
            await bus.publish(EVENT_CHANNELS.VISION_CAPTURED, payload)
        except Exception as e:
            logger.warning("[vision] publish vision.captured failed: %s", e)

    return result


# ─── Vision agent: merge identified meds into entities ──────────────────────────
#
# The safety agent (Dev B) already subscribes to vision.captured for the
# interaction cross-check. THIS agent handles the other half of the spec —
# "merges into entities" — so a camera-identified medication also flows into the
# live extracted facts (EXTRACTED chips, SOAP, research, re-check). It runs for
# BOTH the live /api/vision path and the demo injector, since both publish
# vision.captured. The med is tagged source="vision" so the handoff can show its
# camera provenance.

async def start_vision_agent(bus: InMemoryBus | RedisBus) -> Callable[[], None]:
    async def on_vision_captured(envelope: dict) -> None:
        payload = envelope.get("payload", {})
        encounter_id = payload.get("encounterId", "") or ENCOUNTER_ID
        identified = (payload.get("identified") or "").strip()
        capture_type = (payload.get("captureType") or "").lower()

        # Only medication vials feed the entities/medication list.
        if not identified or capture_type != "vial_label":
            return

        facts_raw = await load_json(EncounterKeys.facts(encounter_id))
        # If extraction hasn't produced facts yet, seed an empty entity set so
        # the camera finding isn't lost.
        entities = entities_from_dict(facts_raw or {})

        if any(m.name.lower() == identified.lower() for m in entities.medications):
            return  # already known — nothing to merge

        entities.medications.append(Medication(name=identified, source="vision"))
        await save_json(EncounterKeys.facts(encounter_id), to_dict(entities))

        # Republish facts so downstream agents (safety re-check, documentation,
        # research, timeline) and the dashboard pick up the camera-found med.
        await bus.publish(EVENT_CHANNELS.FACTS_EXTRACTED, {
            "encounterId": encounter_id,
            "entities": to_dict(entities),
            "extractedAt": datetime.now(timezone.utc).isoformat(),
        })

    return await bus.subscribe(EVENT_CHANNELS.VISION_CAPTURED, on_vision_captured)
