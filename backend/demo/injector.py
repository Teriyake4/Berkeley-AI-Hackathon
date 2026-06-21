"""
Demo scenario injector — mirrors lib/demo/injector.ts.
Replays demo-scenario.json beats on a timer using asyncio.
Supports beat types: transcript, telemetry, audio, vision.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
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


def _scenario_paths() -> List[Path]:
    """Resolve demo-scenario.json for repo dev, Docker Compose, or explicit override."""
    paths: List[Path] = []
    env_path = os.environ.get("DEMO_SCENARIO_PATH")
    if env_path:
        paths.append(Path(env_path))
    paths.extend([
        Path("/scripts/demo-scenario.json"),  # docker compose: ./scripts mounted here
        Path(__file__).resolve().parent.parent.parent / "scripts" / "demo-scenario.json",
        Path(__file__).resolve().parent / "demo-scenario.json",
    ])
    # de-dupe while preserving order
    seen: set[str] = set()
    unique: List[Path] = []
    for p in paths:
        key = str(p)
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def _fallback_scenario() -> Dict[str, Any]:
    """Minimal scenario if JSON file is missing — 1s between lines."""
    beats: List[Dict[str, Any]] = []
    lines = [
        ("paramedic", "Ma'am, I'm Alex with county EMS. What happened?"),
        ("patient", "Chest pain for two hours. It started while gardening."),
        ("paramedic", "Any allergies? Medications?"),
        ("patient", "Penicillin allergy. Lisinopril and warfarin."),
        ("paramedic", "Getting vitals now."),
        ("patient", "A little short of breath."),
    ]
    for i, (speaker, text) in enumerate(lines):
        beats.append({
            "id": f"fallback-{i + 1}",
            "delayMs": i * 1000,
            "type": "transcript",
            "speaker": speaker,
            "text": text,
        })
    return {"encounterId": "demo-encounter-001", "beats": beats}


def _load_scenario() -> Dict[str, Any]:
    for scenario_path in _scenario_paths():
        try:
            if not scenario_path.is_file():
                continue
            with open(scenario_path, "r", encoding="utf-8") as f:
                scenario = json.load(f)
            logger.info("[demo] loaded scenario from %s (%d beats)", scenario_path, len(scenario.get("beats", [])))
            return scenario
        except Exception as e:
            logger.warning("[demo] could not load %s: %s", scenario_path, e)

    logger.error(
        "[demo] demo-scenario.json not found — tried: %s",
        ", ".join(str(p) for p in _scenario_paths()),
    )
    return _fallback_scenario()


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
