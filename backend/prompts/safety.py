"""
Safety prompts and heuristic fallback — mirrors lib/prompts/safety.ts.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List, Optional, Optional

from events import MedicalEntities, Severity


@dataclass
class SafetyResult:
    concern: str
    severity: Severity
    rationale: str
    clarifyingQuestion: Optional[str] = None
    recommendedActions: Optional[List[str]] = None


SAFETY_SYSTEM = """You are the safety intelligence layer for Nos, a pre-hospital EMS AI assistant. For demo purposes only — not for clinical use.

You will receive a structured patient chart compiled from everything said and observed on scene. Read it like a senior ER physician getting a radio handoff, then flag EVERY situation that could harm the patient — whether it's a complex drug interaction, a common-sense physical danger, a missing piece of critical information, or something a reasonable person would immediately recognise as dangerous.

Return ONLY a raw JSON array (no markdown fences, no preamble):
[{
  "concern": string,          // one-line summary of the danger
  "severity": "low"|"medium"|"high"|"critical",
  "rationale": string,        // 1-3 sentences explaining exactly why this is dangerous given the stated facts
  "clarifyingQuestion": string|null,
  "recommendedActions": string[]  // ordered, concrete, imperative — at least 2
}]

Return [] if no concerns found.

---

SEVERITY — pick exactly one:
- critical: act RIGHT NOW or patient may die / suffer permanent harm (e.g. administering allergen, active haemorrhage + anticoagulant, airway compromise, dangerous manipulation of unstable limb)
- high: act before hospital arrival (e.g. warfarin + chest pain, head trauma + blood thinner, serious drug interaction, severe allergy documented)
- medium: document and hand off — will matter at the ED (e.g. drug combination raising risk, condition that may deteriorate, missing history that affects treatment)
- low: note and ask — low urgency but worth capturing (mild interaction, ambiguous detail, routine missing info)

---

WHAT TO FLAG — cast a wide net, not just drug interactions:

1. COMMON SENSE DANGERS
   - Is anyone proposing to do something obviously harmful? (e.g. shaking an unstable limb, removing a stabilising object from a penetrating wound, moving a spinal injury incorrectly)
   - Does the scene context suggest a risk the patient hasn't named? (e.g. mechanism of injury implies spinal risk even if no neck pain stated)
   - Is the paramedic about to give something the patient just said they're allergic to?

2. DRUG INTERACTIONS & PHARMACOLOGY
   - Every drug vs every other drug — known interactions, additive effects, contraindications
   - Every drug vs every condition — e.g. beta-blockers in asthma, NSAIDs in renal failure, opioids in head injury
   - Every drug vs the injury/scene — e.g. anticoagulant + active bleeding, vasodilator + hypotension

3. ALLERGY CONFLICTS
   - Is any drug, food, or substance mentioned on scene related to a stated allergy?
   - Cross-reactivity: penicillin allergy → cephalosporin risk; sulfa → some diuretics; NSAID → aspirin

4. MISSING CRITICAL INFORMATION
   - What does a paramedic NEED to know before administering anything or making a treatment decision that hasn't been asked yet?
   - NREMT gaps: allergies, current medications, last oral intake, events leading to incident, pertinent negatives
   - Unknown values that change the treatment plan (e.g. INR unknown for anticoagulated patient, glucose unknown for altered mental status)

5. TRAJECTORY RISKS
   - What might go wrong between now and hospital arrival?
   - What does the ED need to know that could be missed without this flag?
   - Is there a time-sensitive intervention window closing? (e.g. tPA window in stroke, golden hour in trauma)

6. VISION & SCENE FINDINGS
   - Do any items identified by the camera (medications, substances, injuries) conflict with stated allergies, medications, or conditions?
   - Is anything in the scene context (mechanism of injury, environment) a risk factor?

---

