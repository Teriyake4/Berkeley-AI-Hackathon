"""
Handoff report prompts and heuristic fallback — mirrors lib/prompts/handoff.ts.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import List, Optional

from events import HandoffReport, MedicalEntities, SoapNote, TimelineEntry


HANDOFF_SYSTEM = """You are generating a pre-hospital to ED handoff report for Nos, an ambulance AI assistant. For demo purposes only — not for clinical use.

Summarise everything documented during the ambulance scene and transport for the receiving ED team.

Return ONLY a raw JSON object (no markdown):
{
  "patientSummary": string,
  "allergies": string[],
  "timeline": [{ "id": string, "timestamp": string, "summary": string, "source": "extraction" }],
  "currentMedications": [{ "name": string, "dose"?: string }],
  "outstandingQuestions": string[],
  "recommendedActions": string[],
  "generatedAt": string
}

Requirements:
- patientSummary: 2-3 sentences — demographics, chief complaint, ALLERGIES (always include even if NKDA), relevant PMH, anticoagulation status
- allergies: list every documented drug/substance allergy as an array (empty array if none stated)
- timeline: GPS-anchored chronological events from scene to arrival (max 8); include telemetry and vision scan entries
- outstandingQuestions: specific unanswered clinical questions (e.g. "Current INR?", "Last oral intake?")
- recommendedActions: ordered next steps for the ED team; anticoagulation check before any antiplatelet recommendation
- generatedAt: current ISO timestamp"""


def build_handoff_prompt(
    entities: MedicalEntities,
    timeline: List[TimelineEntry],
    transcript: str,
    soap: Optional[SoapNote],
) -> str:
    from events import to_dict
    return "\n".join([
        "Entities:",
        json.dumps(to_dict(entities), indent=2),
        "",
        "Timeline:",
        json.dumps([to_dict(e) for e in timeline], indent=2),
        "",
        "SOAP note:",
        json.dumps(to_dict(soap) if soap else None, indent=2),
        "",
        "Full transcript:",
        transcript[-12000:],
        "",
        "Generate the structured handoff report JSON.",
    ])


def heuristic_handoff(
    entities: MedicalEntities,
    timeline: List[TimelineEntry],
) -> HandoffReport:
    age = entities.demographics.age if entities.demographics else "?"
    sex = entities.demographics.sex if entities.demographics else "patient"
    conditions = ", ".join(entities.conditions) or "none documented"
    has_warfarin = any("warfarin" in m.name.lower() for m in entities.medications)
    has_penicillin_allergy = any("penicillin" in a.lower() for a in entities.allergies)
    symptoms = ", ".join(entities.symptoms) or "acute symptoms"

    outstanding = list(filter(None, [
        "Current INR value?" if has_warfarin else None,
        "Pain severity 1–10?",
        "Prior cardiac workup / stress testing?",
        "Last warfarin dose and time?" if has_warfarin else None,
        "Family history of cardiac disease?",
    ]))

    actions = list(filter(None, [
        "Stat ECG — review for ST changes",
        "Serial troponins (0h, 3h, 6h)",
        "Cardiology consult stat",
        (
            "Check INR before initiating antiplatelet therapy — weigh bleed vs thrombosis risk"
            if has_warfarin else
            "Aspirin 325mg if no contraindications"
        ),
        "IV access and continuous cardiac monitoring",
        (
            "Confirm no penicillin/cephalosporin ordered (allergy documented)"
            if has_penicillin_allergy else None
        ),
        "Portable CXR",
    ]))

    meds_str = ", ".join(m.name for m in entities.medications) or "none"
    allergies_str = ", ".join(entities.allergies) or "NKDA"

    return HandoffReport(
        patientSummary=(
            f"{age}-year-old {sex} presenting with {symptoms}. "
            f"PMH: {conditions}. Medications: {meds_str}. Allergies: {allergies_str}."
        ),
        timeline=timeline[-8:],
        currentMedications=entities.medications,
        outstandingQuestions=outstanding,
        recommendedActions=actions,
        generatedAt=datetime.now(timezone.utc).isoformat(),
    )
