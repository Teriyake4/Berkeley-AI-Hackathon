import type { HandoffReport, MedicalEntities, SoapNote, TimelineEntry } from "@/lib/events";

export const HANDOFF_SYSTEM = `You are generating a formal shift handoff report for an ER encounter. For demo purposes only — not for clinical use.

Return ONLY a raw JSON object (no markdown):
{
  "patientSummary": string,
  "timeline": [{ "id": string, "timestamp": string, "summary": string, "source": "extraction" }],
  "currentMedications": [{ "name": string, "dose"?: string }],
  "outstandingQuestions": string[],
  "recommendedActions": string[],
  "generatedAt": string
}

Requirements:
- patientSummary: 2-3 sentence clinical summary including demographics, chief complaint, relevant PMH, key meds
- timeline: chronological key events (max 8)
- outstandingQuestions: specific unanswered clinical questions (e.g. "Current INR?")
- recommendedActions: ordered, specific next steps for incoming clinician
- generatedAt: current ISO timestamp`;

export function buildHandoffPrompt(
  entities: MedicalEntities,
  timeline: TimelineEntry[],
  transcript: string,
  soap: Partial<SoapNote> | null
): string {
  return [
    "Entities:",
    JSON.stringify(entities, null, 2),
    "",
    "Timeline:",
    JSON.stringify(timeline, null, 2),
    "",
    "SOAP note:",
    JSON.stringify(soap, null, 2),
    "",
    "Full transcript:",
    transcript.slice(-3000),
    "",
    "Generate the structured handoff report JSON.",
  ].join("\n");
}

export function heuristicHandoff(
  entities: MedicalEntities,
  timeline: TimelineEntry[]
): HandoffReport {
  const age = entities.demographics?.age ?? "?";
  const sex = entities.demographics?.sex ?? "patient";
  const conditions = entities.conditions.join(", ") || "none documented";
  const hasWarfarin = entities.medications.some((m) =>
    m.name.toLowerCase().includes("warfarin")
  );
  const hasPenicillinAllergy = entities.allergies.some((a) =>
    a.toLowerCase().includes("penicillin")
  );
  const symptoms = entities.symptoms.join(", ") || "acute symptoms";

  const outstandingQuestions = [
    hasWarfarin ? "Current INR value?" : null,
    "Pain severity 1–10?",
    "Prior cardiac workup / stress testing?",
    hasWarfarin ? "Last warfarin dose and time?" : null,
    "Family history of cardiac disease?",
  ].filter(Boolean) as string[];

  const recommendedActions = [
    "Stat ECG — review for ST changes",
    "Serial troponins (0h, 3h, 6h)",
    "Cardiology consult stat",
    hasWarfarin
      ? "Check INR before initiating antiplatelet therapy — weigh bleed vs thrombosis risk"
      : "Aspirin 325mg if no contraindications",
    "IV access and continuous cardiac monitoring",
    hasPenicillinAllergy ? "Confirm no penicillin/cephalosporin ordered (allergy documented)" : null,
    "Portable CXR",
  ].filter(Boolean) as string[];

  return {
    patientSummary: `${age}-year-old ${sex} presenting with ${symptoms}. PMH: ${conditions}. Medications: ${entities.medications.map((m) => m.name).join(", ") || "none"}. Allergies: ${entities.allergies.join(", ") || "NKDA"}.`,
    timeline: timeline.slice(-8),
    currentMedications: entities.medications,
    outstandingQuestions,
    recommendedActions,
    generatedAt: new Date().toISOString(),
  };
}
