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
import type { EncounterSnapshot, TranscriptLine, VisionItem } from "@/types/session";
import { ACTIVE_ENCOUNTER_KEY } from "@/types/session";
export type { TranscriptLine, VisionItem } from "@/types/session";

export type EncounterPhase = "idle" | "scene" | "en_route" | "hospital";

export interface UseEncounterEventsOptions {
  /** When set, loads snapshot only — no SSE or new recordings. */
  replayEncounterId?: string;
}

export interface EncounterState {
  encounterId: string;
  startedAt: string | null;
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
  encounterId: "",
  startedAt: null,
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
  | { type: "SET_ENCOUNTER"; encounterId: string; startedAt: string; mode: EncounterState["mode"] }
  | { type: "HYDRATE"; snapshot: EncounterSnapshot }
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
    case "SET_ENCOUNTER":
      return {
        ...initialEncounterState,
        connected: state.connected,
        encounterId: action.encounterId,
        startedAt: action.startedAt,
        mode: action.mode,
        activeAgents: new Set(),
      };
    case "HYDRATE": {
      const hydrated = snapshotToState(action.snapshot);
      return {
        ...state,
        ...hydrated,
        connected: state.connected,
      };
    }
    case "RESET":
      return {
        ...initialEncounterState,
        connected: state.connected,
        encounterId: state.encounterId,
        startedAt: state.startedAt,
        mode: state.mode,
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

function phaseFromTimeline(timeline: TimelineEntry[]): EncounterPhase {
  let phase: EncounterPhase = "idle";
  for (const entry of timeline) {
    if (entry.source !== "telemetry") continue;
    const id = entry.id.toLowerCase();
    if (id.includes("hospital")) phase = "hospital";
    else if (id.includes("en_route")) phase = "en_route";
    else if (id.includes("scene")) phase = "scene";
  }
  return phase;
}

function snapshotToState(snapshot: EncounterSnapshot): Partial<EncounterState> {
  const mode =
    snapshot.meta?.mode === "demo" || snapshot.meta?.mode === "live"
      ? snapshot.meta.mode
      : "idle";
  const timeline = snapshot.timeline ?? [];
  return {
    encounterId: snapshot.encounterId,
    startedAt: snapshot.startedAt ?? snapshot.meta?.startedAt ?? null,
    mode,
    transcript: snapshot.transcript ?? [],
    entities: snapshot.facts ?? null,
    timeline,
    safetyFlags: snapshot.safetyFlags ?? [],
    soap: snapshot.soap ?? null,
    research: (snapshot.research ?? []).map((r) => ({
      query: r.query,
      findings: r.findings,
      citations: r.citations ?? [],
      completedAt: r.completedAt ?? "",
    })),
    handoff: snapshot.handoff ?? null,
    visionItems: snapshot.visionItems ?? [],
    phase: phaseFromTimeline(timeline),
    loading: false,
    activeAgents: new Set(),
  };
}

function payloadEncounterId(payload: unknown): string | undefined {
  if (payload && typeof payload === "object" && "encounterId" in payload) {
    const id = (payload as { encounterId?: string }).encounterId;
    return typeof id === "string" ? id : undefined;
  }
  return undefined;
}

function applyEvent(state: EncounterState, envelope: EventEnvelope): EncounterState {
  const eventEncounterId = payloadEncounterId(envelope.payload);
  if (
    state.encounterId &&
    eventEncounterId &&
    eventEncounterId !== state.encounterId
  ) {
    return state;
  }

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
      const incomingIds = new Set(p.events.map((e) => e.id));
      const preserved = state.timeline.filter((e) => !incomingIds.has(e.id));
      const merged = [...p.events, ...preserved].sort((a, b) =>
        a.timestamp.localeCompare(b.timestamp)
      );
      return { ...state, activeAgents, timeline: merged };
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

async function fetchSnapshot(encounterId: string): Promise<EncounterSnapshot | null> {
  try {
    const res = await fetch(`/api/sessions/${encounterId}`);
    if (!res.ok) return null;
    return (await res.json()) as EncounterSnapshot;
  } catch {
    return null;
  }
}

export function useEncounterEvents(options: UseEncounterEventsOptions = {}) {
  const { replayEncounterId } = options;
  const readOnly = Boolean(replayEncounterId);
  const [state, dispatch] = useReducer(reducer, initialEncounterState);
  const sourceRef = useRef<EventSource | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const agentTimersRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());
  const encounterIdRef = useRef(state.encounterId);

  useEffect(() => {
    encounterIdRef.current = state.encounterId;
  }, [state.encounterId]);

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
      reconnectTimerRef.current = setTimeout(() => connect(), 3000);
    };

    source.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data as string) as {
          channel: string;
          payload?: unknown;
        };
        if (parsed.channel === "connected") return;

        const eventEncounterId = payloadEncounterId(parsed.payload);
        const activeId = encounterIdRef.current;
        if (activeId && eventEncounterId && eventEncounterId !== activeId) {
          return;
        }

        const envelope = parsed as EventEnvelope;
        dispatch({ type: "EVENT", envelope });

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
    if (readOnly) return;
    connect();
    return () => {
      sourceRef.current?.close();
      sourceRef.current = null;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      agentTimersRef.current.forEach((t) => clearTimeout(t));
    };
  }, [connect, readOnly]);

  useEffect(() => {
    if (readOnly && replayEncounterId) {
      fetchSnapshot(replayEncounterId).then((snapshot) => {
        if (!snapshot) return;
        dispatch({ type: "HYDRATE", snapshot });
      });
      return;
    }

    const storedId = sessionStorage.getItem(ACTIVE_ENCOUNTER_KEY);
    if (!storedId) return;

    fetchSnapshot(storedId).then((snapshot) => {
      if (!snapshot) {
        sessionStorage.removeItem(ACTIVE_ENCOUNTER_KEY);
        return;
      }
      dispatch({ type: "HYDRATE", snapshot });
    });
  }, [readOnly, replayEncounterId]);

  const startEncounter = useCallback(async (mode: "demo" | "live") => {
    if (readOnly) return;
    dispatch({ type: "SET_LOADING", loading: mode === "demo" });

    const res = await fetch("/api/encounter", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode }),
    });

    if (!res.ok) return;

    const data = (await res.json()) as {
      encounterId: string;
      startedAt: string;
      mode: "demo" | "live";
    };

    sessionStorage.setItem(ACTIVE_ENCOUNTER_KEY, data.encounterId);
    encounterIdRef.current = data.encounterId;
    dispatch({
      type: "SET_ENCOUNTER",
      encounterId: data.encounterId,
      startedAt: data.startedAt,
      mode: data.mode,
    });
    dispatch({ type: "SET_LOADING", loading: mode === "demo" });

    if (mode === "demo") {
      setTimeout(() => dispatch({ type: "SET_LOADING", loading: false }), 30000);
    }
  }, [readOnly]);

  const requestHandoff = useCallback(async () => {
    if (readOnly || !state.encounterId) return;
    dispatch({ type: "SET_LOADING", loading: true });
    await fetch("/api/handoff", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ encounterId: state.encounterId }),
    });
  }, [readOnly, state.encounterId]);

  const pushTranscript = useCallback(
    async (text: string, speaker: Speaker) => {
      if (readOnly || !state.encounterId) return;
      await fetch("/api/transcript", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, speaker, encounterId: state.encounterId }),
      });
    },
    [readOnly, state.encounterId]
  );

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
    readOnly,
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
