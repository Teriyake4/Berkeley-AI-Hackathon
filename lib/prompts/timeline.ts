import type { MedicalEntities, TimelineEntry } from "@/lib/events";

export const TIMELINE_SYSTEM = `You are a clinical timeline agent. Produce a concise, chronological list of key clinical events from the encounter.

Return ONLY a raw JSON array (no markdown):
[{ "id": string, "timestamp": string (ISO 8601), "summary": string, "source": "extraction" }]

Rules:
- Each entry is one sentence, clinical and factual
- Max 10 entries total (merge or drop minor duplicates)
- Use realistic timestamps spread across the encounter (start ~08:12 today)
- source must be "extraction"`;

export function buildTimelinePrompt(
  entities: MedicalEntities,
  transcript: string,
  existing: TimelineEntry[]
): string {
  const today = new Date().toISOString().slice(0, 10);
  return [
    `Today: ${today}`,
    "",
    "Existing timeline:",
    JSON.stringify(existing, null, 2),
    "",
    "Entities:",
    JSON.stringify(entities, null, 2),
    "",
    "Transcript:",
    transcript.slice(-2000),
    "",
    "Return updated timeline JSON array (max 10 entries).",
  ].join("\n");
}

export function heuristicTimeline(
  entities: MedicalEntities,
  existing: TimelineEntry[]
): TimelineEntry[] {
  const entries = existing.filter((e) => e.source !== "extraction");
  const safetyEntries = existing.filter((e) => e.source === "safety");

  const baseMs = Date.now() - 20 * 60 * 1000; // ~20 min ago
  let offset = 0;

  const add = (summary: string) => {
    if (entries.some((e) => e.summary.toLowerCase().includes(summary.toLowerCase().slice(0, 30))))
      return;
    if (safetyEntries.some((e) =>
      e.summary.toLowerCase().includes(summary.toLowerCase().slice(0, 30))
    ))
      return;
    entries.push({
      id: `tl-${crypto.randomUUID().slice(0, 8)}`,
      timestamp: new Date(baseMs + offset * 90_000).toISOString(),
      summary,
      source: "extraction",
    });
    offset++;
  };

  const age = entities.demographics?.age;
  const sex = entities.demographics?.sex;

  if (age || sex) {
    const demo = [age ? `${age}yo` : null, sex ?? null].filter(Boolean).join(" ");
    add(`Patient demographics: ${demo}`);
  }

  if (entities.symptoms.some((s) => s.includes("chest pain")))
    add("Patient reports acute chest pain");
  if (entities.symptoms.some((s) => s.includes("shortness of breath")))
    add("Mild shortness of breath reported");
  if (entities.symptoms.some((s) => s.includes("left arm")))
    add("Left arm radiation noted");
  if (entities.symptoms.some((s) => s.includes("nausea")))
    add("Nausea reported");

  if (entities.conditions.some((c) => c.includes("hypertension")))
    add("Hypertension history identified");
  if (entities.conditions.some((c) => c.includes("heart valve")))
    add("Mechanical heart valve replacement history noted");
  if (entities.conditions.some((c) => c.includes("atrial fibrillation")))
    add("Atrial fibrillation history identified");

  if (entities.medications.some((m) => m.name.toLowerCase() === "lisinopril"))
    add("Lisinopril (ACE inhibitor) documented");
  if (entities.medications.some((m) => m.name.toLowerCase() === "warfarin"))
    add("Warfarin anticoagulation documented");
  if (entities.medications.some((m) => m.name.toLowerCase() === "aspirin"))
    add("Aspirin ordered/documented");

  if (entities.allergies.some((a) => a.toLowerCase().includes("penicillin")))
    add("Penicillin allergy documented");
  if (entities.allergies.length > 0 && !entities.allergies.some((a) => a.toLowerCase().includes("penicillin")))
    add(`Allergy documented: ${entities.allergies[0]}`);

  // Merge safety entries back in at the correct position
  return [...entries, ...safetyEntries]
    .sort((a, b) => a.timestamp.localeCompare(b.timestamp))
    .slice(-12);
}
