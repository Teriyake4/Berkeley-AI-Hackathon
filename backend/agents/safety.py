"""
Safety agent — ambulance edition.
Handles: interaction flags, allergy-gap timer, missed-follow-up timer,
         NREMT checklist, and vision.captured cross-check.
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

from bus import InMemoryBus, RedisBus
from claude import call_claude_json
from events import EVENT_CHANNELS, Medication, entities_from_dict, to_dict
from prompts.drug_interactions import (
    check_interactions,
    extract_drugs_from_text,
    is_administration_context,
    is_patient_med_context,
    normalize_drug,
)
from prompts.safety import (
    SAFETY_SYSTEM,
    SafetyResult,
    _allergen_in_text,
    build_safety_prompt,
    heuristic_allergy_flags,
    heuristic_safety,
)
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

ADMIN_ACTION_KEYWORDS = (
    "giving", "give you", "give him", "give her", "administer",
    "administered", "feed", "feeding", "inject", "injected",
    "start you on", "put you on", "going to give", "i'll give",
    "thinking about giving",
)


async def _fire_flag(
    bus: InMemoryBus | RedisBus,
    encounter_id: str,
    concern: str,
    severity: str,
    rationale: str,
    prior_concerns: set,
    clarifying_question: str | None = None,
    recommended_actions: list | None = None,
) -> None:
    if concern in prior_concerns:
        return
    prior_concerns.add(concern)

    prior_raw = await load_json(EncounterKeys.safety_flags(encounter_id)) or []
    existing_concerns = {f.get("concern", "") if isinstance(f, dict) else f.concern for f in prior_raw}
    if concern in existing_concerns:
        return

    new_flag = {"concern": concern, "severity": severity, "rationale": rationale}
    if clarifying_question:
        new_flag["clarifyingQuestion"] = clarifying_question
    if recommended_actions:
        new_flag["recommendedActions"] = recommended_actions
    prior_raw.append(new_flag)
    await save_json(EncounterKeys.safety_flags(encounter_id), prior_raw)

    event_payload = {
        "encounterId": encounter_id,
        "concern": concern,
        "severity": severity,
        "rationale": rationale,
        "flaggedAt": datetime.now(timezone.utc).isoformat(),
    }
    if clarifying_question:
        event_payload["clarifyingQuestion"] = clarifying_question
    if recommended_actions:
        event_payload["recommendedActions"] = recommended_actions
    await bus.publish(EVENT_CHANNELS.SAFETY_FLAGGED, event_payload)


async def start_safety_agent(bus: InMemoryBus | RedisBus) -> Callable[[], None]:
    # Per-encounter runtime state (in-memory timers)
    _allergy_timers: Dict[str, asyncio.Task] = {}
    _symptom_timers: Dict[str, asyncio.Task] = {}  # key: "enc_id:symptom"
    _fired: Dict[str, set] = {}  # encounter_id -> set of fired concern keys
    _known_allergies: Dict[str, set] = {}  # encounter_id -> lowercase allergy names

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

    # ── Allergy documentation + administration cross-check ───────────────────

    async def _flag_new_allergies(encounter_id: str, entities) -> None:
        prior = _known_allergies.get(encounter_id, set())
        current = {a.lower() for a in entities.allergies}
        new_allergies = current - prior
        _known_allergies[encounter_id] = current

        fired = _get_fired(encounter_id)
        for allergy_lower in new_allergies:
            display = next(a for a in entities.allergies if a.lower() == allergy_lower)
            await _fire_flag(
                bus, encounter_id,
                concern=f"ALLERGY ALERT: {display} — verify before any administration",
                severity="high",
                rationale=(
                    f"Patient has stated allergy to {display}. "
                    "Confirm all medications, foods, and treatments are safe before administration. "
                    f"Do NOT give {display} or related agents."
                ),
                prior_concerns=fired,
            )

    async def _check_transcript_allergy_conflict(encounter_id: str, text: str, speaker: str) -> None:
        if speaker not in ("paramedic", "doctor"):
            return

        lower = text.lower()
        if not any(kw in lower for kw in ADMIN_ACTION_KEYWORDS):
            return

        from redis_layer.state import get_transcript
        transcript = await get_transcript(encounter_id)
        facts_raw = await load_json(EncounterKeys.facts(encounter_id))
        allergies: List[str] = []
        if facts_raw:
            allergies = entities_from_dict(facts_raw).allergies

        # Also catch allergies stated in transcript before extraction completes
        for match in re.finditer(r"allergic to (\w+(?:\s+\w+)?)", transcript.lower()):
            candidate = match.group(1).strip()
            if candidate and candidate not in [a.lower() for a in allergies]:
                allergies.append(candidate)

        if not allergies:
            return

        fired = _get_fired(encounter_id)
        for allergy in allergies:
            if _allergen_in_text(allergy, lower):
                await _fire_flag(
                    bus, encounter_id,
                    concern=f"CRITICAL: Proposed/administered {allergy} despite documented allergy",
                    severity="high",
                    rationale=(
                        f"Paramedic dialogue suggests giving '{allergy}' while patient has "
                        f"documented {allergy} allergy. STOP — risk of anaphylaxis or severe "
                        "allergic reaction."
                    ),
                    prior_concerns=fired,
                )

    # ── Active medication tracking + drug interaction cross-check ────────────

    async def _get_active_meds(encounter_id: str) -> List[str]:
        raw = await load_json(EncounterKeys.active_medications(encounter_id)) or []
        return [entry["name"] for entry in raw if isinstance(entry, dict) and entry.get("name")]

    async def _register_active_med(
        encounter_id: str,
        drug_name: str,
        source: str,
        *,
        publish_facts: bool = True,
    ) -> List[str]:
        canonical = normalize_drug(drug_name) or drug_name.lower().strip()
        if not canonical:
            return await _get_active_meds(encounter_id)

        active_raw = await load_json(EncounterKeys.active_medications(encounter_id)) or []
        if any(entry.get("name") == canonical for entry in active_raw if isinstance(entry, dict)):
            return [entry["name"] for entry in active_raw if isinstance(entry, dict)]

        active_raw.append({
            "name": canonical,
            "source": source,
            "recordedAt": datetime.now(timezone.utc).isoformat(),
        })
        await save_json(EncounterKeys.active_medications(encounter_id), active_raw)

        if publish_facts:
            facts_raw = await load_json(EncounterKeys.facts(encounter_id))
            entities = entities_from_dict(facts_raw) if facts_raw else None
            if entities is None:
                from events import MedicalEntities
                entities = MedicalEntities()

            already_in_facts = any(
                (normalize_drug(m.name) or m.name.lower()) == canonical
                for m in entities.medications
            )
            if not already_in_facts:
                dose = "administered on scene" if source == "administered" else None
                entities.medications.append(Medication(name=canonical, dose=dose))
                await save_json(EncounterKeys.facts(encounter_id), to_dict(entities))
                await bus.publish(EVENT_CHANNELS.FACTS_EXTRACTED, {
                    "encounterId": encounter_id,
                    "entities": to_dict(entities),
                    "extractedAt": datetime.now(timezone.utc).isoformat(),
                })

        return [entry["name"] for entry in active_raw if isinstance(entry, dict)]

    async def _flag_interactions(encounter_id: str, active_drugs: List[str]) -> None:
        fired = _get_fired(encounter_id)
        for flag in check_interactions(active_drugs):
            await _fire_flag(
                bus, encounter_id,
                concern=flag.concern,
                severity=flag.severity,
                rationale=flag.rationale,
                prior_concerns=fired,
            )

    async def _sync_active_meds_from_entities(encounter_id: str, entities) -> None:
        for med in entities.medications:
            await _register_active_med(
                encounter_id, med.name, "documented", publish_facts=False
            )

    async def _check_patient_medications(encounter_id: str, text: str, speaker: str) -> None:
        if speaker not in ("patient", "bystander"):
            return
        if not is_patient_med_context(text):
            return
        for drug in extract_drugs_from_text(text):
            prior = await _get_active_meds(encounter_id)
            await _register_active_med(encounter_id, drug, "patient_stated")
            updated = await _get_active_meds(encounter_id)
            if drug not in prior or len(updated) > len(prior):
                await _flag_interactions(encounter_id, updated)

    async def _check_administered_medications(
        encounter_id: str, text: str, speaker: str
    ) -> None:
        if speaker not in ("paramedic", "doctor"):
            return
        if not is_administration_context(text):
            return

        administered = extract_drugs_from_text(text)
        if not administered:
            return

        prior = await _get_active_meds(encounter_id)
        for drug in administered:
            await _register_active_med(encounter_id, drug, "administered")
        updated = await _get_active_meds(encounter_id)
        await _flag_interactions(encounter_id, updated)

        # Also cross-check against allergies for administered drugs
        facts_raw = await load_json(EncounterKeys.facts(encounter_id))
        allergies: List[str] = []
        if facts_raw:
            allergies = entities_from_dict(facts_raw).allergies

        from redis_layer.state import get_transcript
        transcript = await get_transcript(encounter_id)
        for match in re.finditer(r"allergic to (\w+(?:\s+\w+)?)", transcript.lower()):
            candidate = match.group(1).strip()
            if candidate and candidate not in [a.lower() for a in allergies]:
                allergies.append(candidate)

        fired = _get_fired(encounter_id)
        lower = text.lower()
        for allergy in allergies:
            if _allergen_in_text(allergy, lower):
                await _fire_flag(
                    bus, encounter_id,
                    concern=f"CRITICAL: Proposed/administered {allergy} despite documented allergy",
                    severity="high",
                    rationale=(
                        f"Paramedic dialogue suggests giving '{allergy}' while patient has "
                        f"documented {allergy} allergy. STOP — risk of anaphylaxis or severe "
                        "allergic reaction."
                    ),
                    prior_concerns=fired,
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

        # Immediate allergy alert when first documented
        await _flag_new_allergies(encounter_id, entities)

        # Sync and cross-check active medications
        await _sync_active_meds_from_entities(encounter_id, entities)
        active_meds = await _get_active_meds(encounter_id)
        await _flag_interactions(encounter_id, active_meds)

        from redis_layer.state import get_transcript
        transcript = await get_transcript(encounter_id)

        # Run Claude safety analysis
        prior_raw = await load_json(EncounterKeys.safety_flags(encounter_id)) or []
        prior: List[SafetyResult] = [
            SafetyResult(**f) if isinstance(f, dict) else f for f in prior_raw
        ]

        # Load all accumulated research briefs to give Claude full clinical context
        all_research = await load_json(EncounterKeys.research(encounter_id)) or []

        result = await call_claude_json(
            SAFETY_SYSTEM,
            build_safety_prompt(entities, transcript, research_briefs=all_research),
            "safety",
        )

        if result and isinstance(result, list):
            flags = [SafetyResult(**f) if isinstance(f, dict) else f for f in result]
        else:
            flags = heuristic_safety(entities, transcript)

        if not isinstance(flags, list):
            flags = heuristic_safety(entities, transcript)

        # Always merge heuristic allergy/interaction flags (Claude may miss them)
        heuristic_flags = heuristic_safety(entities, transcript)
        interaction_flags = check_interactions(active_meds)
        heuristic_flags.extend(interaction_flags)
        prior_concerns_in_batch = {f.concern for f in flags}
        for hf in heuristic_flags:
            if hf.concern not in prior_concerns_in_batch:
                flags.append(hf)
                prior_concerns_in_batch.add(hf.concern)

        prior_concerns = {p.concern if isinstance(p, SafetyResult) else p.get("concern", "") for p in prior}
        new_flags = [f for f in flags if f.concern not in prior_concerns]
        all_flags = prior + new_flags
        await save_json(EncounterKeys.safety_flags(encounter_id), [to_dict(f) for f in all_flags])

        for flag in new_flags:
            cq = flag.clarifyingQuestion if isinstance(flag, SafetyResult) else flag.get("clarifyingQuestion") if isinstance(flag, dict) else None
            ra = flag.recommendedActions if isinstance(flag, SafetyResult) else flag.get("recommendedActions") if isinstance(flag, dict) else None
            await _fire_flag(
                bus, encounter_id,
                concern=flag.concern,
                severity=flag.severity,
                rationale=flag.rationale,
                prior_concerns=fired,
                clarifying_question=cq,
                recommended_actions=ra,
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
        active_meds = await _get_active_meds(encounter_id)
        scanned_drugs = extract_drugs_from_text(identified)
        for drug in scanned_drugs:
            await _register_active_med(encounter_id, drug, "vision_scan", publish_facts=False)
        updated_active = await _get_active_meds(encounter_id)
        await _flag_interactions(encounter_id, updated_active)

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

    async def _check_allergy_stated(encounter_id: str, text: str) -> None:
        lower = text.lower()
        if "allerg" not in lower:
            return
        match = re.search(r"allergic to (\w+(?:\s+\w+)?)", lower)
        if not match:
            return
        allergen = match.group(1).strip()
        concern = f"ALLERGY ALERT: {allergen} — verify before any administration"
        fired = _get_fired(encounter_id)
        await _fire_flag(
            bus, encounter_id,
            concern=concern,
            severity="high",
            rationale=(
                f"Patient has stated allergy to {allergen}. "
                "Confirm all medications, foods, and treatments are safe before administration. "
                f"Do NOT give {allergen} or related agents."
            ),
            prior_concerns=fired,
        )
        known = _known_allergies.get(encounter_id, set())
        known.add(allergen.lower())
        _known_allergies[encounter_id] = known

    async def on_transcript(envelope: dict) -> None:
        payload = envelope.get("payload", {})
        encounter_id = payload.get("encounterId", "")
        text = payload.get("text", "")
        speaker = payload.get("speaker", "")
        if not encounter_id or not text:
            return
        if speaker in ("patient", "bystander"):
            await _check_allergy_stated(encounter_id, text)
            await _check_patient_medications(encounter_id, text, speaker)
        if speaker in ("paramedic", "doctor"):
            await _check_administered_medications(encounter_id, text, speaker)
            await _check_transcript_allergy_conflict(encounter_id, text, speaker)

    async def on_research_completed(envelope: dict) -> None:
        payload = envelope.get("payload", {})
        encounter_id = payload.get("encounterId", "")
        if not encounter_id:
            return

        facts_raw = await load_json(EncounterKeys.facts(encounter_id))
        if not facts_raw:
            return
        entities = entities_from_dict(facts_raw)

        from redis_layer.state import get_transcript
        transcript = await get_transcript(encounter_id)
        all_research = await load_json(EncounterKeys.research(encounter_id)) or []

        result = await call_claude_json(
            SAFETY_SYSTEM,
            build_safety_prompt(entities, transcript, research_briefs=all_research),
            "safety",
        )

        if result and isinstance(result, list):
            flags = [
                SafetyResult(**{k: v for k, v in f.items() if k in ("concern", "severity", "rationale", "clarifyingQuestion", "recommendedActions")})
                if isinstance(f, dict) else f
                for f in result
            ]
        else:
            flags = heuristic_safety(entities, transcript)

        if not isinstance(flags, list):
            flags = []

        prior_raw = await load_json(EncounterKeys.safety_flags(encounter_id)) or []
        prior_concerns = {f.get("concern", "") if isinstance(f, dict) else f.concern for f in prior_raw}
        fired = _get_fired(encounter_id)

        for flag in flags:
            concern = flag.concern if isinstance(flag, SafetyResult) else flag.get("concern", "")
            severity = flag.severity if isinstance(flag, SafetyResult) else flag.get("severity", "medium")
            rationale = flag.rationale if isinstance(flag, SafetyResult) else flag.get("rationale", "")
            cq = flag.clarifyingQuestion if isinstance(flag, SafetyResult) else flag.get("clarifyingQuestion")
            ra = flag.recommendedActions if isinstance(flag, SafetyResult) else flag.get("recommendedActions")
            if concern and concern not in prior_concerns:
                await _fire_flag(bus, encounter_id, concern, severity, rationale, fired, clarifying_question=cq, recommended_actions=ra)

    unsub_facts = await bus.subscribe(EVENT_CHANNELS.FACTS_EXTRACTED, on_facts_extracted)
    unsub_vision = await bus.subscribe(EVENT_CHANNELS.VISION_CAPTURED, on_vision_captured)
    unsub_transcript = await bus.subscribe(EVENT_CHANNELS.TRANSCRIPT_SEGMENT, on_transcript)
    unsub_research = await bus.subscribe(EVENT_CHANNELS.RESEARCH_COMPLETED, on_research_completed)

    def stop() -> None:
        unsub_facts()
        unsub_vision()
        unsub_transcript()
        unsub_research()
        for task in list(_allergy_timers.values()):
            task.cancel()
        for task in list(_symptom_timers.values()):
            task.cancel()

    return stop
