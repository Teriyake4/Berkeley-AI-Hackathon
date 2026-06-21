"""
Timeline agent — ambulance edition.
Consumes facts.extracted, audio.event, telemetry.updated, vision.captured.
Publishes timeline.updated.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Callable, List

from bus import InMemoryBus, RedisBus
from claude import call_claude_json
from events import EVENT_CHANNELS, TimelineEntry, entities_from_dict, timeline_entry_from_dict, to_dict
from prompts.timeline import (
    TIMELINE_SYSTEM,
    build_timeline_prompt,
    heuristic_timeline,
    merge_timeline,
    _normalize_extraction_timestamps,
)
from redis_layer.keys import EncounterKeys
from redis_layer.state import get_transcript, load_json, save_json

logger = logging.getLogger(__name__)

TELEMETRY_LABELS = {
    "scene_arrival": "Scene Arrival",
    "patient_contact": "Patient contact established",
    "en_route": "En Route",
    "hospital_arrival": "Hospital Arrival",
}

AUDIO_LABELS = {
    "silence": "Extended silence on scene",
    "alarm": "Monitor alarm detected",
    "distress": "Patient distress audio detected",
    "monitor_tone": "Monitor tone change detected",
}


async def _append_and_publish(
    bus: InMemoryBus | RedisBus,
    encounter_id: str,
    new_entry: TimelineEntry,
) -> None:
    existing_raw = await load_json(EncounterKeys.timeline(encounter_id)) or []
    existing: List[TimelineEntry] = [
        timeline_entry_from_dict(e) if isinstance(e, dict) else e
        for e in existing_raw
    ]

    short = new_entry.summary[:40].lower()
    if any(short in e.summary.lower() for e in existing):
        return

    updated = sorted(existing + [new_entry], key=lambda e: e.timestamp)[-20:]

    await save_json(EncounterKeys.timeline(encounter_id), [to_dict(e) for e in updated])
    await bus.publish(EVENT_CHANNELS.TIMELINE_UPDATED, {
        "encounterId": encounter_id,
        "events": [to_dict(e) for e in updated],
    })


async def _publish_timeline(
    bus: InMemoryBus | RedisBus,
    encounter_id: str,
    events: List[TimelineEntry],
) -> None:
    await save_json(EncounterKeys.timeline(encounter_id), [to_dict(e) for e in events])
    await bus.publish(EVENT_CHANNELS.TIMELINE_UPDATED, {
        "encounterId": encounter_id,
        "events": [to_dict(e) for e in events],
    })


async def start_timeline_agent(bus: InMemoryBus | RedisBus) -> Callable[[], None]:

    async def on_facts_extracted(envelope: dict) -> None:
        payload = envelope.get("payload", {})
        encounter_id = payload.get("encounterId", "")
        entities_raw = payload.get("entities", {})
        entities = entities_from_dict(entities_raw)
        extracted_at = payload.get("extractedAt") or datetime.now(timezone.utc).isoformat()

        existing_raw = await load_json(EncounterKeys.timeline(encounter_id)) or []
        existing: List[TimelineEntry] = [
            timeline_entry_from_dict(e) if isinstance(e, dict) else e
            for e in existing_raw
        ]
        transcript = await get_transcript(encounter_id)
        transcript_lines = await load_json(EncounterKeys.transcript_lines(encounter_id)) or []

        result = await call_claude_json(
            TIMELINE_SYSTEM,
            build_timeline_prompt(
                entities, transcript, existing, extracted_at, transcript_lines
            ),
            "timeline",
        )

        if result and isinstance(result, list):
            raw_events = [
                timeline_entry_from_dict(e) if isinstance(e, dict) else e for e in result
            ]
            extraction_events = _normalize_extraction_timestamps(
                raw_events, existing, extracted_at, transcript_lines
            )
        else:
            extraction_events = heuristic_timeline(
                entities, existing, extracted_at, transcript_lines
            )

        events = merge_timeline(existing, extraction_events)
        await _publish_timeline(bus, encounter_id, events)

    async def on_audio_event(envelope: dict) -> None:
        payload = envelope.get("payload", {})
        encounter_id = payload.get("encounterId", "")
        event_type = payload.get("type", "")
        timestamp = payload.get("timestamp", datetime.now(timezone.utc).isoformat())
        detail = payload.get("detail", "")

        label = AUDIO_LABELS.get(event_type, f"Audio event: {event_type}")
        summary = f"{label}{f' — {detail}' if detail else ''}"

        entry = TimelineEntry(
            id=f"audio-{event_type}-{timestamp}",
            timestamp=timestamp,
            summary=summary,
            source="audio",
        )
        await _append_and_publish(bus, encounter_id, entry)

    async def on_telemetry_updated(envelope: dict) -> None:
        payload = envelope.get("payload", {})
        encounter_id = payload.get("encounterId", "")
        event = payload.get("event", "")
        timestamp = payload.get("timestamp", datetime.now(timezone.utc).isoformat())
        label = payload.get("label", "")

        summary = TELEMETRY_LABELS.get(event, event.replace("_", " ").title())
        if label:
            summary = f"{summary} — {label}"

        entry = TimelineEntry(
            id=f"telemetry-{event}-{timestamp}",
            timestamp=timestamp,
            summary=summary,
            source="telemetry",
        )
        await _append_and_publish(bus, encounter_id, entry)

    async def on_vision_captured(envelope: dict) -> None:
        payload = envelope.get("payload", {})
        encounter_id = payload.get("encounterId", "")
        identified = payload.get("identified", "")
        capture_type = payload.get("captureType", "")
        timestamp = payload.get("timestamp", datetime.now(timezone.utc).isoformat())

        if not identified:
            return

        summary = f"Vision: {identified} identified"
        entry = TimelineEntry(
            id=f"vision-{timestamp}",
            timestamp=timestamp,
            summary=summary,
            source="vision",
        )
        await _append_and_publish(bus, encounter_id, entry)

    unsub_facts = await bus.subscribe(EVENT_CHANNELS.FACTS_EXTRACTED, on_facts_extracted)
    unsub_audio = await bus.subscribe(EVENT_CHANNELS.AUDIO_EVENT, on_audio_event)
    unsub_telemetry = await bus.subscribe(EVENT_CHANNELS.TELEMETRY_UPDATED, on_telemetry_updated)
    unsub_vision = await bus.subscribe(EVENT_CHANNELS.VISION_CAPTURED, on_vision_captured)

    def stop() -> None:
        unsub_facts()
        unsub_audio()
        unsub_telemetry()
        unsub_vision()

    return stop
