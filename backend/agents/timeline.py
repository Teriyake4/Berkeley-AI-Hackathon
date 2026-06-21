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
from prompts.timeline import TIMELINE_SYSTEM, build_timeline_prompt, heuristic_timeline
from redis_layer.keys import EncounterKeys
from redis_layer.state import get_transcript, load_json, save_json

logger = logging.getLogger(__name__)

TELEMETRY_LABELS = {
    "scene_arrival": "GPS: Scene arrival",
    "patient_contact": "GPS: Patient contact established",
    "en_route": "GPS: En route to hospital",
    "hospital_arrival": "GPS: Hospital arrival",
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

    updated = existing + [new_entry]
    updated = sorted(updated, key=lambda e: e.timestamp)[-15:]

    await save_json(EncounterKeys.timeline(encounter_id), [to_dict(e) for e in updated])
    await bus.publish(EVENT_CHANNELS.TIMELINE_UPDATED, {
        "encounterId": encounter_id,
        "events": [to_dict(e) for e in updated],
    })


async def start_timeline_agent(bus: InMemoryBus | RedisBus) -> Callable[[], None]:

    async def on_facts_extracted(envelope: dict) -> None:
        payload = envelope.get("payload", {})
        encounter_id = payload.get("encounterId", "")
        entities_raw = payload.get("entities", {})
        entities = entities_from_dict(entities_raw)

        existing_raw = await load_json(EncounterKeys.timeline(encounter_id)) or []
        existing: List[TimelineEntry] = [
            timeline_entry_from_dict(e) if isinstance(e, dict) else e
            for e in existing_raw
        ]
        transcript = await get_transcript(encounter_id)

        result = await call_claude_json(
            TIMELINE_SYSTEM,
            build_timeline_prompt(entities, transcript, existing),
            "timeline",
        )

        if result and isinstance(result, list):
            events = [timeline_entry_from_dict(e) if isinstance(e, dict) else e for e in result]
        else:
            events = heuristic_timeline(entities, existing)

        if not isinstance(events, list):
            events = heuristic_timeline(entities, existing)

        await save_json(EncounterKeys.timeline(encounter_id), [to_dict(e) for e in events])
        await bus.publish(EVENT_CHANNELS.TIMELINE_UPDATED, {
            "encounterId": encounter_id,
            "events": [to_dict(e) for e in events],
        })

    async def on_audio_event(envelope: dict) -> None:
        payload = envelope.get("payload", {})
        encounter_id = payload.get("encounterId", "")
        event_type = payload.get("type", "")
        timestamp = payload.get("timestamp", datetime.now(timezone.utc).isoformat())
        detail = payload.get("detail", "")

        label = AUDIO_LABELS.get(event_type, f"Audio event: {event_type}")
        summary = f"{label}{f' — {detail}' if detail else ''}"

        entry = TimelineEntry(
            id=f"audio-{uuid.uuid4().hex[:8]}",
            timestamp=timestamp,
            summary=summary,
            source="manual",
        )
        await _append_and_publish(bus, encounter_id, entry)

    async def on_telemetry_updated(envelope: dict) -> None:
        payload = envelope.get("payload", {})
        encounter_id = payload.get("encounterId", "")
        event = payload.get("event", "")
        timestamp = payload.get("timestamp", datetime.now(timezone.utc).isoformat())
        label = payload.get("label", "")

        summary = TELEMETRY_LABELS.get(event, f"GPS: {event}")
        if label:
            summary = f"{summary} — {label}"

        entry = TimelineEntry(
            id=f"telemetry-{uuid.uuid4().hex[:8]}",
            timestamp=timestamp,
            summary=summary,
            source="manual",
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

        summary = f"Vision scan ({capture_type}): {identified} identified on scene"
        entry = TimelineEntry(
            id=f"vision-{uuid.uuid4().hex[:8]}",
            timestamp=timestamp,
            summary=summary,
            source="manual",
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
