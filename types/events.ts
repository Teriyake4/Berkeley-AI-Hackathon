/**
 * SHARED CONTRACT — sync in #engineering before changing.
 * All agents and the dashboard import from this file only.
 */

// ─── Primitives ─────────────────────────────────────────────────────────────

export type Speaker = "paramedic" | "doctor" | "patient" | "bystander" | "unknown";

export type Severity = "low" | "medium" | "high" | "critical";

export interface TimelineEntry {
  id: string;
  timestamp: string; // ISO 8601
  summary: string;
  source?: "extraction" | "safety" | "manual" | "telemetry" | "audio" | "vision";
}

export interface Medication {
  name: string;
  dose?: string;
  frequency?: string;
  /** Provenance: "stated" verbally vs "vision" identified via camera scan. */
  source?: "stated" | "vision";
}

export interface MedicalEntities {
  medications: Medication[];
  conditions: string[];
  allergies: string[];
  vitals: Record<string, string>;
  symptoms: string[];
  demographics?: {
    age?: number;
    sex?: string;
  };
}

export interface SoapNote {
  subjective: string;
  objective: string;
  assessment: string;
  plan: string;
}

export interface Citation {
  title: string;
  url: string;
  snippet?: string;
}

export interface HandoffReport {
  patientSummary: string;
  allergies?: string[];
  timeline: TimelineEntry[];
  currentMedications: Medication[];
  outstandingQuestions: string[];
  recommendedActions: string[];
  generatedAt: string; // ISO 8601
}

// ─── Event payloads ─────────────────────────────────────────────────────────

export interface TranscriptSegmentPayload {
  encounterId: string;
  text: string;
  speaker: Speaker;
  timestamp: string;
}

export interface FactsExtractedPayload {
  encounterId: string;
  entities: MedicalEntities;
  extractedAt: string;
}

export interface TimelineUpdatedPayload {
  encounterId: string;
  events: TimelineEntry[];
}

export interface SafetyFlaggedPayload {
  encounterId: string;
  concern: string;
  severity: Severity;
  rationale: string;
  flaggedAt: string;
  clarifyingQuestion?: string;
  recommendedActions?: string[];
}

export interface NoteUpdatedPayload {
  encounterId: string;
  soap: SoapNote;
  updatedAt: string;
}

export interface ResearchCompletedPayload {
  encounterId: string;
  query: string;
  findings: string;
  citations: Citation[];
  completedAt: string;
}

export interface HandoffRequestedPayload {
  encounterId: string;
  requestedAt: string;
}

export interface HandoffGeneratedPayload {
  encounterId: string;
  report: HandoffReport;
}

export interface AudioEventPayload {
  encounterId: string;
  type: string; // e.g. "silence", "alarm", "distress", "monitor_tone"
  timestamp: string;
  detail?: string;
}

export interface TelemetryUpdatedPayload {
  encounterId: string;
  event: string; // e.g. "scene_arrival", "patient_contact", "en_route", "hospital_arrival"
  timestamp: string;
  label?: string;
}

export interface VisionCapturedPayload {
  encounterId: string;
  identified: string; // e.g. "aspirin 325mg"
  captureType: string; // e.g. "vial_label", "bracelet", "wound"
  timestamp: string;
  rawText?: string;
}

// ─── Event map (channel name → payload type) ────────────────────────────────

export const EVENT_CHANNELS = {
  TRANSCRIPT_SEGMENT: "transcript.segment",
  FACTS_EXTRACTED: "facts.extracted",
  TIMELINE_UPDATED: "timeline.updated",
  SAFETY_FLAGGED: "safety.flagged",
  NOTE_UPDATED: "note.updated",
  RESEARCH_COMPLETED: "research.completed",
  HANDOFF_REQUESTED: "handoff.requested",
  HANDOFF_GENERATED: "handoff.generated",
  AUDIO_EVENT: "audio.event",
  TELEMETRY_UPDATED: "telemetry.updated",
  VISION_CAPTURED: "vision.captured",
} as const;

export type EventChannel = (typeof EVENT_CHANNELS)[keyof typeof EVENT_CHANNELS];

export interface EventPayloadMap {
  [EVENT_CHANNELS.TRANSCRIPT_SEGMENT]: TranscriptSegmentPayload;
  [EVENT_CHANNELS.FACTS_EXTRACTED]: FactsExtractedPayload;
  [EVENT_CHANNELS.TIMELINE_UPDATED]: TimelineUpdatedPayload;
  [EVENT_CHANNELS.SAFETY_FLAGGED]: SafetyFlaggedPayload;
  [EVENT_CHANNELS.NOTE_UPDATED]: NoteUpdatedPayload;
  [EVENT_CHANNELS.RESEARCH_COMPLETED]: ResearchCompletedPayload;
  [EVENT_CHANNELS.HANDOFF_REQUESTED]: HandoffRequestedPayload;
  [EVENT_CHANNELS.HANDOFF_GENERATED]: HandoffGeneratedPayload;
  [EVENT_CHANNELS.AUDIO_EVENT]: AudioEventPayload;
  [EVENT_CHANNELS.TELEMETRY_UPDATED]: TelemetryUpdatedPayload;
  [EVENT_CHANNELS.VISION_CAPTURED]: VisionCapturedPayload;
}

export type EventEnvelope<C extends EventChannel = EventChannel> = {
  channel: C;
  payload: EventPayloadMap[C];
};

export function createEvent<C extends EventChannel>(
  channel: C,
  payload: EventPayloadMap[C]
): EventEnvelope<C> {
  return { channel, payload };
}
