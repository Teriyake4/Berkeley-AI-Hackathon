"use client";

import { useCallback, useEffect, useMemo, useReducer, useRef } from "react";
import type {
  Citation,
  EventEnvelope,
  HandoffReport,
  MedicalEntities,
  SafetyFlaggedPayload,
  SoapNote,
  Speaker,
  TimelineEntry,
  TranscriptSegmentPayload,
} from "@/types/events";
import { EVENT_CHANNELS } from "@/types/events";
import { ENCOUNTER_ID } from "@/types/constants";

/** Console = synthetic line injected when the vision agent identifies something. */
export type TranscriptSpeaker = Speaker | "console";

export interface TranscriptLine {
  speaker: TranscriptSpeaker;
  text: string;
  timestamp: string;
}

export type EncounterPhase = "idle" | "scene" | "en_route" | "hospital";

export interface VisionItem {
  identified: string;
  captureType: string;
  timestamp: string;
}

export interface EncounterState {
  encounterId: string;
  connected: boolean;
  transcript: TranscriptLine[];
  entities: MedicalEntities | null;
  timeline: TimelineEntry[];
  safetyFlags: SafetyFlaggedPayload[];
  soap: SoapNote | null;
  research: Array<{
    query: string;
    findings: string;
    citations: Citation[];
    completedAt: string;
  }>;
  handoff: HandoffReport | null;
  /** Items identified by the camera/vision agent (stated vs camera provenance). */
  visionItems: VisionItem[];
  /** Encounter location phase, derived from telemetry events. */
  phase: EncounterPhase;
  mode: "idle" | "demo" | "live";
  loading: boolean;
  /** Which agents fired in the last 3s (for activity indicator) */
  activeAgents: Set<string>;
}

const initialEntities: MedicalEntities = {
  medications: [],
  conditions: [],
  allergies: [],
  vitals: {},
  symptoms: [],
};

export const initialEncounterState: EncounterState = {
  encounterId: ENCOUNTER_ID,
  connected: false,
  transcript: [],
  entities: null,
  timeline: [],
  safetyFlags: [],
  soap: null,
  research: [],
  handoff: null,
  visionItems: [],
  phase: "idle",
  mode: "idle",
  loading: false,
  activeAgents: new Set(),
};

type Action =
  | { type: "CONNECTED" }
  | { type: "DISCONNECTED" }
  | { type: "SET_MODE"; mode: EncounterState["mode"] }
  | { type: "SET_LOADING"; loading: boolean }
  | { type: "RESET" }
  | { type: "AGENT_ACTIVE"; agent: string }
  | { type: "AGENT_IDLE"; agent: string }
  | { type: "EVENT"; envelope: EventEnvelope };

function reducer(state: EncounterState, action: Action): EncounterState {
  switch (action.type) {
    case "CONNECTED":
      return { ...state, connected: true };
    case "DISCONNECTED":
      return { ...state, connected: false };
    case "SET_MODE":
      return { ...state, mode: action.mode };
    case "SET_LOADING":
      return { ...state, loading: action.loading };
    case "RESET":
      return {
        ...initialEncounterState,
        connected: state.connected,
        encounterId: state.encounterId,
        activeAgents: new Set(),
      };
    case "AGENT_ACTIVE": {
      const next = new Set(state.activeAgents);
      next.add(action.agent);
      return { ...state, activeAgents: next };
    }
    case "AGENT_IDLE": {
      const next = new Set(state.activeAgents);
      next.delete(action.agent);
      return { ...state, activeAgents: next };
    }
    case "EVENT":
      return applyEvent(state, action.envelope);
    default:
      return state;
  }
}

function agentForChannel(channel: string): string | null {
  const map: Record<string, string> = {
    [EVENT_CHANNELS.FACTS_EXTRACTED]: "extraction",
    [EVENT_CHANNELS.TIMELINE_UPDATED]: "timeline",
    [EVENT_CHANNELS.SAFETY_FLAGGED]: "safety",
    [EVENT_CHANNELS.NOTE_UPDATED]: "documentation",
    [EVENT_CHANNELS.RESEARCH_COMPLETED]: "research",
    [EVENT_CHANNELS.HANDOFF_GENERATED]: "handoff",
    [EVENT_CHANNELS.VISION_CAPTURED]: "vision",
  };
  return map[channel] ?? null;
}

const TELEMETRY_PHASE: Record<string, EncounterPhase> = {
  scene_arrival: "scene",
  patient_contact: "scene",
  en_route: "en_route",
  hospital_arrival: "hospital",
};

