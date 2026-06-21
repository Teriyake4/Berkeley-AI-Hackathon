"""
Timeline prompts and heuristic fallback — mirrors lib/prompts/timeline.ts.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import List

from events import MedicalEntities, TimelineEntry


TIMELINE_SYSTEM = """You are a clinical timeline agent for pre-hospital EMS/ambulance encounters.
Produce a concise, chronological list of key clinical events from the scene.

Return ONLY a raw JSON array (no markdown):
[{ "id": string, "timestamp": string (ISO 8601), "summary": string, "source": "extraction" }]

Rules:
- Each entry is one sentence, clinical and factual
- Use ambulance context: scene arrival, patient contact, transport, en route — not ER admissions
- Max 12 entries total (merge or drop minor duplicates)
- Use realistic timestamps spread across the encounter (start from scene arrival)
- source must be "extraction\""""


def build_timeline_prompt(
    entities: MedicalEntities,
    transcript: str,
    existing: List[TimelineEntry],
) -> str:
    from events import to_dict
    today = datetime.now(timezone.utc).date().isoformat()
    return "\n".join([
        f"Today: {today}",
        "",
        "Existing timeline:",
        json.dumps([to_dict(e) for e in existing], indent=2),
        "",
        "Entities:",
        json.dumps(to_dict(entities), indent=2),
        "",
        "Transcript:",
        transcript[-2000:],
        "",
        "Return updated timeline JSON array (max 10 entries).",
    ])


def heuristic_timeline(
    entities: MedicalEntities,
    existing: List[TimelineEntry],
) -> List[TimelineEntry]:
    entries = [e for e in existing if e.source != "extraction"]
    safety_entries = [e for e in existing if e.source == "safety"]

    base_dt = datetime.now(timezone.utc) - timedelta(minutes=20)
    offset = [0]  # mutable counter

    def add(summary: str) -> None:
        low = summary.lower()[:30]
        if any(low in e.summary.lower() for e in entries):
            return
        if any(low in e.summary.lower() for e in safety_entries):
            return
        ts = (base_dt + timedelta(seconds=offset[0] * 90)).isoformat()
        entries.append(TimelineEntry(
            id=f"tl-{uuid.uuid4().hex[:8]}",
            timestamp=ts,
            summary=summary,
            source="extraction",
        ))
        offset[0] += 1

    age = entities.demographics.age if entities.demographics else None
    sex = entities.demographics.sex if entities.demographics else None

    if age or sex:
        demo = " ".join(filter(None, [f"{age}yo" if age else None, sex]))
        add(f"Patient demographics: {demo}")

    if any("chest pain" in s for s in entities.symptoms):
        add("Patient reports acute chest pain")
    if any("shortness of breath" in s for s in entities.symptoms):
        add("Mild shortness of breath reported")
    if any("left arm" in s for s in entities.symptoms):
        add("Left arm radiation noted")
    if any("nausea" in s for s in entities.symptoms):
        add("Nausea reported")

    if any("hypertension" in c for c in entities.conditions):
        add("Hypertension history identified")
    if any("heart valve" in c for c in entities.conditions):
        add("Mechanical heart valve replacement history noted")
    if any("atrial fibrillation" in c for c in entities.conditions):
        add("Atrial fibrillation history identified")

    if any(m.name.lower() == "lisinopril" for m in entities.medications):
        add("Lisinopril (ACE inhibitor) documented")
    if any(m.name.lower() == "warfarin" for m in entities.medications):
        add("Warfarin anticoagulation documented")
    if any(m.name.lower() == "aspirin" for m in entities.medications):
        add("Aspirin ordered/documented")

    if any("penicillin" in a.lower() for a in entities.allergies):
        add("Penicillin allergy documented")
    elif entities.allergies:
        add(f"Allergy documented: {entities.allergies[0]}")

    combined = sorted(entries + safety_entries, key=lambda e: e.timestamp)
    return combined[-12:]