RULES:
- Only flag things grounded in STATED facts, observed entities, or direct logical inference from them
- Never flag based on demographics alone (age is not a flag without a symptom or drug)
- Use "consider", "verify", "ensure" language — never a definitive diagnosis
- clarifyingQuestion: ONE specific question the paramedic should ask RIGHT NOW to resolve uncertainty — null if the danger is already confirmed
- recommendedActions: always include, always concrete and imperative ("Monitor SpO2 every 2 minutes, target ≥ 94%" not "monitor patient")
  - If clarifyingQuestion set: cover both branches (if yes / if no)
  - If danger confirmed: specific pre-hospital steps + what to relay to ED

Be comprehensive. A paramedic can dismiss a flag you raise. They cannot act on a danger you missed."""


_VALID_SEVERITIES = frozenset({"low", "medium", "high", "critical"})


def parse_safety_flag(item: object) -> Optional[SafetyResult]:
    """Parse one LLM flag item, ignoring extra fields like sourceEntities."""
    if isinstance(item, SafetyResult):
        return item
    if not isinstance(item, dict):
        return None
    concern = item.get("concern")
    if not concern or not isinstance(concern, str):
        return None
    severity = item.get("severity", "medium")
    if severity not in _VALID_SEVERITIES:
        severity = "medium"
    return SafetyResult(
        concern=concern,
        severity=severity,
        rationale=str(item.get("rationale") or ""),
        clarifyingQuestion=item.get("clarifyingQuestion"),
        recommendedActions=item.get("recommendedActions"),
    )


def parse_safety_flags_from_llm(items: list) -> List[SafetyResult]:
    flags: List[SafetyResult] = []
    for item in items:
        parsed = parse_safety_flag(item)
        if parsed:
            flags.append(parsed)
    return flags


def build_safety_prompt(
    entities: MedicalEntities,
    transcript: str = "",
    research_briefs: list | None = None,
    *,
    active_meds: list | None = None,
    vision_items: list | None = None,
    nremt_gaps: list | None = None,
    recent_actions: list | None = None,
) -> str:
    """
    Build the full patient chart that the LLM reasons over.

    Design philosophy: compile EVERYTHING known about this patient into a
    readable, structured markdown document that resembles a clinical chart.
    The LLM was trained on charts; markdown prose is easier to reason over
    than raw JSON. The entities section is the authoritative accumulated
    record; the transcript is recent context; everything else adds breadth.
    """
    lines: list[str] = ["# PATIENT SAFETY CHART\n"]
    lines.append(
        "> This chart is compiled from the full encounter so far. "
        "All facts are stated or directly observed — nothing is inferred from demographics alone.\n"
    )

    # ── PATIENT PROFILE ──────────────────────────────────────────────────────
    lines.append("## Patient Profile")
    demo = entities.demographics
    if demo:
        age = getattr(demo, "age", None) or getattr(demo, "ageRange", None)
        sex = getattr(demo, "sex", None) or getattr(demo, "gender", None)
        weight = getattr(demo, "weight", None)
        bits = []
        if age:
            bits.append(f"Age: {age}")
        if sex:
            bits.append(f"Sex: {sex}")
        if weight:
            bits.append(f"Weight: {weight}")
        lines.append(", ".join(bits) if bits else "_Unknown_")
    else:
        lines.append("_No demographics recorded yet_")
    lines.append("")

    # ── CHIEF COMPLAINT / SYMPTOMS ──────────────────────────────────────────
    lines.append("## Chief Complaint & Symptoms")
    syms = getattr(entities, "symptoms", []) or []
    cc = getattr(entities, "chiefComplaint", None) or getattr(entities, "chief_complaint", None)
    if cc:
        lines.append(f"**Chief complaint:** {cc}")
    if syms:
        for s in syms:
            name = getattr(s, "name", str(s))
            severity = getattr(s, "severity", None)
            onset = getattr(s, "onset", None)
            detail = name
            if severity:
                detail += f" (severity: {severity})"
            if onset:
                detail += f" — onset: {onset}"
            lines.append(f"- {detail}")
    else:
        lines.append("_No symptoms recorded_")
    lines.append("")

    # ── ALLERGIES (HIGH-PRIORITY) ────────────────────────────────────────────
    lines.append("## ⚠ Allergies")
    allergies = getattr(entities, "allergies", []) or []
    if allergies:
        for a in allergies:
            name = getattr(a, "name", str(a))
            reaction = getattr(a, "reaction", None)
            line = f"- **{name}**"
            if reaction:
                line += f" → reaction: {reaction}"
            lines.append(line)
    else:
        lines.append("_No allergies stated (allergy status may be unknown — see gaps below)_")
    lines.append("")

    # ── MEDICATIONS ─────────────────────────────────────────────────────────
    lines.append("## Medications")
    meds = getattr(entities, "medications", []) or []
    # Deduplicate against active_meds list
    active_set: set[str] = set()
    if active_meds:
        lines.append("### Administered On-Scene")
        for m in active_meds:
            lines.append(f"- {m} _(administered by paramedic)_")
            active_set.add(m.lower().strip())
        lines.append("")
    if meds:
        lines.append("### Patient's Reported Medications")
        for m in meds:
            name = getattr(m, "name", str(m))
            if name.lower().strip() in active_set:
                continue
            dose = getattr(m, "dose", None)
            freq = getattr(m, "frequency", None)
            source = getattr(m, "source", None)
            detail = f"- {name}"
            if dose:
                detail += f" {dose}"
            if freq:
                detail += f", {freq}"
            if source and source not in ("stated", ""):
                detail += f" _(source: {source})_"
            lines.append(detail)
    if vision_items:
        lines.append("### Identified by Camera")
        for vi in vision_items:
            label = vi.get("label_text") or vi.get("labelText") or vi.get("type", "unknown")
            confidence = vi.get("confidence", "")
            lines.append(f"- {label} _(vision scan, confidence: {confidence})_")
    if not meds and not active_meds and not vision_items:
        lines.append("_No medications recorded_")
    lines.append("")

    # ── CONDITIONS / PMH ────────────────────────────────────────────────────
    lines.append("## Medical Conditions / Past Medical History")
    conditions = getattr(entities, "conditions", []) or []
    if conditions:
        for c in conditions:
            name = getattr(c, "name", str(c))
            status = getattr(c, "status", None)
            detail = f"- {name}"
            if status:
                detail += f" ({status})"
            lines.append(detail)
    else:
        lines.append("_None stated_")
    lines.append("")

    # ── INJURIES ────────────────────────────────────────────────────────────
    injuries = getattr(entities, "injuries", []) or []
    if injuries:
        lines.append("## Injuries")
        for inj in injuries:
            name = getattr(inj, "name", str(inj))
            loc = getattr(inj, "location", None)
            sev = getattr(inj, "severity", None)
            detail = f"- {name}"
            if loc:
                detail += f" — location: {loc}"
            if sev:
                detail += f" (severity: {sev})"
            lines.append(detail)
        lines.append("")

    # ── VITALS ──────────────────────────────────────────────────────────────
    vitals = getattr(entities, "vitals", None) or {}
    if vitals:
        lines.append("## Vitals")
        if isinstance(vitals, dict):
            for k, v in vitals.items():
                if v is not None:
                    lines.append(f"- {k}: {v}")
        lines.append("")

    # ── RECENT PARAMEDIC ACTIONS ─────────────────────────────────────────────
    if recent_actions:
        lines.append("## Recent Paramedic Actions / Plans")
        lines.append("_(What the paramedic has said they are doing or about to do)_")
        for action in recent_actions[-10:]:
            lines.append(f"- {action}")
        lines.append("")

    # ── ASSESSMENT GAPS (NREMT) ───────────────────────────────────────────────
    if nremt_gaps:
        lines.append("## Assessment Gaps (Not Yet Covered)")
        for gap in nremt_gaps:
            lines.append(f"- {gap}")
        lines.append("")

    # ── CLINICAL RESEARCH BRIEFS ─────────────────────────────────────────────
    if research_briefs:
        lines.append("## Clinical Research Briefs")
        lines.append("_(Auto-generated summaries for each identified entity)_")
        for brief in research_briefs:
            entity = brief.get("entity", "unknown")
            entity_type = brief.get("entityType", "")
            cb = brief.get("clinicalBrief") or {}
            lines.append(f"\n### {entity}" + (f" ({entity_type})" if entity_type else ""))
            if cb.get("summary"):
                lines.append(cb["summary"])
            if cb.get("keyRisks"):
                lines.append("**Key risks:** " + "; ".join(cb["keyRisks"]))
            if cb.get("drugInteractions"):
                lines.append("**Drug interactions:** " + "; ".join(cb["drugInteractions"]))
            if cb.get("contraindications"):
                lines.append("**Contraindications:** " + "; ".join(cb["contraindications"]))
            if cb.get("preHospitalActions"):
                lines.append("**Pre-hospital actions:** " + "; ".join(cb["preHospitalActions"]))
            elif brief.get("findings"):
                lines.append(f"**Findings:** {brief['findings']}")
        lines.append("")

    # ── SCENE TRANSCRIPT ─────────────────────────────────────────────────────
    if transcript.strip():
        lines.append("## Scene Transcript")
        lines.append(
            "> Everything above is extracted from the full transcript. "
            "This excerpt shows the most recent exchanges (last ~3 000 chars) "
            "for nuance and actions/statements not yet reflected in structured fields above."
        )
        lines.append("")
        lines.append(transcript[-3000:])
        lines.append("")

    # ── TASK ─────────────────────────────────────────────────────────────────
    lines.append("---")
    lines.append("## Task")
    lines.append(
        "Read the chart above as a senior ER physician receiving this patient. "
        "Flag EVERY safety concern — drug interactions, allergy conflicts, "
        "dangerous proposed actions, common-sense physical dangers, missing "
        "critical information, and trajectory risks. "
        "Return a JSON array of flags."
    )
    return "\n".join(lines)


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


# Canonical display names for common allergens (dedupes tylenol / Tylenol / acetaminophen)
ALLERGEN_CANONICAL: dict[str, str] = {
    "tylenol": "Tylenol",
    "acetaminophen": "Tylenol",
    "penicillin": "Penicillin",
    "sulfa": "Sulfa",
    "aspirin": "Aspirin",
    "ibuprofen": "Ibuprofen",
    "advil": "Ibuprofen",
    "motrin": "Ibuprofen",
    "nsaids": "NSAIDs",
    "latex": "Latex",
    "morphine": "Morphine",
    "codeine": "Codeine",
}


def canonical_allergen(name: str) -> str:
    key = name.lower().strip()
    return ALLERGEN_CANONICAL.get(key, name.strip().title())


def allergy_alert_concern(allergen: str) -> str:
    display = canonical_allergen(allergen)
    return f"ALLERGY ALERT: {display} — verify before any administration"


def allergy_alert_rationale(allergen: str) -> str:
    display = canonical_allergen(allergen)
    return (
        f"Patient has stated allergy to {display}. "
        "Confirm all medications, foods, and treatments are safe before administration. "
        f"Do NOT give {display} or related agents."
    )


def concern_dedupe_key(concern: str) -> str:
    """Case-insensitive dedupe for allergy alerts; exact match otherwise."""
    if concern.upper().startswith("ALLERGY ALERT:"):
        return concern.lower()
    return concern


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


_SEVERE_LIMB_TRAUMA = (
    # Clinical / formal
    "partially detached", "partial detachment", "partially attached",
    "very broken", "badly broken", "badly fractured", "compound fracture",
    "open fracture", "bone sticking", "bone protruding", "bone sticking out",
    "swinging around", "swinging", "dangling", "hanging loose", "hanging off",
    "almost amputat", "nearly severed", "nearly detached",
    "unstable fracture", "limb is detached", "leg is detached", "arm is detached",
    # Colloquial / natural speech — essential for real scene dialogue
    "fall off", "falling off", "fell off", "about to come off", "coming off",
    "barely attached", "barely hanging", "barely connected", "barely holding",
    "almost off", "nearly off", "almost came off", "nearly came off",
    "hanging by a thread", "hanging on by", "not attached", "isn't attached",
    "hardly attached", "just hanging", "about to go", "going to fall",
    "about to lose", "about to drop off", "can't feel", "no feeling in",
    "won't stay on", "won't stay attached", "might come off",
)

_DANGEROUS_LIMB_MANEUVER = (
    "violently shak", "violent shak", "shaking it", "shake it", "shake the",
    "twist it", "twisting it", "twist the", "wiggle it", "wiggling",
    "move it around", "bend it", "bending it", "straighten it",
    "pull on it", "pulling on", "yank", "yanking",
    "test if it's okay", "test if it is okay", "test if its okay",
    "test by shak", "test by mov", "test by twist", "test by bend",
    "see if it's okay", "see if it moves", "manipulat",
)


def _text_indicates_severe_limb_trauma(text: str) -> bool:
    lower = text.lower()
    if any(p in lower for p in _SEVERE_LIMB_TRAUMA):
        return True
    if "detached" in lower and any(w in lower for w in ("leg", "arm", "limb", "foot", "ankle")):
        return True
    if "broken" in lower and any(w in lower for w in ("leg", "arm", "limb", "bone", "ankle", "femur")):
        return True
    return False


def _text_indicates_dangerous_limb_maneuver(text: str) -> bool:
    lower = text.lower()
    if any(p in lower for p in _DANGEROUS_LIMB_MANEUVER):
        return True
    if "shake" in lower and any(w in lower for w in ("leg", "arm", "limb", " it", "this", "that")):
        return True
    if "test if" in lower and any(w in lower for w in ("okay", "ok", "stable", "broken", "move")):
        return True
    return False


def check_trauma_procedure_risks(
    symptoms: List[str],
    transcript: str = "",
) -> List[SafetyResult]:
    """Flag unstable limb injuries and dangerous assessment/manipulation on scene."""
    flags: List[SafetyResult] = []
    combined = f"{' '.join(symptoms)} {transcript}".strip()
    if not combined:
        return flags

    has_severe = _text_indicates_severe_limb_trauma(combined)
    if not has_severe:
        return flags

    has_maneuver = _text_indicates_dangerous_limb_maneuver(transcript)

    if has_maneuver:
        flags.append(SafetyResult(
            concern="CRITICAL: Dangerous manipulation proposed for unstable limb injury",
            severity="critical",
            rationale=(
                "Patient has described an unstable or severely injured limb (partial detachment, "
                "gross deformity, or limb swinging/dangling). Paramedic dialogue proposes shaking, "
                "twisting, or other aggressive movement. STOP — this risks complete vascular "
                "disruption, hemorrhage, nerve damage, and conversion to amputation. "
                "Immobilize in found position; do not test stability by manipulation."
            ),
            recommendedActions=[
                "Stop all manipulation of the injured limb immediately",
                "Immobilize in the position found with padded splints above and below the injury",
                "Assess distal pulses, motor function, and sensation without moving the limb",
                "Control external bleeding with direct pressure — avoid tourniquet unless life-threatening hemorrhage",
                "Notify receiving ED of suspected unstable fracture or partial amputation",
            ],
        ))
    else:
        flags.append(SafetyResult(
            concern="Unstable limb injury — immobilize and avoid manipulation",
            severity="high",
            rationale=(
                "Scene dialogue indicates an unstable or severely injured limb (partial detachment, "
                "gross deformity, or limb swinging/dangling). Minimize movement; splint in found position "
                "and assess neurovascular status distally without manipulating the injury."
            ),
            recommendedActions=[
                "Splint the limb in the position found — do not attempt to straighten or test range of motion",
                "Check distal pulses, capillary refill, motor function, and sensation before and after splinting",
                "Avoid unnecessary movement during extrication and transport",
            ],
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

    # Unstable limb trauma and dangerous manipulation on scene
    flags.extend(check_trauma_procedure_risks(entities.symptoms, transcript))

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