function humanize(event: string): string {
  return event.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function applyEvent(state: EncounterState, envelope: EventEnvelope): EncounterState {
  // Mark the relevant agent as briefly active
  const agent = agentForChannel(envelope.channel);
  const activeAgents = new Set(state.activeAgents);
  if (agent) activeAgents.add(agent);

  switch (envelope.channel) {
    case EVENT_CHANNELS.TRANSCRIPT_SEGMENT: {
      const p = envelope.payload as TranscriptSegmentPayload;
      return {
        ...state,
        activeAgents,
        transcript: [
          ...state.transcript,
          { speaker: p.speaker, text: p.text, timestamp: p.timestamp },
        ],
      };
    }
    case EVENT_CHANNELS.FACTS_EXTRACTED: {
      const p = envelope.payload as import("@/types/events").FactsExtractedPayload;
      return { ...state, activeAgents, entities: p.entities };
    }
    case EVENT_CHANNELS.TIMELINE_UPDATED: {
      const p = envelope.payload as import("@/types/events").TimelineUpdatedPayload;
      return { ...state, activeAgents, timeline: p.events };
    }
    case EVENT_CHANNELS.SAFETY_FLAGGED: {
      const p = envelope.payload as import("@/types/events").SafetyFlaggedPayload;
      const alreadyExists = state.safetyFlags.some(
        (f) => f.concern.toLowerCase() === p.concern.toLowerCase()
      );
      if (alreadyExists) return state;
      return {
        ...state,
        activeAgents,
        safetyFlags: [...state.safetyFlags, p],
        timeline: [
          ...state.timeline,
          {
            id: `safety-${p.flaggedAt}`,
            timestamp: p.flaggedAt,
            summary: `⚠ ${p.concern}`,
            source: "safety" as const,
          },
        ],
      };
    }
    case EVENT_CHANNELS.NOTE_UPDATED: {
      const p = envelope.payload as import("@/types/events").NoteUpdatedPayload;
      return { ...state, activeAgents, soap: p.soap };
    }
    case EVENT_CHANNELS.RESEARCH_COMPLETED: {
      const p = envelope.payload as import("@/types/events").ResearchCompletedPayload;
      // Deduplicate by query
      const alreadyExists = state.research.some((r) => r.query === p.query);
      if (alreadyExists) return state;
      return {
        ...state,
        activeAgents,
        research: [
          ...state.research,
          {
            query: p.query,
            findings: p.findings,
            citations: p.citations,
            completedAt: p.completedAt,
          },
        ],
      };
    }
    case EVENT_CHANNELS.HANDOFF_GENERATED: {
      const p = envelope.payload as import("@/types/events").HandoffGeneratedPayload;
      return { ...state, activeAgents, handoff: p.report, loading: false };
    }
    case EVENT_CHANNELS.TELEMETRY_UPDATED: {
      const p = envelope.payload as import("@/types/events").TelemetryUpdatedPayload;
      const phase = TELEMETRY_PHASE[p.event] ?? state.phase;
      const summary = p.label
        ? `${humanize(p.event)} — ${p.label}`
        : humanize(p.event);
      return {
        ...state,
        phase,
        timeline: [
          ...state.timeline,
          {
            id: `telemetry-${p.event}-${p.timestamp}`,
            timestamp: p.timestamp,
            summary,
            source: "telemetry" as const,
          },
        ],
      };
    }
    case EVENT_CHANNELS.AUDIO_EVENT: {
      const p = envelope.payload as import("@/types/events").AudioEventPayload;
      const summary = p.detail ? `${humanize(p.type)} — ${p.detail}` : humanize(p.type);
      return {
        ...state,
        timeline: [
          ...state.timeline,
          {
            id: `audio-${p.type}-${p.timestamp}`,
            timestamp: p.timestamp,
            summary,
            source: "audio" as const,
          },
        ],
      };
    }
    case EVENT_CHANNELS.VISION_CAPTURED: {
      const p = envelope.payload as import("@/types/events").VisionCapturedPayload;
      // Dedupe identical captures
      if (state.visionItems.some((v) => v.identified === p.identified)) {
        return { ...state, activeAgents };
      }
      return {
        ...state,
        activeAgents,
        visionItems: [
          ...state.visionItems,
          { identified: p.identified, captureType: p.captureType, timestamp: p.timestamp },
        ],
        // Inject an ambient "Console" line into the same scrolling transcript
        transcript: [
          ...state.transcript,
          {
            speaker: "console" as const,
            text: `Observing — ${p.identified} identified.`,
            timestamp: p.timestamp,
          },
        ],
        timeline: [
          ...state.timeline,
          {
            id: `vision-${p.timestamp}`,
            timestamp: p.timestamp,
            summary: `Vision: ${p.identified} identified`,
            source: "vision" as const,
          },
        ],
      };
    }
    default:
      return state;
  }
}

export function useEncounterEvents() {
  const [state, dispatch] = useReducer(reducer, initialEncounterState);
  const sourceRef = useRef<EventSource | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const agentTimersRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  const connect = useCallback(() => {
    if (sourceRef.current) {
      sourceRef.current.close();
      sourceRef.current = null;
    }

    const source = new EventSource("/api/events");
    sourceRef.current = source;

    source.onopen = () => {
      dispatch({ type: "CONNECTED" });
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
    };

    source.onerror = () => {
      dispatch({ type: "DISCONNECTED" });
      source.close();
      sourceRef.current = null;
      // Auto-reconnect after 3s
      reconnectTimerRef.current = setTimeout(() => connect(), 3000);
    };

    source.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data as string) as {
          channel: string;
          payload?: unknown;
        };
        if (parsed.channel === "connected") return;

        const envelope = parsed as EventEnvelope;
        dispatch({ type: "EVENT", envelope });

        // Clear agent-active badge after 2.5s
        const agent = agentForChannel(envelope.channel);
        if (agent) {
          const timers = agentTimersRef.current;
          if (timers.has(agent)) clearTimeout(timers.get(agent)!);
          timers.set(
            agent,
            setTimeout(() => dispatch({ type: "AGENT_IDLE", agent }), 2500)
          );
        }
      } catch {
        /* ignore parse errors */
      }
    };
  }, []);

  useEffect(() => {
    connect();
    return () => {
      sourceRef.current?.close();
      sourceRef.current = null;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      agentTimersRef.current.forEach((t) => clearTimeout(t));
    };
  }, [connect]);

  const startEncounter = useCallback(
    async (mode: "demo" | "live") => {
      dispatch({ type: "RESET" });
      dispatch({ type: "SET_MODE", mode });
      dispatch({ type: "SET_LOADING", loading: mode === "demo" });

      await fetch("/api/encounter", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode, encounterId: ENCOUNTER_ID }),
      });

      if (mode === "demo") {
        setTimeout(() => dispatch({ type: "SET_LOADING", loading: false }), 30000);
      }
    },
    []
  );

  const requestHandoff = useCallback(async () => {
    dispatch({ type: "SET_LOADING", loading: true });
    await fetch("/api/handoff", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ encounterId: ENCOUNTER_ID }),
    });
  }, []);

  const pushTranscript = useCallback(async (text: string, speaker: Speaker) => {
    await fetch("/api/transcript", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, speaker, encounterId: ENCOUNTER_ID }),
    });
  }, []);

  const missingInfo = useMemo(
    () => getMissingInfo(state.entities ?? initialEntities, state.safetyFlags),
    [state.entities, state.safetyFlags]
  );

  const suggestedFollowUps = useMemo(
    () => getSuggestedFollowUps(state.entities ?? initialEntities, state.safetyFlags),
    [state.entities, state.safetyFlags]
  );

  return {
    state,
    missingInfo,
    suggestedFollowUps,
    startEncounter,
    requestHandoff,
    pushTranscript,
  };
}

