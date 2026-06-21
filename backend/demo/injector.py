"""
Demo scenario injector — mirrors lib/demo/injector.ts.
Replays demo-scenario.json beats on a timer using asyncio.
Supports beat types: transcript, telemetry, audio, vision.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from bus import InMemoryBus, RedisBus
from events import EVENT_CHANNELS
from redis_layer.state import append_transcript

logger = logging.getLogger(__name__)

_active_injectors: Dict[str, asyncio.Event] = {}


def stop_demo(encounter_id: str) -> None:
    event = _active_injectors.get(encounter_id)
    if event:
        event.set()
        _active_injectors.pop(encounter_id, None)


def is_demo_running(encounter_id: str) -> bool:
    return encounter_id in _active_injectors


def _load_scenario() -> Dict[str, Any]:
    scenario_path = Path(__file__).parent.parent.parent / "scripts" / "demo-scenario.json"
    try:
        with open(scenario_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error("[demo] failed to load demo-scenario.json: %s", e)
        return {
            "encounterId": "demo-encounter-001",
            "beats": [
                {"id": "b1", "delayMs": 0, "type": "transcript", "speaker": "paramedic",
                 "text": "Ma'am, I'm with county EMS. What happened?"},
                {"id": "b2", "delayMs": 4000, "type": "transcript", "speaker": "patient",
                 "text": "Chest pain for two hours. I take warfarin."},
                {"id": "b3", "delayMs": 9000, "type": "transcript", "speaker": "paramedic",
                 "text": "Any allergies? Shortness of breath?"},
                {"id": "b4", "delayMs": 13000, "type": "transcript", "speaker": "patient",
                 "text": "Penicillin allergy. A little short of breath, left arm pain."},
            ],
        }


async def run_demo_scenario(bus: InMemoryBus | RedisBus, encounter_id: str) -> None:
    stop_demo(encounter_id)

    abort_event = asyncio.Event()
    _active_injectors[encounter_id] = abort_event

    scenario = _load_scenario()
    beats: List[Dict[str, Any]] = scenario.get("beats", [])

    logger.info("[demo] starting replay for %s (%d beats)", encounter_id, len(beats))

    elapsed = 0
    for beat in beats:
        if abort_event.is_set():
            logger.info("[demo] replay aborted")
            return

        wait_ms = beat.get("delayMs", 0) - elapsed
        if wait_ms > 0:
            try:
                await asyncio.wait_for(
                    asyncio.shield(asyncio.ensure_future(abort_event.wait())),
                    timeout=wait_ms / 1000.0,
                )
                logger.info("[demo] replay aborted during wait")
                return
            except asyncio.TimeoutError:
                pass

        elapsed = beat.get("delayMs", 0)
        if abort_event.is_set():
            return

        timestamp = datetime.now(timezone.utc).isoformat()
        beat_type = beat.get("type", "transcript")
        beat_id = beat.get("id", "?")

        try:
            if beat_type == "transcript":
                speaker = beat.get("speaker", "unknown")
                text = beat.get("text", "")
                await append_transcript(encounter_id, f"[{speaker}] {text}")
                await bus.publish(EVENT_CHANNELS.TRANSCRIPT_SEGMENT, {
                    "encounterId": encounter_id,
                    "text": text,
                    "speaker": speaker,
                    "timestamp": timestamp,
                })
                logger.debug("[demo] beat %s [transcript] %s: %s", beat_id, speaker, text[:60])

            elif beat_type == "telemetry":
                await bus.publish(EVENT_CHANNELS.TELEMETRY_UPDATED, {
                    "encounterId": encounter_id,
                    "event": beat.get("event", ""),
                    "timestamp": timestamp,
                    "label": beat.get("label"),
                })
                logger.debug("[demo] beat %s [telemetry] %s", beat_id, beat.get("event"))

            elif beat_type == "audio":
                await bus.publish(EVENT_CHANNELS.AUDIO_EVENT, {
                    "encounterId": encounter_id,
                    "type": beat.get("event", ""),
                    "timestamp": timestamp,
                    "detail": beat.get("detail"),
                })
                logger.debug("[demo] beat %s [audio] %s", beat_id, beat.get("event"))

            elif beat_type == "vision":
                await bus.publish(EVENT_CHANNELS.VISION_CAPTURED, {
                    "encounterId": encounter_id,
                    "identified": beat.get("identified", ""),
                    "captureType": beat.get("captureType", "vial_label"),
                    "timestamp": timestamp,
                    "rawText": beat.get("rawText"),
                })
                logger.debug("[demo] beat %s [vision] %s", beat_id, beat.get("identified"))

            else:
                logger.warning("[demo] unknown beat type '%s' for beat %s", beat_type, beat_id)

        except Exception as e:
            logger.error("[demo] failed to publish beat %s: %s", beat_id, e)

    _active_injectors.pop(encounter_id, None)
    logger.info("[demo] replay complete")
