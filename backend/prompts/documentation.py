"""
Documentation (SOAP note) prompts and heuristic fallback — mirrors lib/prompts/documentation.ts.
"""
from __future__ import annotations

import json
from typing import List

from events import MedicalEntities, SoapNote, TimelineEntry


DOCUMENTATION_SYSTEM = """You are a clinical documentation agent for Nos, a pre-hospital EMS/ambulance AI assistant. For demo purposes only — not for clinical use.

Generate a live SOAP note from paramedic-patient scene dialogue.

Return ONLY a raw JSON object (no markdown):
{ "subjective": string, "objective": string, "assessment": string, "plan": string }

Guidelines:
- Subjective: Chief complaint and HPI (onset, duration, location, quality, radiation, associated symptoms), ALLERGIES first and prominently, current medications, PMH — all from stated scene facts only
- Objective: Vitals documented on scene (BP, HR, SpO2, RR); if not yet taken note "pending on scene"
- Assessment: Working impression using "consider …" / "verify …" language — no diagnosis; respect anticoagulation status
- Plan: Immediate pre-hospital interventions and handoff priorities; cite anticoagulation before any antiplatelet recommendation"""


def build_documentation_prompt(
    entities: MedicalEntities,
    timeline: List[TimelineEntry],
    transcript: str,
) -> str:
    from events import to_dict
    return "\n".join([
        "Patient entities:",
        json.dumps(to_dict(entities), indent=2),
        "",
        "Timeline:",
        json.dumps([to_dict(e) for e in timeline], indent=2),
        "",
        "Transcript:",
        transcript[-2000:],
        "",
        "Generate SOAP note JSON.",
    ])


def heuristic_soap(entities: MedicalEntities, timeline: List[TimelineEntry]) -> SoapNote:
    age = entities.demographics.age if entities.demographics else None
    sex = entities.demographics.sex if entities.demographics else None
    demo = " ".join(filter(None, [f"{age}-year-old" if age else None, sex]))

    meds = ", ".join(m.name for m in entities.medications) or "none documented"
    symptoms = ", ".join(entities.symptoms) if entities.symptoms else "acute symptoms"
    conditions = ", ".join(entities.conditions) if entities.conditions else "none documented"
    allergies = ", ".join(entities.allergies) if entities.allergies else "NKDA"

    has_warfarin = any("warfarin" in m.name.lower() for m in entities.medications)
    has_chest_pain = any("chest pain" in s for s in entities.symptoms)
    has_arm_pain = any("arm" in s for s in entities.symptoms)
    has_sob = any("breath" in s for s in entities.symptoms)

    acs_features = ", ".join(filter(None, [
        "chest pain" if has_chest_pain else None,
        "arm radiation" if has_arm_pain else None,
        "dyspnea" if has_sob else None,
    ]))

    if has_chest_pain and has_warfarin:
        assessment = (
            f"Acute {acs_features or 'chest pain'} in anticoagulated patient with cardiac history. "
            "Primary concern: ACS. Mechanical valve complicates management."
        )
    elif has_chest_pain:
        assessment = f"Acute {acs_features or 'chest pain'}. Rule out ACS, aortic dissection, PE."
    else:
        assessment = "Acute presentation under evaluation."

    if has_warfarin:
        plan = (
            "1. Stat ECG and serial troponins\n"
            "2. Check INR before antiplatelet therapy\n"
            "3. Cardiology consult stat\n"
            "4. Assess bleed vs. thrombosis risk before aspirin\n"
            "5. IV access, continuous monitoring"
        )
    else:
        plan = (
            "1. Stat ECG and serial troponins\n"
            "2. Aspirin 325mg (absent contraindications)\n"
            "3. Cardiology consult\n"
            "4. IV access, continuous monitoring"
        )

    return SoapNote(
        subjective=(
            f"{demo or 'Patient'} presenting with {symptoms}. "
            f"PMH: {conditions}. Current medications: {meds}. Allergies: {allergies}."
        ),
        objective="Vitals pending. Physical exam not yet documented. ECG and troponin ordered.",
        assessment=assessment,
        plan=plan,
    )