function getMissingInfo(
  entities: MedicalEntities,
  _safetyFlags: SafetyFlaggedPayload[]
): string[] {
  const missing: string[] = [];
  if (!entities.demographics?.age) missing.push("Patient age");
  if (!entities.demographics?.sex) missing.push("Patient sex");
  if (Object.keys(entities.vitals).length === 0) missing.push("Vital signs");
  if (!entities.symptoms.some((s) => s.toLowerCase().includes("severity")))
    missing.push("Pain severity (1–10)");
  if (entities.medications.some((m) => m.name.toLowerCase().includes("warfarin")))
    missing.push("Current INR");
  if (
    entities.symptoms.some((s) => s.includes("chest pain")) &&
    !entities.vitals["bp"]
  )
    missing.push("Blood pressure");
  return missing;
}

function getSuggestedFollowUps(
  entities: MedicalEntities,
  safetyFlags: SafetyFlaggedPayload[]
): string[] {
  const suggestions: string[] = [];

  const hasWarfarin = entities.medications.some((m) =>
    m.name.toLowerCase().includes("warfarin")
  );
  const hasChestPain = entities.symptoms.some((s) => s.includes("chest pain"));
  const hasHeartValve = entities.conditions.some((c) => c.includes("heart valve"));
  const highSeverityFlags = safetyFlags.filter((f) => f.severity === "high");

  const hasAnyAllergy = entities.allergies.length > 0;

  if (hasAnyAllergy) {
    suggestions.push("Confirm no ordered medications or foods contain known allergens");
    for (const allergy of entities.allergies.slice(0, 2)) {
      suggestions.push(`What reaction does the patient have to ${allergy}?`);
    }
  }
  if (hasWarfarin) {
    suggestions.push("What is your most recent INR reading?");
    suggestions.push("When did you last take your warfarin?");
  }
  if (hasChestPain) {
    suggestions.push("On a scale of 1–10, how would you rate the chest pain?");
    suggestions.push("Did the chest pain start suddenly or gradually?");
  }
  if (hasHeartValve) {
    suggestions.push("Do you have records of your last cardiology visit?");
  }
  if (highSeverityFlags.length > 0) {
    suggestions.push("Has a cardiologist been contacted?");
  }
  if (entities.symptoms.some((s) => s.includes("arm"))) {
    suggestions.push("Is the arm pain constant or intermittent?");
  }

  return suggestions.slice(0, 4);
}
