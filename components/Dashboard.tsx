"use client";

import { useState } from "react";
import { useEncounterEvents } from "@/hooks/useEncounterEvents";
import { DisclaimerBanner } from "@/components/DisclaimerBanner";
import { TranscriptPanel } from "@/components/TranscriptPanel";
import { TimelinePanel } from "@/components/TimelinePanel";
import { InsightsPanel } from "@/components/InsightsPanel";
import { SoapPanel } from "@/components/SoapPanel";
import { HandoffModal } from "@/components/HandoffModal";
import { LiveMic } from "@/components/LiveMic";
import type { MedicalEntities } from "@/lib/events";

const AGENT_LABELS: Record<string, string> = {
  extraction: "Extraction",
  timeline: "Timeline",
  safety: "Safety",
  documentation: "SOAP",
  research: "Research",
  handoff: "Handoff",
};

export function Dashboard() {
  const { state, missingInfo, suggestedFollowUps, startEncounter, requestHandoff, pushTranscript } =
    useEncounterEvents();
  const [handoffOpen, setHandoffOpen] = useState(false);

  const handleHandoff = async () => {
    setHandoffOpen(true);
    await requestHandoff();
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-50">
      <DisclaimerBanner />

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <header className="bg-clinical-900 text-white px-6 py-3 flex items-center justify-between shadow-md">
        <div>
          <h1 className="text-xl font-bold tracking-tight">ER Copilot</h1>
          <p className="text-clinical-200 text-xs">AI Clinical Operations Assistant</p>
        </div>

        <div className="flex items-center gap-3">
          {/* Connection status */}
          <span
            className={`text-xs px-2.5 py-1 rounded-full font-medium ${
              state.connected
                ? "bg-emerald-500/20 text-emerald-300"
                : "bg-red-500/20 text-red-300 animate-pulse"
            }`}
          >
            {state.connected ? "● Connected" : "○ Reconnecting…"}
          </span>

          {/* Mode toggle */}
          <div className="flex rounded-lg overflow-hidden border border-clinical-700">
            <button
              onClick={() => startEncounter("demo")}
              disabled={state.mode === "demo" && state.loading}
              className={`px-4 py-2 text-sm font-medium transition-colors ${
                state.mode === "demo"
                  ? "bg-clinical-500 text-white"
                  : "bg-clinical-800 text-clinical-100 hover:bg-clinical-700"
              }`}
            >
              {state.mode === "demo" && state.loading ? "Running…" : "Demo"}
            </button>
            <button
              onClick={() => startEncounter("live")}
              className={`px-4 py-2 text-sm font-medium transition-colors ${
                state.mode === "live"
                  ? "bg-clinical-500 text-white"
                  : "bg-clinical-800 text-clinical-100 hover:bg-clinical-700"
              }`}
            >
              Live
            </button>
          </div>

          <LiveMic active={state.mode === "live"} onTranscript={pushTranscript} />
        </div>
      </header>

      {/* ── Agent activity strip ────────────────────────────────────────────── */}
      <div className="bg-clinical-950 border-b border-clinical-800 px-6 py-1.5 flex items-center gap-4">
        <span className="text-xs text-clinical-400 font-medium mr-1">AGENTS</span>
        {Object.entries(AGENT_LABELS).map(([key, label]) => {
          const active = state.activeAgents.has(key);
          return (
            <div key={key} className="flex items-center gap-1.5">
              <span
                className={`h-1.5 w-1.5 rounded-full transition-all duration-300 ${
                  active ? "bg-emerald-400 shadow-[0_0_6px_2px_rgba(52,211,153,0.6)]" : "bg-clinical-700"
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
            <EntityChip key={m.name} label={m.name} color="blue" />
          ))}
          {state.entities.conditions.map((c) => (
            <EntityChip key={c} label={c} color="slate" />
          ))}
          {state.entities.allergies.map((a) => (
            <EntityChip key={a} label={`⚠ ${a} allergy`} color="red" />
          ))}
        </div>
      )}

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

        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
          <SoapPanel soap={state.soap} />
        </div>
      </main>

      {/* ── Footer ──────────────────────────────────────────────────────────── */}
      <footer className="px-6 py-3 border-t bg-white flex items-center justify-between">
        <p className="text-sm text-slate-500">
          {state.mode === "idle"
            ? "Select Demo or Live to begin an encounter"
            : state.mode === "demo"
            ? `Demo encounter — ${state.transcript.length} transcript lines`
            : `Live encounter — ${state.transcript.length} transcript lines`}
        </p>
        <button
          onClick={handleHandoff}
          disabled={state.transcript.length === 0}
          className="px-6 py-2.5 rounded-lg bg-clinical-600 text-white font-semibold text-sm hover:bg-clinical-700 active:bg-clinical-800 disabled:opacity-40 disabled:cursor-not-allowed shadow-md transition-colors"
        >
          Generate Handoff Report
        </button>
      </footer>

      <HandoffModal
        open={handoffOpen}
        onClose={() => setHandoffOpen(false)}
        transcript={state.transcript}
        report={state.handoff}
        loading={state.loading && !state.handoff}
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
