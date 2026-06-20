import type { MedicalEntities } from "@/lib/events";

export const EXTRACTION_SYSTEM = `You are a clinical entity extraction agent. Extract structured medical facts from doctor-patient conversation transcripts.

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
- Include every medication, including ones taken long-term (e.g. lisinopril, warfarin)
- Include allergies (e.g. "penicillin allergy")
- Symptoms: include chief complaint and associated symptoms
- Do NOT invent facts not stated in the transcript
- Merge carefully with existing entities — never drop previously extracted data`;

export function buildExtractionPrompt(
  transcript: string,
  existing: MedicalEntities | null
): string {
  return [
    "Existing entities (preserve all, only add new):",
    JSON.stringify(existing ?? {}, null, 2),
    "",
    "New transcript to process:",
    transcript,
    "",
    "Return the fully merged entities JSON.",
  ].join("\n");
}

export function heuristicExtract(
  transcript: string,
  existing: MedicalEntities | null
): MedicalEntities {
  const lower = transcript.toLowerCase();
  const entities: MedicalEntities = existing
    ? JSON.parse(JSON.stringify(existing))
    : { medications: [], conditions: [], allergies: [], vitals: {}, symptoms: [] };

  const addMed = (name: string, dose?: string) => {
    if (!entities.medications.some((m) => m.name.toLowerCase() === name.toLowerCase())) {
      entities.medications.push(dose ? { name, dose } : { name });
    }
  };
  const addCondition = (c: string) => {
    if (!entities.conditions.some((x) => x.toLowerCase() === c.toLowerCase()))
      entities.conditions.push(c);
  };
  const addSymptom = (s: string) => {
    if (!entities.symptoms.some((x) => x.toLowerCase() === s.toLowerCase()))
      entities.symptoms.push(s);
  };
  const addAllergy = (a: string) => {
    if (!entities.allergies.some((x) => x.toLowerCase() === a.toLowerCase()))
      entities.allergies.push(a);
  };

  // Medications
  if (lower.includes("warfarin")) addMed("warfarin");
  if (lower.includes("lisinopril")) addMed("lisinopril");
  if (lower.includes("aspirin")) addMed("aspirin");
  if (lower.includes("metoprolol")) addMed("metoprolol");
  if (lower.includes("atorvastatin") || lower.includes("statin")) addMed("atorvastatin");
  if (lower.includes("heparin")) addMed("heparin");
  if (lower.includes("nitroglycerin") || lower.includes("nitro")) addMed("nitroglycerin");

  // Allergies
  if (lower.includes("penicillin") && (lower.includes("allerg") || lower.includes("reaction")))
    addAllergy("penicillin");
  if (lower.includes("sulfa") && lower.includes("allerg")) addAllergy("sulfa");
  if (lower.includes("nsaid") && lower.includes("allerg")) addAllergy("NSAIDs");

  // Conditions
  if (lower.includes("hypertension") || lower.includes("high blood pressure"))
    addCondition("hypertension");
  if (lower.includes("heart valve")) addCondition("heart valve replacement");
  if (lower.includes("atrial fibrillation") || lower.includes("afib")) addCondition("atrial fibrillation");
  if (lower.includes("diabetes")) addCondition("diabetes mellitus");
  if (lower.includes("heart failure")) addCondition("heart failure");
  if (lower.includes("coronary artery disease") || lower.includes("cad")) addCondition("coronary artery disease");

  // Symptoms
  if (lower.includes("chest pain") || lower.includes("chest pressure")) addSymptom("chest pain");
  if (lower.includes("shortness of breath") || lower.includes("short of breath") || lower.includes("dyspnea"))
    addSymptom("shortness of breath");
  if (lower.includes("left arm")) addSymptom("left arm pain");
  if (lower.includes("jaw pain") || lower.includes("jaw")) addSymptom("jaw pain");
  if (lower.includes("nausea")) addSymptom("nausea");
  if (lower.includes("diaphoresis") || lower.includes("sweating")) addSymptom("diaphoresis");
  if (lower.includes("dizziness") || lower.includes("dizzy")) addSymptom("dizziness");
  if (lower.includes("palpitation")) addSymptom("palpitations");

  // Demographics — age
  const ageMatch = lower.match(/\b(5[5-9]|6[0-9]|7[0-9]|8[0-9])\b/);
  if (ageMatch) {
    entities.demographics = {
      ...entities.demographics,
      age: parseInt(ageMatch[1], 10),
    };
  }
  // Sex
  if (lower.match(/\b(male|man|he|his|gentleman)\b/))
    entities.demographics = { ...entities.demographics, sex: "male" };
  else if (lower.match(/\b(female|woman|she|her|lady)\b/))
    entities.demographics = { ...entities.demographics, sex: "female" };

  return entities;
}
