"""
Extraction agent — mirrors lib/agents/extraction.ts.
Debounced on transcript.segment; extracts medical entities via Claude or heuristics.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Callable

from bus import InMemoryBus, RedisBus
from claude import call_claude_json
from debounce import schedule_debounce, clear_debounce
from events import EVENT_CHANNELS, MedicalEntities, entities_from_dict, to_dict
from prompts.extraction import EXTRACTION_SYSTEM, build_extraction_prompt, heuristic_extract
from redis_layer.keys import EncounterKeys
from redis_layer.state import append_buffer, get_buffer, clear_buffer, load_json, save_json

logger = logging.getLogger(__name__)

EXTRACTION_DELAY_MS = 4000
SILENCE_MS = 1500


async def start_extraction_agent(bus: InMemoryBus | RedisBus) -> Callable[[], None]:
    async def run_extraction(encounter_id: str) -> None:
        transcript = await get_buffer(encounter_id)
        if not transcript.strip():
            return

        existing_raw = await load_json(EncounterKeys.facts(encounter_id))
        existing = entities_from_dict(existing_raw) if existing_raw else None

        result = await call_claude_json(
            EXTRACTION_SYSTEM,
            build_extraction_prompt(transcript, existing),
            "extraction",
        )

        if result and isinstance(result, dict):
            entities = entities_from_dict(result)
        else:
            entities = heuristic_extract(transcript, existing)

        entities = _merge_entities(existing, entities)
        await save_json(EncounterKeys.facts(encounter_id), to_dict(entities))
        await clear_buffer(encounter_id)

        await bus.publish(EVENT_CHANNELS.FACTS_EXTRACTED, {
            "encounterId": encounter_id,
            "entities": to_dict(entities),
            "extractedAt": datetime.now(timezone.utc).isoformat(),
        })

    async def on_transcript(envelope: dict) -> None:
        payload = envelope.get("payload", {})
        encounter_id = payload.get("encounterId", "")
        text = payload.get("text", "")

        await append_buffer(encounter_id, text)
        full = await get_buffer(encounter_id)

        schedule_debounce(
            f"extract:{encounter_id}",
            EXTRACTION_DELAY_MS,
            SILENCE_MS,
            full,
            lambda: run_extraction(encounter_id),
        )

    unsub = await bus.subscribe(EVENT_CHANNELS.TRANSCRIPT_SEGMENT, on_transcript)
    return unsub


def _merge_entities(
    existing: MedicalEntities | None,
    incoming: MedicalEntities,
) -> MedicalEntities:
    if existing is None:
        return incoming

    med_names = {m.name.lower() for m in existing.medications}
    merged_meds = list(existing.medications)
    for m in incoming.medications:
        if m.name.lower() not in med_names:
            merged_meds.append(m)

    allergy_keys: set[str] = set()
    merged_allergies: list[str] = []
    for a in existing.allergies + incoming.allergies:
        key = a.lower().strip()
        if key not in allergy_keys:
            allergy_keys.add(key)
            merged_allergies.append(a)

    return MedicalEntities(
        medications=merged_meds,
        conditions=list(dict.fromkeys(existing.conditions + incoming.conditions)),
        allergies=merged_allergies,
        vitals={**existing.vitals, **incoming.vitals},
        symptoms=list(dict.fromkeys(existing.symptoms + incoming.symptoms)),
        demographics=incoming.demographics or existing.demographics,
    )
