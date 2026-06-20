import type { MedicalEntities, Severity } from "@/lib/events";

export interface SafetyResult {
  concern: string;
  severity: Severity;
  rationale: string;
}

export const SAFETY_SYSTEM = `You are a clinical safety flagging agent. For demo purposes only — not for actual diagnosis or clinical use.

Given medical entities from an ER encounter, identify safety concerns and drug interactions.
Return ONLY a raw JSON array (no markdown):
[{ "concern": string, "severity": "low"|"medium"|"high", "rationale": string }]

Return an empty array [] if no concerns are identified.

Focus on:
- Anticoagulant + acute coronary syndrome (high risk)
- Drug-drug interactions (e.g. warfarin + aspirin)
- High-risk medication combinations
- Classic ACS red flag constellation (age + chest pain + radiation)
- Allergy risks with ordered medications`;

export function buildSafetyPrompt(entities: MedicalEntities): string {
  return [
    "Patient entities:",
    JSON.stringify(entities, null, 2),
    "",
    "Identify safety concerns. Return JSON array.",
  ].join("\n");
}

export function heuristicSafety(entities: MedicalEntities): SafetyResult[] {
  const flags: SafetyResult[] = [];
  const meds = entities.medications.map((m) => m.name.toLowerCase());
  const symptoms = entities.symptoms.map((s) => s.toLowerCase());
  const conditions = entities.conditions.map((c) => c.toLowerCase());
  const allergies = entities.allergies.map((a) => a.toLowerCase());

  const hasWarfarin = meds.some((m) => m.includes("warfarin"));
  const hasAspirin = meds.some((m) => m.includes("aspirin"));
  const hasPenicillinAllergy = allergies.some((a) => a.includes("penicillin"));
  const hasChestPain = symptoms.some((s) => s.includes("chest pain"));
  const hasArmPain = symptoms.some((s) => s.includes("arm"));
  const hasSob = symptoms.some((s) => s.includes("breath"));
  const hasHeartValve = conditions.some((c) => c.includes("heart valve"));
  const age = entities.demographics?.age ?? 0;

  // ── High severity ────────────────────────────────────────────────────────

  if (hasWarfarin && hasChestPain) {
    flags.push({
      concern: "Warfarin + chest pain — anticoagulation complicates ACS management",
      severity: "high",
      rationale:
        "Patient on warfarin presenting with acute chest pain. Thrombotic vs. hemorrhagic risk must be carefully balanced. Check INR before antiplatelet therapy. Mechanical valve may require uninterrupted anticoagulation.",
    });
  }

  if (hasWarfarin && hasAspirin) {
    flags.push({
      concern: "Warfarin + aspirin — dual antithrombotic bleeding risk",
      severity: "high",
      rationale:
        "Concurrent warfarin and aspirin significantly increases GI and intracranial bleeding risk. Ensure benefit clearly outweighs risk before combining.",
    });
  }

  // ── Medium severity ───────────────────────────────────────────────────────

  if (age >= 65 && hasChestPain && (hasArmPain || hasSob)) {
    flags.push({
      concern: "ACS presentation — age ≥65, chest pain, and associated symptoms",
      severity: "medium",
      rationale:
        "Classic ACS feature cluster: age, acute chest pain, arm radiation/dyspnea. Expedite ECG, troponin, and cardiology consult.",
    });
  }

  if (hasHeartValve && hasWarfarin && hasChestPain) {
    flags.push({
      concern: "Mechanical valve patient — warfarin interruption risk",
      severity: "medium",
      rationale:
        "Mechanical heart valve requires continuous anticoagulation. Any interruption carries thromboembolic stroke risk. Coordinate hematology/cardiology before any warfarin reversal.",
    });
  }

  // ── Low severity ──────────────────────────────────────────────────────────

  if (hasPenicillinAllergy) {
    flags.push({
      concern: "Penicillin allergy documented — verify ordered antibiotics",
      severity: "low",
      rationale:
        "Patient has documented penicillin allergy. Confirm no penicillin/cephalosporin (cross-reactivity ~2%) ordered. Use alternative antibiotics if needed.",
    });
  }

  return flags;
}
