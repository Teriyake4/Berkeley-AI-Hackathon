"""
Safety prompts and heuristic fallback — mirrors lib/prompts/safety.ts.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List, Optional

from events import MedicalEntities, Severity


@dataclass
class SafetyResult:
    concern: str
    severity: Severity
    rationale: str
    clarifyingQuestion: Optional[str] = None
    recommendedActions: Optional[List[str]] = None


SAFETY_SYSTEM = """You are a comprehensive clinical safety intelligence agent for Nos, a pre-hospital EMS AI assistant. For demo purposes only — not for clinical use.

You receive the patient's full clinical picture plus research briefs generated for each identified entity. Your job: reason holistically across ALL of this and flag every situation that could cause patient harm.

Return ONLY a raw JSON array (no markdown):
[{
  "concern": string,
  "severity": "low"|"medium"|"high"|"critical",
  "rationale": string,
  "sourceEntities": string[],
  "clarifyingQuestion": string|null,
  "recommendedActions": string[]
}]

Return [] if no concerns found.

RULES:
- Only flag concerns grounded in STATED facts from the transcript or extracted entities
- Never infer from demographics alone — age without a stated symptom is not a flag
- Use "consider …" / "verify …" language — never a definitive diagnosis
- sourceEntities: list the specific entity names that triggered this concern
- clarifyingQuestion: a single targeted question the paramedic should ask or verify RIGHT NOW to resolve uncertainty; null if the danger is already confirmed by stated facts

SEVERITY TIERS — pick exactly one:
- critical: imminent life threat requiring immediate action (e.g. known allergy + drug being administered, active hemorrhage + anticoagulant, airway compromise)
- high: serious risk — act before hospital arrival (e.g. warfarin + chest pain, head trauma + blood thinner, unknown INR in anticoagulated ACS patient)
- medium: significant concern — document and hand off (e.g. drug combination that raises bleeding risk but no active bleeding, condition that could deteriorate)
- low: worth noting — monitor or ask (e.g. mild interaction, missing routine information, ambiguous history detail)

USE clarifyingQuestion WHEN:
- The risk level depends on information not yet stated (e.g. "Is the patient's INR currently therapeutic?")
- A symptom could have two very different causes with very different treatments (e.g. "Is the altered mental status new or chronic?")
- A medication's safety depends on an unknown factor (e.g. "When was the last dose of warfarin taken?")
- You can see a potential danger but need one more fact to confirm it

Leave clarifyingQuestion null when the stated facts alone are sufficient to confirm the danger.

recommendedActions: always populate — concrete, ordered steps the paramedic should take RIGHT NOW.
- If clarifyingQuestion is set: actions should cover what to do while waiting for the answer AND what to do for each likely answer (e.g. "If INR > 3: hold antiplatelet, notify ED; If INR ≤ 2: antiplatelet may proceed with caution")
- If danger is confirmed: specific pre-hospital interventions, what to avoid, what to communicate to the receiving ED
- Keep each action to one sentence, imperative, specific (not "monitor patient" — "monitor SpO2 every 2 minutes, target ≥ 94%")

THINK LIKE A SENIOR EMERGENCY PHYSICIAN reviewing the full chart before the patient arrives:
- Every drug: how does it interact with their conditions, injuries, scene, and other drugs?
- Every condition: what drugs are contraindicated? What complications should be watched for?
- Every allergy: what could plausibly be administered on scene that would trigger a reaction?
- Every injury or significant symptom: how does it interact with existing medications and conditions?
- Vision scan findings: do any identified substances conflict with known meds, allergies, or conditions?
- The trajectory: are there risks in how this patient will be received at the ED?
- Missing information: is there something unknown that could be critical (e.g. INR unknown for anticoagulated patient)?

Use the research briefs to inform your reasoning — they contain known risks, interactions, and contraindications for each identified entity. Do not limit yourself to the examples in the briefs; reason beyond them.

