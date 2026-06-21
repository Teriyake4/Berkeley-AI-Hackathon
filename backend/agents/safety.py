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
from claude import call_claude_json, has_llm
from debounce import schedule_debounce
from events import EVENT_CHANNELS, MedicalEntities, Medication, entities_from_dict, to_dict
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
    _allergen_stem,
    allergy_alert_concern,
    allergy_alert_rationale,
    build_safety_prompt,
    concern_dedupe_key,
    heuristic_allergy_flags,
    heuristic_safety,
    parse_safety_flags_from_llm,
)
from redis_layer.keys import EncounterKeys
from redis_layer.state import load_json, save_json

logger = logging.getLogger(__name__)

ALLERGY_GAP_SECONDS = 120   # 2 minutes
MISSED_FOLLOWUP_SECONDS = 180  # 3 minutes
# LLM safety re-runs on transcript activity (independent of extraction debounce)
SAFETY_DEBOUNCE_MS = 2000
SAFETY_SILENCE_MS = 1000

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
    dedupe = concern_dedupe_key(concern)
    if dedupe in {concern_dedupe_key(c) for c in prior_concerns}:
        return
    prior_concerns.add(dedupe)

    prior_raw = await load_json(EncounterKeys.safety_flags(encounter_id)) or []
    existing_keys = {concern_dedupe_key(f.get("concern", "") if isinstance(f, dict) else f.concern) for f in prior_raw}
    if dedupe in existing_keys:
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
                concern=allergy_alert_concern(display),
                severity="high",
                rationale=allergy_alert_rationale(display),
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

    # ── LLM safety analysis (primary path) ───────────────────────────────────

    async def _run_safety_analysis(encounter_id: str) -> None:
        """Run Claude/NIM safety pass on full transcript + entities; merge deterministic heuristics."""
        from redis_layer.state import get_transcript

        transcript = await get_transcript(encounter_id)
        if not transcript.strip():
            return

        facts_raw = await load_json(EncounterKeys.facts(encounter_id))
        entities = entities_from_dict(facts_raw) if facts_raw else MedicalEntities()

        prior_raw = await load_json(EncounterKeys.safety_flags(encounter_id)) or []
        prior_concerns = {
            concern_dedupe_key(f.get("concern", "") if isinstance(f, dict) else f.concern)
            for f in prior_raw
        }

        all_research = await load_json(EncounterKeys.research(encounter_id)) or []
        active_meds = await _get_active_meds(encounter_id)
        fired = _get_fired(encounter_id)

        flags: List[SafetyResult] = []
        llm_result = None

        if has_llm():
            try:
                llm_result = await call_claude_json(
                    SAFETY_SYSTEM,
                    build_safety_prompt(entities, transcript, research_briefs=all_research),
                    "safety",
                )
                if llm_result and isinstance(llm_result, list):
                    flags = parse_safety_flags_from_llm(llm_result)
                    logger.info(
                        "[safety] LLM analysis for %s → %d flag(s)",
                        encounter_id, len(flags),
                    )
                elif llm_result is not None:
                    logger.warning("[safety] LLM returned non-list for %s: %s", encounter_id, type(llm_result))
            except Exception as e:
                logger.error("[safety] LLM analysis failed for %s: %s", encounter_id, e)

        if not flags and (not has_llm() or llm_result is None):
            logger.info("[safety] Using heuristic fallback for %s", encounter_id)
            flags = heuristic_safety(entities, transcript)

        # Always merge deterministic supplements (allergy, interactions, trauma)
        supplements = heuristic_safety(entities, transcript)
        supplements.extend(check_interactions(active_meds))
        seen = {f.concern for f in flags}
        for hf in supplements:
            if concern_dedupe_key(hf.concern) not in {concern_dedupe_key(c) for c in seen}:
                flags.append(hf)
                seen.add(hf.concern)

        new_flags = [f for f in flags if concern_dedupe_key(f.concern) not in prior_concerns]
        if new_flags:
            stored = list(prior_raw) + [
                {
                    "concern": f.concern,
                    "severity": f.severity,
                    "rationale": f.rationale,
                    **({"clarifyingQuestion": f.clarifyingQuestion} if f.clarifyingQuestion else {}),
                    **({"recommendedActions": f.recommendedActions} if f.recommendedActions else {}),
                }
                for f in new_flags
            ]
            await save_json(EncounterKeys.safety_flags(encounter_id), stored)

        for flag in new_flags:
            await _fire_flag(
                bus, encounter_id,
                concern=flag.concern,
                severity=flag.severity,
                rationale=flag.rationale,
                prior_concerns=fired,
                clarifying_question=flag.clarifyingQuestion,
                recommended_actions=flag.recommendedActions,
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

        await _run_safety_analysis(encounter_id)

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
        known = _known_allergies.get(encounter_id, set())
        if allergen.lower() in known or _allergen_stem(allergen) in {_allergen_stem(k) for k in known}:
            return

        fired = _get_fired(encounter_id)
        await _fire_flag(
            bus, encounter_id,
            concern=allergy_alert_concern(allergen),
            severity="high",
            rationale=allergy_alert_rationale(allergen),
            prior_concerns=fired,
        )
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

        # Re-run LLM safety on transcript activity (don't wait for extraction debounce)
        from redis_layer.state import get_transcript
        full = await get_transcript(encounter_id)
        schedule_debounce(
            f"safety:{encounter_id}",
            SAFETY_DEBOUNCE_MS,
            SAFETY_SILENCE_MS,
            full,
            lambda: _run_safety_analysis(encounter_id),
        )

    async def on_research_completed(envelope: dict) -> None:
        payload = envelope.get("payload", {})
        encounter_id = payload.get("encounterId", "")
        if not encounter_id:
            return
        await _run_safety_analysis(encounter_id)

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
