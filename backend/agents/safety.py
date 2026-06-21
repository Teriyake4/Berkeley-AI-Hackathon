"""
Safety agent — ambulance edition.
Handles: interaction flags, allergy-gap timer, missed-follow-up timer,
         NREMT checklist, and vision.captured cross-check.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

from bus import InMemoryBus, RedisBus
from claude import call_claude_json
from events import EVENT_CHANNELS, entities_from_dict, to_dict
from prompts.safety import SAFETY_SYSTEM, SafetyResult, build_safety_prompt, heuristic_safety
from redis_layer.keys import EncounterKeys
from redis_layer.state import load_json, save_json

logger = logging.getLogger(__name__)

ALLERGY_GAP_SECONDS = 120   # 2 minutes
MISSED_FOLLOWUP_SECONDS = 180  # 3 minutes

NREMT_ITEMS = [
    ("allergies", "Allergies not yet documented on scene"),
    ("medications", "Current medications not yet documented on scene"),
    ("last_oral_intake", "Last oral intake not yet documented (SAMPLE history)"),
    ("events_leading", "Events/history leading to chief complaint not yet documented (SAMPLE)"),
    ("pertinent_negatives", "Pertinent negatives for chief complaint not yet assessed"),
]


async def _fire_flag(
    bus: InMemoryBus | RedisBus,
    encounter_id: str,
    concern: str,
    severity: str,
    rationale: str,
    prior_concerns: set,
) -> None:
    if concern in prior_concerns:
        return
    prior_concerns.add(concern)

    prior_raw = await load_json(EncounterKeys.safety_flags(encounter_id)) or []
    existing_concerns = {f.get("concern", "") if isinstance(f, dict) else f.concern for f in prior_raw}
    if concern in existing_concerns:
        return

    new_flag = {"concern": concern, "severity": severity, "rationale": rationale}
    prior_raw.append(new_flag)
    await save_json(EncounterKeys.safety_flags(encounter_id), prior_raw)

    await bus.publish(EVENT_CHANNELS.SAFETY_FLAGGED, {
        "encounterId": encounter_id,
        "concern": concern,
        "severity": severity,
        "rationale": rationale,
        "flaggedAt": datetime.now(timezone.utc).isoformat(),
    })


async def start_safety_agent(bus: InMemoryBus | RedisBus) -> Callable[[], None]:
    # Per-encounter runtime state (in-memory timers)
    _allergy_timers: Dict[str, asyncio.Task] = {}
    _symptom_timers: Dict[str, asyncio.Task] = {}  # key: "enc_id:symptom"
    _fired: Dict[str, set] = {}  # encounter_id -> set of fired concern keys

    def _get_fired(encounter_id: str) -> set:
        if encounter_id not in _fired:
            _fired[encounter_id] = set()
        return _fired[encounter_id]

    # ── Allergy gap timer ────────────────────────────────────────────────────

    async def _allergy_gap_timer(encounter_id: str) -> None:
        await asyncio.sleep(ALLERGY_GAP_SECONDS)
        facts_raw = await load_json(EncounterKeys.facts(encounter_id))
        if not facts_raw:
            return
        entities = entities_from_dict(facts_raw)
        if not entities.allergies:
            await _fire_flag(
                bus, encounter_id,
                concern="Allergies not documented — 2 minutes elapsed on scene",
                severity="medium",
                rationale=(
                    "No allergies have been stated after 2 minutes on scene. "
                    "NREMT protocol requires allergy status before medication administration."
                ),
                prior_concerns=_get_fired(encounter_id),
            )

    # ── Missed follow-up timer ───────────────────────────────────────────────

    async def _symptom_followup_timer(encounter_id: str, symptom: str) -> None:
        await asyncio.sleep(MISSED_FOLLOWUP_SECONDS)
        facts_raw = await load_json(EncounterKeys.facts(encounter_id))
        if not facts_raw:
            return
        entities = entities_from_dict(facts_raw)
        still_present = any(symptom.lower() in s.lower() for s in entities.symptoms)
        if still_present:
            concern = f"{symptom.title()} mentioned on scene — not reassessed in 3 minutes"
            await _fire_flag(
                bus, encounter_id,
                concern=concern,
                severity="medium",
                rationale=(
                    f"'{symptom}' was documented but no follow-up assessment or plan "
                    "documented in the last 3 minutes. NREMT protocol requires reassessment."
                ),
                prior_concerns=_get_fired(encounter_id),
            )

    # ── NREMT checklist ──────────────────────────────────────────────────────

    async def _check_nremt(encounter_id: str, entities) -> None:
        nremt_raw = await load_json(EncounterKeys.nremt_covered(encounter_id)) or {}

        if entities.allergies:
            nremt_raw["allergies"] = True
        if entities.medications:
            nremt_raw["medications"] = True

        from redis_layer.state import get_transcript
        transcript = await get_transcript(encounter_id)
        tl = transcript.lower()
        if any(kw in tl for kw in ["last ate", "last drink", "last meal", "oral intake", "when did you eat"]):
            nremt_raw["last_oral_intake"] = True
        if any(kw in tl for kw in ["what happened", "how did this start", "what were you doing", "how long ago"]):
            nremt_raw["events_leading"] = True
        if any(kw in tl for kw in ["any nausea", "any vomiting", "any fever", "any cough", "any shortness"]):
            nremt_raw["pertinent_negatives"] = True

        await save_json(EncounterKeys.nremt_covered(encounter_id), nremt_raw)

        for key, reminder in NREMT_ITEMS:
            if not nremt_raw.get(key):
                await _fire_flag(
                    bus, encounter_id,
                    concern=f"NREMT gap: {reminder}",
                    severity="low",
                    rationale=f"NREMT primary assessment: {reminder}. Ensure this is addressed before transport.",
                    prior_concerns=_get_fired(encounter_id),
                )

    # ── Main facts handler ───────────────────────────────────────────────────

    async def on_facts_extracted(envelope: dict) -> None:
        payload = envelope.get("payload", {})
        encounter_id = payload.get("encounterId", "")
        entities = entities_from_dict(payload.get("entities", {}))
        fired = _get_fired(encounter_id)

        # Start allergy gap timer on first facts event for this encounter
        if encounter_id not in _allergy_timers:
            task = asyncio.create_task(_allergy_gap_timer(encounter_id))
            _allergy_timers[encounter_id] = task

        # Start missed follow-up timers for newly seen symptoms
        for symptom in entities.symptoms:
            timer_key = f"{encounter_id}:{symptom.lower()}"
            if timer_key not in _symptom_timers:
                task = asyncio.create_task(_symptom_followup_timer(encounter_id, symptom))
                _symptom_timers[timer_key] = task

        # If allergies are now documented, cancel the allergy gap timer
        if entities.allergies and encounter_id in _allergy_timers:
            _allergy_timers[encounter_id].cancel()
            del _allergy_timers[encounter_id]
            nremt_raw = await load_json(EncounterKeys.nremt_covered(encounter_id)) or {}
            nremt_raw["allergies"] = True
            await save_json(EncounterKeys.nremt_covered(encounter_id), nremt_raw)

        # Run Claude safety analysis
        prior_raw = await load_json(EncounterKeys.safety_flags(encounter_id)) or []
        prior: List[SafetyResult] = [
            SafetyResult(**f) if isinstance(f, dict) else f for f in prior_raw
        ]

        result = await call_claude_json(
            SAFETY_SYSTEM,
            build_safety_prompt(entities),
            "safety",
        )

        if result and isinstance(result, list):
            flags = [SafetyResult(**f) if isinstance(f, dict) else f for f in result]
        else:
            flags = heuristic_safety(entities)

        if not isinstance(flags, list):
            flags = heuristic_safety(entities)

        prior_concerns = {p.concern if isinstance(p, SafetyResult) else p.get("concern", "") for p in prior}
        new_flags = [f for f in flags if f.concern not in prior_concerns]
        all_flags = prior + new_flags
        await save_json(EncounterKeys.safety_flags(encounter_id), [to_dict(f) for f in all_flags])

        for flag in new_flags:
            await _fire_flag(
                bus, encounter_id,
                concern=flag.concern,
                severity=flag.severity,
                rationale=flag.rationale,
                prior_concerns=fired,
            )

        # NREMT checklist (runs after interaction flags so allergy coverage is recorded)
        await _check_nremt(encounter_id, entities)

    # ── Vision cross-check ───────────────────────────────────────────────────

    async def on_vision_captured(envelope: dict) -> None:
        payload = envelope.get("payload", {})
        encounter_id = payload.get("encounterId", "")
        identified = payload.get("identified", "")
        capture_type = payload.get("captureType", "")

        if not identified:
            return

        vision_raw = await load_json(EncounterKeys.vision_items(encounter_id)) or []
        vision_raw.append({"identified": identified, "captureType": capture_type})
        await save_json(EncounterKeys.vision_items(encounter_id), vision_raw)

        facts_raw = await load_json(EncounterKeys.facts(encounter_id))
        if not facts_raw:
            return
        entities = entities_from_dict(facts_raw)
        meds_lower = [m.name.lower() for m in entities.medications]
        identified_lower = identified.lower()

        if "aspirin" in identified_lower and any("warfarin" in m for m in meds_lower):
            await _fire_flag(
                bus, encounter_id,
                concern=f"Vision scan: {identified} — patient is on warfarin (bleeding risk)",
                severity="high",
                rationale=(
                    f"Vial scan identified '{identified}' on scene. Patient has documented warfarin therapy. "
                    "Concurrent aspirin + warfarin significantly increases GI and intracranial bleeding risk. "
                    "Verify before administration."
                ),
                prior_concerns=_get_fired(encounter_id),
            )

        for allergy in entities.allergies:
            if allergy.lower() in identified_lower:
                await _fire_flag(
                    bus, encounter_id,
                    concern=f"Vision scan: {identified} — patient has documented {allergy} allergy",
                    severity="high",
                    rationale=(
                        f"Vial scan identified '{identified}' on scene. Patient has documented allergy to {allergy}. "
                        "Do NOT administer — verify alternative."
                    ),
                    prior_concerns=_get_fired(encounter_id),
                )

    unsub_facts = await bus.subscribe(EVENT_CHANNELS.FACTS_EXTRACTED, on_facts_extracted)
    unsub_vision = await bus.subscribe(EVENT_CHANNELS.VISION_CAPTURED, on_vision_captured)

    def stop() -> None:
        unsub_facts()
        unsub_vision()
        for task in list(_allergy_timers.values()):
            task.cancel()
        for task in list(_symptom_timers.values()):
            task.cancel()

    return stop
