"""
Safety prompts and heuristic fallback — mirrors lib/prompts/safety.ts.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List

from events import MedicalEntities, Severity


@dataclass
class SafetyResult:
    concern: str
    severity: Severity
    rationale: str


SAFETY_SYSTEM = """You are a clinical safety flagging agent for pre-hospital EMS/ambulance encounters. For demo purposes only — not for clinical use.

Given medical entities from an ambulance scene encounter, identify safety concerns based ONLY on stated facts.
Return ONLY a raw JSON array (no markdown):
[{ "concern": string, "severity": "low"|"medium"|"high", "rationale": string }]

Return an empty array [] if no concerns are identified.

CRITICAL RULE: Only flag concerns based on STATED facts — never infer from demographics alone (e.g. never flag "age → ACS" without a stated symptom).

Focus on:
- Anticoagulant + acute chest pain — stated warfarin/heparin + stated chest pain
- Drug-drug interactions — e.g. warfarin + aspirin (both must be stated)
- High-risk medication on scene (from vial scan) + patient's known medications
- Allergy + medication cross-check
- Mechanical valve + anticoagulation management"""


def build_safety_prompt(entities: MedicalEntities) -> str:
    from events import to_dict
    return "\n".join([
        "Patient entities:",
        json.dumps(to_dict(entities), indent=2),
        "",
        "Identify safety concerns. Return JSON array.",
    ])


def heuristic_safety(entities: MedicalEntities) -> List[SafetyResult]:
    flags: List[SafetyResult] = []
    meds = [m.name.lower() for m in entities.medications]
    symptoms = [s.lower() for s in entities.symptoms]
    conditions = [c.lower() for c in entities.conditions]
    allergies = [a.lower() for a in entities.allergies]

    has_warfarin = any("warfarin" in m for m in meds)
    has_aspirin = any("aspirin" in m for m in meds)
    has_penicillin_allergy = any("penicillin" in a for a in allergies)
    has_chest_pain = any("chest pain" in s for s in symptoms)
    has_arm_pain = any("arm" in s for s in symptoms)
    has_sob = any("breath" in s for s in symptoms)
    has_heart_valve = any("heart valve" in c for c in conditions)
    age = entities.demographics.age if entities.demographics else 0

    # High severity
    if has_warfarin and has_chest_pain:
        flags.append(SafetyResult(
            concern="Warfarin + chest pain — anticoagulation complicates ACS management",
            severity="high",
            rationale=(
                "Patient on warfarin presenting with acute chest pain. Thrombotic vs. hemorrhagic "
                "risk must be carefully balanced. Check INR before antiplatelet therapy. Mechanical "
                "valve may require uninterrupted anticoagulation."
            ),
        ))

    if has_warfarin and has_aspirin:
        flags.append(SafetyResult(
            concern="Warfarin + aspirin — dual antithrombotic bleeding risk",
            severity="high",
            rationale=(
                "Concurrent warfarin and aspirin significantly increases GI and intracranial bleeding "
                "risk. Ensure benefit clearly outweighs risk before combining."
            ),
        ))

    # Medium severity
    if (age or 0) >= 65 and has_chest_pain and (has_arm_pain or has_sob):
        flags.append(SafetyResult(
            concern="ACS presentation — age ≥65, chest pain, and associated symptoms",
            severity="medium",
            rationale=(
                "Classic ACS feature cluster: age, acute chest pain, arm radiation/dyspnea. "
                "Expedite ECG, troponin, and cardiology consult."
            ),
        ))

    if has_heart_valve and has_warfarin and has_chest_pain:
        flags.append(SafetyResult(
            concern="Mechanical valve patient — warfarin interruption risk",
            severity="medium",
            rationale=(
                "Mechanical heart valve requires continuous anticoagulation. Any interruption carries "
                "thromboembolic stroke risk. Coordinate hematology/cardiology before any warfarin reversal."
            ),
        ))

    # Low severity
    if has_penicillin_allergy:
        flags.append(SafetyResult(
            concern="Penicillin allergy documented — verify ordered antibiotics",
            severity="low",
            rationale=(
                "Patient has documented penicillin allergy. Confirm no penicillin/cephalosporin "
                "(cross-reactivity ~2%) ordered. Use alternative antibiotics if needed."
            ),
        ))

    return flags
