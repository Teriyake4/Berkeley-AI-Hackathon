"""
Timeline prompts and heuristic fallback — mirrors lib/prompts/timeline.ts.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from events import MedicalEntities, TimelineEntry


TIMELINE_SYSTEM = """You are a clinical timeline agent for pre-hospital EMS/ambulance encounters.
Produce a concise, chronological list of key clinical events from the scene.

Return ONLY a raw JSON array (no markdown):
[{ "id": string, "timestamp": string (ISO 8601), "summary": string, "source": "extraction" }]

Rules:
- Each entry is one sentence, clinical and factual
- Use ambulance context: scene arrival, patient contact, transport, en route — not ER admissions
- Max 12 entries total (merge or drop minor duplicates)
- Timestamps MUST come from the provided transcript lines or anchorTimestamp — never invent times or dates
- source must be "extraction\""""


def _parse_iso(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _match_transcript_timestamp(summary: str, transcript_lines: List[Dict[str, Any]]) -> Optional[str]:
    if not transcript_lines:
        return None
    s = summary.lower()
    pairs = [
        ("chest pain", "chest pain"),
        ("shortness of breath", "shortness of breath"),
        ("left arm", "arm"),
        ("nausea", "nausea"),
        ("penicillin", "penicillin"),
        ("warfarin", "warfarin"),
        ("lisinopril", "lisinopril"),
        ("aspirin", "aspirin"),
        ("hypertension", "blood pressure"),
        ("heart valve", "valve"),
        ("atrial fibrillation", "warfarin"),
        ("allergy", "allerg"),
        ("demographics", "year"),
    ]
    for sum_kw, tx_kw in pairs:
        if sum_kw not in s:
            continue
        for line in transcript_lines:
            text = line.get("text", "").lower()
            if tx_kw in text:
                ts = line.get("timestamp")
                if ts:
                    return ts
    return None


def _resolve_entry_timestamp(
    summary: str,
    anchor_at: str,
    transcript_lines: List[Dict[str, Any]],
    stagger_seconds: int = 0,
) -> str:
    matched = _match_transcript_timestamp(summary, transcript_lines)
    if matched:
        return matched
    anchor = _parse_iso(anchor_at)
    return (anchor + timedelta(seconds=stagger_seconds)).isoformat()


def _normalize_extraction_timestamps(
    events: List[TimelineEntry],
    existing: List[TimelineEntry],
    anchor_at: str,
    transcript_lines: List[Dict[str, Any]],
) -> List[TimelineEntry]:
    existing_by_id = {e.id: e for e in existing if e.source == "extraction"}
    normalized: List[TimelineEntry] = []
    stagger = 0
    for event in events:
        if event.source != "extraction":
            normalized.append(event)
            continue
        if event.id in existing_by_id:
            normalized.append(
                TimelineEntry(
                    id=event.id,
                    timestamp=existing_by_id[event.id].timestamp,
                    summary=event.summary,
                    source="extraction",
                )
            )
            continue
        ts = _resolve_entry_timestamp(event.summary, anchor_at, transcript_lines, stagger)
        stagger += 1
        normalized.append(
            TimelineEntry(
                id=event.id,
                timestamp=ts,
                summary=event.summary,
                source="extraction",
            )
        )
    return normalized


def merge_timeline(
    existing: List[TimelineEntry],
    extraction_events: List[TimelineEntry],
) -> List[TimelineEntry]:
    """Keep non-extraction entries; replace extraction slice with new events."""
    non_extraction = [e for e in existing if e.source != "extraction"]
    merged = non_extraction + extraction_events
    return sorted(merged, key=lambda e: e.timestamp)[-20:]


def build_timeline_prompt(
    entities: MedicalEntities,
    transcript: str,
    existing: List[TimelineEntry],
    anchor_at: str,
    transcript_lines: List[Dict[str, Any]],
) -> str:
    from events import to_dict
    structured = [
        {
            "timestamp": line.get("timestamp"),
            "speaker": line.get("speaker"),
            "text": line.get("text"),
        }
        for line in transcript_lines[-30:]
    ]
    return "\n".join([
        f"anchorTimestamp (ISO — use for new entries when no transcript match): {anchor_at}",
        "",
        "Transcript lines with timestamps (prefer these for each fact):",
        json.dumps(structured, indent=2),
        "",
        "Existing timeline:",
        json.dumps([to_dict(e) for e in existing], indent=2),
        "",
        "Entities:",
        json.dumps(to_dict(entities), indent=2),
        "",
        "Plain transcript (reference):",
        transcript[-2000:],
        "",
        "Return updated extraction timeline JSON array (max 10 entries). Use only provided timestamps.",
    ])


def heuristic_timeline(
    entities: MedicalEntities,
    existing: List[TimelineEntry],
    anchor_at: str,
    transcript_lines: List[Dict[str, Any]],
) -> List[TimelineEntry]:
    entries = [e for e in existing if e.source == "extraction"]
    existing_summaries = {e.summary.lower()[:30] for e in entries}
    stagger = 0

    def add(summary: str) -> None:
        nonlocal stagger
        low = summary.lower()[:30]
        if any(low in s for s in existing_summaries):
            return
        ts = _resolve_entry_timestamp(summary, anchor_at, transcript_lines, stagger)
        stagger += 1
        entries.append(
            TimelineEntry(
                id=f"tl-{uuid.uuid4().hex[:8]}",
                timestamp=ts,
                summary=summary,
                source="extraction",
            )
        )
        existing_summaries.add(low)

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

    return sorted(entries, key=lambda e: e.timestamp)