Be comprehensive — it is better to flag something the paramedic dismisses than to miss something grave."""


def build_safety_prompt(
    entities: MedicalEntities,
    transcript: str = "",
    research_briefs: list | None = None,
) -> str:
    from events import to_dict
    parts = [
        "=== PATIENT ENTITIES (extracted from scene) ===",
        json.dumps(to_dict(entities), indent=2),
    ]
    if transcript.strip():
        parts += [
            "",
            "=== SCENE TRANSCRIPT (last 2000 chars) ===",
            transcript[-2000:],
        ]
    if research_briefs:
        parts += ["", "=== CLINICAL RESEARCH BRIEFS (generated for each identified entity) ==="]
        for brief in research_briefs:
            entity = brief.get("entity", "unknown")
            entity_type = brief.get("entityType", "")
            cb = brief.get("clinicalBrief") or {}
            parts.append(f"\n--- {entity} ({entity_type}) ---")
            if cb.get("summary"):
                parts.append(f"Summary: {cb['summary']}")
            if cb.get("keyRisks"):
                parts.append("Key risks: " + "; ".join(cb["keyRisks"]))
            if cb.get("drugInteractions"):
                parts.append("Drug interactions: " + "; ".join(cb["drugInteractions"]))
            if cb.get("contraindications"):
                parts.append("Contraindications: " + "; ".join(cb["contraindications"]))
            if cb.get("preHospitalActions"):
                parts.append("Pre-hospital actions: " + "; ".join(cb["preHospitalActions"]))
            elif brief.get("findings"):
                parts.append(f"Findings: {brief['findings']}")
    parts += ["", "=== TASK ===", "Identify ALL safety concerns. Return JSON array."]
    return "\n".join(parts)


def _allergen_stem(name: str) -> str:
    """Normalize allergen name for fuzzy matching (peaches → peach)."""
    token = name.lower().strip()
    if token.endswith("ies"):
        return token[:-3] + "y"
    if token.endswith("es") and len(token) > 3:
        return token[:-2]
    if token.endswith("s") and len(token) > 3:
        return token[:-1]
    return token


def _allergen_in_text(allergen: str, text: str) -> bool:
    stem = _allergen_stem(allergen)
    lower = text.lower()
    return stem in lower or allergen.lower() in lower


def heuristic_allergy_flags(
    entities: MedicalEntities,
    transcript: str = "",
) -> List[SafetyResult]:
    """Flag administration conflicts and medication-allergy cross-checks."""
    flags: List[SafetyResult] = []
    allergies = entities.allergies
    if not allergies:
        return flags

    tl = transcript.lower()
    admin_keywords = (
        "giving", "give you", "give him", "give her", "administer",
        "administered", "feed", "feeding", "inject", "injected",
        "start you on", "put you on", "going to give", "i'll give",
        "thinking about giving",
    )
    has_admin_intent = any(kw in tl for kw in admin_keywords)

    for allergy in allergies:
        if has_admin_intent and _allergen_in_text(allergy, tl):
            flags.append(SafetyResult(
                concern=f"CRITICAL: Proposed/administered {allergy} despite documented allergy",
                severity="high",
                rationale=(
                    f"Transcript indicates paramedic may give or has given '{allergy}' "
                    f"while patient has documented {allergy} allergy. "
                    "STOP — risk of anaphylaxis or severe allergic reaction."
                ),
            ))

    meds = [m.name.lower() for m in entities.medications]
    for allergy in allergies:
        stem = _allergen_stem(allergy)
        for med in meds:
            if stem in med or med in stem:
                flags.append(SafetyResult(
                    concern=f"Medication conflict: {med} vs documented {allergy} allergy",
                    severity="high",
                    rationale=(
                        f"Patient is documented on {med} but has stated allergy to {allergy}. "
                        "Verify compatibility before administration."
                    ),
                ))

    return flags


def heuristic_safety(entities: MedicalEntities, transcript: str = "") -> List[SafetyResult]:
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

    # Allergies — administration conflicts and med cross-checks
    flags.extend(heuristic_allergy_flags(entities, transcript))

    # Drug-drug interactions among all documented/active medications
    from prompts.drug_interactions import check_interactions, check_situational_risks
    flags.extend(check_interactions(meds))

    # Situational risks: injuries, scene context, vitals + medications
    flags.extend(check_situational_risks(meds, entities.symptoms, entities.conditions, transcript))

    if has_penicillin_allergy:
        flags.append(SafetyResult(
            concern="Penicillin allergy — avoid beta-lactam antibiotics",
            severity="high",
            rationale=(
                "Patient has documented penicillin allergy. Confirm no penicillin/cephalosporin "
                "(cross-reactivity ~2%) ordered. Use alternative antibiotics if needed."
            ),
        ))

    return flags
