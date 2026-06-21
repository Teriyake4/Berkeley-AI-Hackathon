"use client";

import Link from "next/link";
import { useState } from "react";
import { useEncounterEvents } from "@/hooks/useEncounterEvents";
import { DisclaimerBanner } from "@/components/DisclaimerBanner";
import { SafetyAlertBanner } from "@/components/SafetyAlertBanner";
import { TranscriptPanel } from "@/components/TranscriptPanel";
import { TimelinePanel } from "@/components/TimelinePanel";
import { InsightsPanel } from "@/components/InsightsPanel";
import { SoapPanel } from "@/components/SoapPanel";
import { HandoffModal } from "@/components/HandoffModal";
import { LiveMic } from "@/components/LiveMic";
import { VisionCapture } from "@/components/VisionCapture";
import { TelemetryBar } from "@/components/TelemetryBar";
import type { MedicalEntities } from "@/types/events";

const AGENT_LABELS: Record<string, string> = {
  extraction: "Extraction",
  timeline: "Timeline",
  safety: "Safety",
  documentation: "PCR",
  research: "Research",
  vision: "Vision",
  handoff: "Handoff",
};

function formatStartTime(iso: string | null): string {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

export function Dashboard({ replayEncounterId }: { replayEncounterId?: string }) {
  const {
    state,
    missingInfo,
    suggestedFollowUps,
    startEncounter,
    requestHandoff,
    pushTranscript,
    readOnly,
  } = useEncounterEvents({ replayEncounterId });
  const [handoffOpen, setHandoffOpen] = useState(false);

  const handleHandoff = async () => {
    setHandoffOpen(true);
    if (!readOnly) {
      await requestHandoff();
    }
  };

  const loadingReplay = readOnly && !state.encounterId;

  if (loadingReplay) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 text-slate-500">
        Loading session…
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col bg-slate-50">
      <DisclaimerBanner />

      {readOnly && (
        <div className="bg-slate-800 text-slate-100 px-6 py-2 text-sm flex items-center justify-between gap-4">
          <span>
            <span className="font-semibold text-amber-300">Replay mode</span>
            {" — "}
            {state.startedAt
              ? `Session from ${formatStartTime(state.startedAt)}`
              : "Viewing archived session"}
            . Recordings disabled.
          </span>
          <div className="flex items-center gap-3 shrink-0">
            <Link
              href="/logs"
              className="text-slate-300 hover:text-white underline-offset-2 hover:underline"
            >
              ← All sessions
            </Link>
            <Link
              href="/"
              className="px-3 py-1 rounded-md bg-ambulance-600 text-white text-xs font-semibold hover:bg-ambulance-500"
            >
              New Session
            </Link>
          </div>
        </div>
      )}

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <header className="bg-ambulance-900 text-white px-6 py-3 flex items-center justify-between shadow-md">
        <div className="flex items-center gap-3">
          <span className="text-2xl" aria-hidden>
            🚑
          </span>
          <div>
            <h1 className="text-xl font-bold tracking-tight">Nos</h1>
            <p className="text-ambulance-200 text-xs">
              AI Paramedic Copilot — scene to hospital handoff
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {!readOnly && (
            <>
              <span
                className={`text-xs px-2.5 py-1 rounded-full font-medium ${
                  state.connected
                    ? "bg-emerald-500/20 text-emerald-300"
                    : "bg-red-500/20 text-red-300 animate-pulse"
                }`}
              >
                {state.connected ? "● Connected" : "○ Reconnecting…"}
              </span>

              <Link
                href="/logs"
                className="px-3 py-2 text-sm font-medium rounded-lg bg-ambulance-800 text-ambulance-100 hover:bg-ambulance-700 border border-ambulance-700 transition-colors"
              >
                Session Log
              </Link>

              <div className="flex rounded-lg overflow-hidden border border-ambulance-700">
                <button
                  onClick={() => startEncounter("demo")}
                  disabled={state.mode === "demo" && state.loading}
                  className={`px-4 py-2 text-sm font-medium transition-colors ${
                    state.mode === "demo"
                      ? "bg-ambulance-500 text-white"
                      : "bg-ambulance-800 text-ambulance-100 hover:bg-ambulance-700"
                  }`}
                >
                  {state.mode === "demo" && state.loading ? "Running…" : "Demo"}
                </button>
                <button
                  onClick={() => startEncounter("live")}
                  className={`px-4 py-2 text-sm font-medium transition-colors ${
                    state.mode === "live"
                      ? "bg-ambulance-500 text-white"
                      : "bg-ambulance-800 text-ambulance-100 hover:bg-ambulance-700"
                  }`}
                >
                  Live
                </button>
              </div>

              <LiveMic active={state.mode === "live"} onTranscript={pushTranscript} />
            </>
          )}

          {readOnly && (
            <span className="text-xs px-2.5 py-1 rounded-full font-medium bg-slate-500/30 text-slate-200">
              Archived
            </span>
          )}
        </div>
      </header>

      {/* ── Agent activity strip ────────────────────────────────────────────── */}
      {!readOnly && (
        <div className="bg-clinical-950 border-b border-clinical-800 px-6 py-1.5 flex items-center gap-4">
          <span className="text-xs text-clinical-400 font-medium mr-1">AGENTS</span>
          {Object.entries(AGENT_LABELS).map(([key, label]) => {
            const active = state.activeAgents.has(key);
            return (
              <div key={key} className="flex items-center gap-1.5">
                <span
                  className={`h-1.5 w-1.5 rounded-full transition-all duration-300 ${
                    active
                      ? "bg-emerald-400 shadow-[0_0_6px_2px_rgba(52,211,153,0.6)]"
                      : "bg-clinical-700"
                  }`}
                />
                <span
                  className={`text-xs font-medium transition-colors ${
                    active ? "text-emerald-300" : "text-clinical-500"
                  }`}
                >
                  {label}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* ── Entity chips bar ────────────────────────────────────────────────── */}
      {state.entities && hasAnyEntities(state.entities) && (
        <div className="bg-white border-b border-slate-200 px-4 py-2 flex flex-wrap items-center gap-2">
          <span className="text-xs text-slate-400 font-medium mr-1">EXTRACTED</span>
          {state.entities.demographics?.age && (
            <EntityChip label={`${state.entities.demographics.age}yo`} color="purple" />
          )}
          {state.entities.demographics?.sex && (
            <EntityChip label={state.entities.demographics.sex} color="purple" />
          )}
          {state.entities.symptoms.map((s) => (
            <EntityChip key={s} label={s} color="amber" />
          ))}
          {state.entities.medications.map((m) => (
            <EntityChip
              key={m.name}
              label={
                m.dose?.includes("administered")
                  ? `💉 ${m.name} (given on scene)`
                  : m.name
              }
              color={m.dose?.includes("administered") ? "red" : "blue"}
            />
          ))}
          {state.entities.conditions.map((c) => (
            <EntityChip key={c} label={c} color="slate" />
          ))}
          {state.entities.allergies.map((a) => (
            <EntityChip key={a} label={`⚠ ${a} allergy`} color="red" />
          ))}
        </div>
      )}

      <SafetyAlertBanner safetyFlags={state.safetyFlags} entities={state.entities} />

      {/* ── Main panels ─────────────────────────────────────────────────────── */}
      <main className="flex-1 p-4 grid grid-rows-[1fr_auto] gap-4 overflow-hidden">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 min-h-0">
          <div className="lg:col-span-3 bg-white rounded-xl border border-slate-200 p-4 shadow-sm min-h-[280px] lg:min-h-0 flex flex-col">
            <TranscriptPanel lines={state.transcript} />
          </div>
          <div className="lg:col-span-5 bg-white rounded-xl border border-slate-200 p-4 shadow-sm min-h-[280px] lg:min-h-0 flex flex-col">
            <TimelinePanel events={state.timeline} />
          </div>
          <div className="lg:col-span-4 bg-white rounded-xl border border-slate-200 p-4 shadow-sm min-h-[280px] lg:min-h-0 flex flex-col">
            <InsightsPanel
              safetyFlags={state.safetyFlags}
              missingInfo={missingInfo}
              research={state.research}
              suggestedFollowUps={suggestedFollowUps}
            />
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
          <div className="lg:col-span-4 bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
            <VisionCapture
              active={!readOnly}
              readOnly={readOnly}
              encounterId={state.encounterId}
              visionItems={state.visionItems}
            />
          </div>
          <div className="lg:col-span-8 bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
            <SoapPanel soap={state.soap} />
          </div>
        </div>
      </main>

      {/* ── Footer ──────────────────────────────────────────────────────────── */}
      <footer className="px-6 py-3 border-t bg-white flex items-center justify-between gap-6">
        <div className="flex-1 min-w-0">
          <TelemetryBar phase={state.phase} />
        </div>
        <button
          onClick={handleHandoff}
          disabled={state.transcript.length === 0}
          className="px-6 py-2.5 rounded-lg bg-ambulance-600 text-white font-semibold text-sm hover:bg-ambulance-700 active:bg-ambulance-800 disabled:opacity-40 disabled:cursor-not-allowed shadow-md transition-colors shrink-0"
        >
          {readOnly ? "View Handoff Report" : "Generate Handoff Report"}
        </button>
      </footer>

      <HandoffModal
        open={handoffOpen}
        onClose={() => setHandoffOpen(false)}
        transcript={state.transcript}
        report={state.handoff}
        loading={!readOnly && state.loading && !state.handoff}
      />
    </div>
  );
}

function hasAnyEntities(e: MedicalEntities): boolean {
  return (
    e.medications.length > 0 ||
    e.symptoms.length > 0 ||
    e.conditions.length > 0 ||
    e.allergies.length > 0 ||
    Boolean(e.demographics?.age)
  );
}

const chipColors = {
  purple: "bg-purple-50 text-purple-800 border-purple-200",
  amber: "bg-amber-50 text-amber-800 border-amber-200",
  blue: "bg-blue-50 text-blue-800 border-blue-200",
  slate: "bg-slate-100 text-slate-700 border-slate-200",
  red: "bg-red-50 text-red-800 border-red-200",
};

function EntityChip({
  label,
  color,
}: {
  label: string;
  color: keyof typeof chipColors;
}) {
  return (
    <span
      className={`inline-block text-xs font-medium px-2 py-0.5 rounded-full border animate-fade-in capitalize ${chipColors[color]}`}
    >
      {label}
    </span>
  );
}
