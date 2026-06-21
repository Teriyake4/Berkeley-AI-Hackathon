"""
SHARED CONTRACT — sync before changing.
All agents and routes import event types from this module.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional
from enum import Enum


# ─── Primitives ────────────────────────────────────────────────────────────────

Speaker = Literal["paramedic", "doctor", "patient", "bystander", "unknown"]
Severity = Literal["low", "medium", "high"]


@dataclass
class TimelineEntry:
    id: str
    timestamp: str  # ISO 8601
    summary: str
    source: Optional[Literal["extraction", "safety", "manual"]] = None


@dataclass
class Medication:
    name: str
    dose: Optional[str] = None
    frequency: Optional[str] = None
    source: Optional[str] = None  # "stated" | "vision"


@dataclass
class Demographics:
    age: Optional[int] = None
    sex: Optional[str] = None


@dataclass
class MedicalEntities:
    medications: List[Medication] = field(default_factory=list)
    conditions: List[str] = field(default_factory=list)
    allergies: List[str] = field(default_factory=list)
    vitals: Dict[str, str] = field(default_factory=dict)
    symptoms: List[str] = field(default_factory=list)
    demographics: Optional[Demographics] = None


@dataclass
class SoapNote:
    subjective: str
    objective: str
    assessment: str
    plan: str


@dataclass
class Citation:
    title: str
    url: str
    snippet: Optional[str] = None


@dataclass
class HandoffReport:
    patientSummary: str
    timeline: List[TimelineEntry]
    currentMedications: List[Medication]
    outstandingQuestions: List[str]
    recommendedActions: List[str]
    generatedAt: str  # ISO 8601
    allergies: List[str] = field(default_factory=list)


# ─── Event payloads ─────────────────────────────────────────────────────────────

@dataclass
class TranscriptSegmentPayload:
    encounterId: str
    text: str
    speaker: Speaker
    timestamp: str


@dataclass
class FactsExtractedPayload:
    encounterId: str
    entities: MedicalEntities
    extractedAt: str


@dataclass
class TimelineUpdatedPayload:
    encounterId: str
    events: List[TimelineEntry]


@dataclass
class SafetyFlaggedPayload:
    encounterId: str
    concern: str
    severity: Severity
    rationale: str
    flaggedAt: str


@dataclass
class NoteUpdatedPayload:
    encounterId: str
    soap: SoapNote
    updatedAt: str


@dataclass
class ResearchCompletedPayload:
    encounterId: str
    query: str
    findings: str
    citations: List[Citation]
    completedAt: str


@dataclass
class HandoffRequestedPayload:
    encounterId: str
    requestedAt: str


@dataclass
class HandoffGeneratedPayload:
    encounterId: str
    report: HandoffReport


@dataclass
class AudioEventPayload:
    encounterId: str
    type: str  # e.g. "silence", "alarm", "distress", "monitor_tone"
    timestamp: str
    detail: Optional[str] = None


@dataclass
class TelemetryUpdatedPayload:
    encounterId: str
    event: str  # e.g. "scene_arrival", "patient_contact", "en_route", "hospital_arrival"
    timestamp: str
    label: Optional[str] = None


@dataclass
class VisionCapturedPayload:
    encounterId: str
    identified: str  # e.g. "aspirin 325mg"
    captureType: str  # e.g. "vial_label", "bracelet", "wound"
    timestamp: str
    rawText: Optional[str] = None


# ─── Event channels ─────────────────────────────────────────────────────────────

class EventChannels:
    TRANSCRIPT_SEGMENT = "transcript.segment"
    FACTS_EXTRACTED = "facts.extracted"
    TIMELINE_UPDATED = "timeline.updated"
    SAFETY_FLAGGED = "safety.flagged"
    NOTE_UPDATED = "note.updated"
    RESEARCH_COMPLETED = "research.completed"
    HANDOFF_REQUESTED = "handoff.requested"
    HANDOFF_GENERATED = "handoff.generated"
    AUDIO_EVENT = "audio.event"
    TELEMETRY_UPDATED = "telemetry.updated"
    VISION_CAPTURED = "vision.captured"


EVENT_CHANNELS = EventChannels()


def create_event(channel: str, payload: Any) -> Dict[str, Any]:
    return {"channel": channel, "payload": payload}


# ─── Serialization helpers ───────────────────────────────────────────────────────

import json
import dataclasses


def to_dict(obj: Any) -> Any:
    """Recursively convert dataclasses to plain dicts."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: to_dict(v) for k, v in dataclasses.asdict(obj).items() if v is not None}
    if isinstance(obj, list):
        return [to_dict(i) for i in obj]
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    return obj


def entities_from_dict(d: Dict) -> MedicalEntities:
    if not d:
        return MedicalEntities()
    meds = [_med_from_dict(m) for m in d.get("medications", [])]
    demo_raw = d.get("demographics")
    demo = Demographics(**demo_raw) if isinstance(demo_raw, dict) and demo_raw else None
    return MedicalEntities(
        medications=meds,
        conditions=d.get("conditions", []),
        allergies=d.get("allergies", []),
        vitals=d.get("vitals", {}),
        symptoms=d.get("symptoms", []),
        demographics=demo,
    )


def timeline_entry_from_dict(d: Dict) -> TimelineEntry:
    return TimelineEntry(
        id=d["id"],
        timestamp=d["timestamp"],
        summary=d["summary"],
        source=d.get("source"),
    )


def soap_from_dict(d: Dict) -> SoapNote:
    return SoapNote(
        subjective=d.get("subjective", ""),
        objective=d.get("objective", ""),
        assessment=d.get("assessment", ""),
        plan=d.get("plan", ""),
    )


def _med_from_dict(m):
    if not isinstance(m, dict):
        return m
    return Medication(
        name=m.get("name", ""),
        dose=m.get("dose"),
        frequency=m.get("frequency"),
        source=m.get("source"),
    )


def handoff_from_dict(d: Dict) -> HandoffReport:
    return HandoffReport(
        patientSummary=d.get("patientSummary", ""),
        allergies=d.get("allergies", []),
        timeline=[timeline_entry_from_dict(e) for e in d.get("timeline", [])],
        currentMedications=[_med_from_dict(m) for m in d.get("currentMedications", [])],
        outstandingQuestions=d.get("outstandingQuestions", []),
        recommendedActions=d.get("recommendedActions", []),
        generatedAt=d.get("generatedAt", ""),
    )
