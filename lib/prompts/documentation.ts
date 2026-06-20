import type { MedicalEntities, SoapNote, TimelineEntry } from "@/lib/events";

export const DOCUMENTATION_SYSTEM = `You are a clinical documentation agent generating a SOAP note. For demo purposes only — not for clinical use.

Return ONLY a raw JSON object (no markdown):
{ "subjective": string, "objective": string, "assessment": string, "plan": string }

Guidelines:
- Subjective: Chief complaint, HPI including onset/duration/location/quality/radiation/associated symptoms, PMH, medications, allergies
- Objective: Vitals and exam findings documented (if none yet, note "pending")
- Assessment: Differential with most likely at top
- Plan: Diagnostic workup and initial treatment steps, respecting anticoagulation status`;

export function buildDocumentationPrompt(
  entities: MedicalEntities,
  timeline: TimelineEntry[],
  transcript: string
): string {
  return [
    "Patient entities:",
    JSON.stringify(entities, null, 2),
    "",
    "Timeline:",
    JSON.stringify(timeline, null, 2),
    "",
    "Transcript:",
    transcript.slice(-2000),
    "",
    "Generate SOAP note JSON.",
  ].join("\n");
}

export function heuristicSoap(
  entities: MedicalEntities,
  _timeline: TimelineEntry[]
): SoapNote {
  const age = entities.demographics?.age;
  const sex = entities.demographics?.sex;
  const demo = [age ? `${age}-year-old` : null, sex ?? null].filter(Boolean).join(" ");

  const meds = entities.medications.map((m) => m.name).join(", ") || "none documented";
  const symptoms = entities.symptoms.length
    ? entities.symptoms.join(", ")
    : "acute symptoms";
  const conditions = entities.conditions.length
    ? entities.conditions.join(", ")
    : "none documented";
  const allergies = entities.allergies.length
    ? entities.allergies.join(", ")
    : "NKDA";

  const hasWarfarin = entities.medications.some((m) =>
    m.name.toLowerCase().includes("warfarin")
  );
  const hasChestPain = entities.symptoms.some((s) => s.includes("chest pain"));
  const hasArmPain = entities.symptoms.some((s) => s.includes("arm"));
  const hasSob = entities.symptoms.some((s) => s.includes("breath"));

  const acsFeatures = [
    hasChestPain ? "chest pain" : null,
    hasArmPain ? "arm radiation" : null,
    hasSob ? "dyspnea" : null,
  ]
    .filter(Boolean)
    .join(", ");

  return {
    subjective: `${demo || "Patient"} presenting with ${symptoms}. PMH: ${conditions}. Current medications: ${meds}. Allergies: ${allergies}.`,
    objective: "Vitals pending. Physical exam not yet documented. ECG and troponin ordered.",
    assessment:
      hasChestPain && hasWarfarin
        ? `Acute ${acsFeatures || "chest pain"} in anticoagulated patient with cardiac history. Primary concern: ACS. Mechanical valve complicates management.`
        : hasChestPain
        ? `Acute ${acsFeatures || "chest pain"}. Rule out ACS, aortic dissection, PE.`
        : "Acute presentation under evaluation.",
    plan: hasWarfarin
      ? "1. Stat ECG and serial troponins\n2. Check INR before antiplatelet therapy\n3. Cardiology consult stat\n4. Assess bleed vs. thrombosis risk before aspirin\n5. IV access, continuous monitoring"
      : "1. Stat ECG and serial troponins\n2. Aspirin 325mg (absent contraindications)\n3. Cardiology consult\n4. IV access, continuous monitoring",
  };
}
