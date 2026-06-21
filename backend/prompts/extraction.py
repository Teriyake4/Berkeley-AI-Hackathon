"""
Extraction prompts and heuristic fallback — mirrors lib/prompts/extraction.ts.
"""
from __future__ import annotations

import json
import re
from typing import Optional

from events import MedicalEntities, Medication, Demographics

EXTRACTION_SYSTEM = """You are a clinical entity extraction agent for pre-hospital EMS/ambulance encounters.
Extract structured medical facts from paramedic-patient scene dialogue.

Return ONLY a raw JSON object matching this exact shape (no markdown, no explanation):
{
  "medications": [{ "name": string, "dose"?: string, "frequency"?: string }],
  "conditions": string[],
  "allergies": string[],
  "vitals": { [key: string]: string },
  "symptoms": string[],
  "demographics": { "age"?: number, "sex"?: string }
}

Rules:
- ALLERGIES ARE MANDATORY: Extract all stated drug/substance allergies immediately when mentioned
- Include every medication (including maintenance meds: lisinopril, warfarin, metoprolol, etc.)
- Symptoms: include chief complaint, onset, duration, location, quality, radiation, and associated symptoms
- Use ambulance context: paramedic, patient, bystander, scene — not ER/hospital terminology
- Do NOT invent facts — only extract what was explicitly stated on scene
- Idempotent merge: never drop previously extracted facts; only add new ones
- Vitals: capture if spoken (BP, HR, SpO2, RR, GCS, temperature)"""


def build_extraction_prompt(transcript: str, existing: Optional[MedicalEntities]) -> str:
    from events import to_dict
    existing_dict = to_dict(existing) if existing else {}
    return "\n".join([
        "Existing entities (preserve all — never drop allergies or medications):",
        json.dumps(existing_dict, indent=2),
        "",
        "New scene dialogue to process:",
        transcript,
        "",
        "IMPORTANT: If allergies are mentioned, they MUST appear in the output.",
        "Return the fully merged entities JSON.",
    ])


def heuristic_extract(transcript: str, existing: Optional[MedicalEntities]) -> MedicalEntities:
    from events import to_dict, entities_from_dict
    import copy

    lower = transcript.lower()
    if existing:
        from events import to_dict, entities_from_dict
        entities = entities_from_dict(to_dict(existing))
    else:
        entities = MedicalEntities()

    def add_med(name: str, dose: Optional[str] = None) -> None:
        if not any(m.name.lower() == name.lower() for m in entities.medications):
            entities.medications.append(Medication(name=name, dose=dose))

    def add_condition(c: str) -> None:
        if not any(x.lower() == c.lower() for x in entities.conditions):
            entities.conditions.append(c)

    def add_symptom(s: str) -> None:
        if not any(x.lower() == s.lower() for x in entities.symptoms):
            entities.symptoms.append(s)

    def add_allergy(a: str) -> None:
        if not any(x.lower() == a.lower() for x in entities.allergies):
            entities.allergies.append(a)

    # Medications
    if "warfarin" in lower:
        add_med("warfarin")
    if "lisinopril" in lower:
        add_med("lisinopril")
    if "aspirin" in lower:
        add_med("aspirin")
    if "metoprolol" in lower:
        add_med("metoprolol")
    if "atorvastatin" in lower or "statin" in lower:
        add_med("atorvastatin")
    if "heparin" in lower:
        add_med("heparin")
    if "nitroglycerin" in lower or "nitro" in lower:
        add_med("nitroglycerin")

    # Allergies
    if "penicillin" in lower and ("allerg" in lower or "reaction" in lower):
        add_allergy("penicillin")
    if "sulfa" in lower and "allerg" in lower:
        add_allergy("sulfa")
    if "nsaid" in lower and "allerg" in lower:
        add_allergy("NSAIDs")

    # Conditions
    if "hypertension" in lower or "high blood pressure" in lower:
        add_condition("hypertension")
    if "heart valve" in lower:
        add_condition("heart valve replacement")
    if "atrial fibrillation" in lower or "afib" in lower:
        add_condition("atrial fibrillation")
    if "diabetes" in lower:
        add_condition("diabetes mellitus")
    if "heart failure" in lower:
        add_condition("heart failure")
    if "coronary artery disease" in lower or " cad " in lower:
        add_condition("coronary artery disease")

    # Symptoms
    if "chest pain" in lower or "chest pressure" in lower:
        add_symptom("chest pain")
    if "shortness of breath" in lower or "short of breath" in lower or "dyspnea" in lower:
        add_symptom("shortness of breath")
    if "left arm" in lower:
        add_symptom("left arm pain")
    if "jaw pain" in lower or "jaw" in lower:
        add_symptom("jaw pain")
    if "nausea" in lower:
        add_symptom("nausea")
    if "diaphoresis" in lower or "sweating" in lower:
        add_symptom("diaphoresis")
    if "dizziness" in lower or "dizzy" in lower:
        add_symptom("dizziness")
    if "palpitation" in lower:
        add_symptom("palpitations")

    # Demographics — age
    age_match = re.search(r"\b(5[5-9]|6[0-9]|7[0-9]|8[0-9])\b", lower)
    demo = entities.demographics or Demographics()
    if age_match:
        demo.age = int(age_match.group(1))
    if re.search(r"\b(male|man|he|his|gentleman)\b", lower):
        demo.sex = "male"
    elif re.search(r"\b(female|woman|she|her|lady)\b", lower):
        demo.sex = "female"
    if demo.age or demo.sex:
        entities.demographics = demo

    return entities
