import type {
  HandoffReport,
  MedicalEntities,
  SafetyFlaggedPayload,
  SoapNote,
  Speaker,
  TimelineEntry,
} from "@/types/events";

export type TranscriptSpeaker = Speaker | "console";

export interface TranscriptLine {
  speaker: TranscriptSpeaker;
  text: string;
  timestamp: string;
}

export interface VisionItem {
  identified: string;
  captureType: string;
  timestamp: string;
}

export interface SessionSummary {
  encounterId: string;
  startedAt: string;
  mode: "demo" | "live" | "unknown";
  status: "active" | "completed" | "unknown";
  endedAt?: string;
}

export interface EncounterSnapshot {
  encounterId: string;
  startedAt?: string;
  meta?: {
    startedAt: string;
    mode: string;
    status: string;
    endedAt?: string;
  };
  transcript: TranscriptLine[];
  facts: MedicalEntities | null;
  timeline: TimelineEntry[];
  safetyFlags: SafetyFlaggedPayload[];
  soap: SoapNote | null;
  research: Array<{
    query: string;
    findings: string;
    citations: Array<{ title: string; url: string; snippet?: string }>;
    completedAt?: string;
  }>;
  handoff: HandoffReport | null;
  visionItems: VisionItem[];
}

export const ACTIVE_ENCOUNTER_KEY = "nos-active-encounter-id";
