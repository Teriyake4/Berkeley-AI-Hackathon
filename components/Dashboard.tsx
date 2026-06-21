"use client";

import Link from "next/link";
import { useState } from "react";
import { useEncounterEvents } from "@/hooks/useEncounterEvents";
import { NosMark } from "@/components/NosMark";
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
      <div className="flex min-h-screen items-center justify-center bg-ink-900 font-mono text-sm text-[var(--text-faint)]">
        <span className="mr-2 h-2 w-2 animate-pulse rounded-full bg-clinical-400" />
        Loading session…
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col bg-ink-900 text-[var(--text)]">
      <DisclaimerBanner />

      {readOnly && (
        <div className="flex items-center justify-between gap-4 border-b border-[var(--line)] bg-ink-850 px-6 py-2 text-sm text-[var(--text-muted)]">
          <span>
            <span className="font-semibold text-amber-400">Replay mode</span>
            {" — "}
            {state.startedAt
              ? `Session from ${formatStartTime(state.startedAt)}`
              : "Viewing archived session"}
            . Recordings disabled.
          </span>
          <div className="flex shrink-0 items-center gap-3">
            <Link
              href="/logs"
              className="text-[var(--text-muted)] underline-offset-2 hover:text-white hover:underline"
            >
              ← All sessions
            </Link>
            <Link
              href="/dashboard"
              className="rounded-md bg-signal-500 px-3 py-1 text-xs font-semibold text-white hover:bg-signal-400"
            >
              New Session
            </Link>
          </div>
        </div>
      )}

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <header className="flex items-center justify-between border-b border-[var(--line)] bg-ink-850/90 px-6 py-3 backdrop-blur supports-[backdrop-filter]:bg-ink-850/70">
        <Link href="/" className="flex items-center gap-3">
          <NosMark size={32} />
          <div>
            <h1 className="font-display text-xl font-extrabold leading-none tracking-tight">
              Nos
            </h1>
            <p className="mt-0.5 font-mono text-[10px] uppercase tracking-[0.16em] text-[var(--text-faint)]">
              Paramedic Copilot · scene → handoff
            </p>
          </div>
        </Link>

        <div className="flex items-center gap-3">
          {!readOnly && (
            <>
              <span
                className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 font-mono text-[11px] font-medium ${
                  state.connected
                    ? "bg-vitals-400/15 text-vitals-400"
                    : "animate-pulse bg-signal-500/15 text-signal-300"
                }`}
              >
                <span
                  className={`h-1.5 w-1.5 rounded-full ${
                    state.connected ? "bg-vitals-400" : "bg-signal-400"
                  }`}
                />
                {state.connected ? "CONNECTED" : "RECONNECTING"}
              </span>

              <Link
                href="/logs"
                className="rounded-lg border border-[var(--line-strong)] px-3 py-2 text-sm font-medium text-[var(--text-muted)] transition-colors hover:bg-white/5 hover:text-white"
              >
                Sessions
              </Link>

              <div className="flex overflow-hidden rounded-lg border border-[var(--line-strong)]">
                <button
                  onClick={() => startEncounter("demo")}
                  disabled={state.mode === "demo" && state.loading}
                  className={`px-4 py-2 text-sm font-medium transition-colors ${
                    state.mode === "demo"
                      ? "bg-clinical-500 text-ink-950"
                      : "bg-transparent text-[var(--text-muted)] hover:bg-white/5"
                  }`}
                >
                  {state.mode === "demo" && state.loading ? "Running…" : "Demo"}
                </button>
                <button
                  onClick={() => startEncounter("live")}
                  className={`border-l border-[var(--line-strong)] px-4 py-2 text-sm font-medium transition-colors ${
                    state.mode === "live"
                      ? "bg-signal-500 text-white"
                      : "bg-transparent text-[var(--text-muted)] hover:bg-white/5"
                  }`}
                >
                  Live
                </button>
              </div>

              <LiveMic active={state.mode === "live"} onTranscript={pushTranscript} />
            </>
          )}

          {readOnly && (
            <span className="rounded-full bg-white/5 px-2.5 py-1 font-mono text-[11px] font-medium text-[var(--text-muted)]">
              ARCHIVED
            </span>
          )}
        </div>
      </header>

      {/* ── Agent activity strip ────────────────────────────────────────────── */}
      {!readOnly && (
        <div className="flex items-center gap-5 border-b border-[var(--line)] bg-ink-950/60 px-6 py-2">
          <span className="panel-label">Agents</span>
          {Object.entries(AGENT_LABELS).map(([key, label]) => {
            const active = state.activeAgents.has(key);
            return (
              <div key={key} className="flex items-center gap-1.5">
                <span
                  className={`h-1.5 w-1.5 rounded-full transition-all duration-300 ${
                    active
                      ? "bg-vitals-400 shadow-[0_0_8px_2px_rgba(61,220,151,0.6)]"
                      : "bg-ink-600"
                  }`}
                />
                <span
                  className={`text-xs font-medium transition-colors ${
                    active ? "text-vitals-400" : "text-[var(--text-faint)]"
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
        <div className="flex flex-wrap items-center gap-2 border-b border-[var(--line)] bg-ink-850/50 px-4 py-2">
          <span className="panel-label mr-1">Extracted</span>
          {state.entities.demographics?.age && (
            <EntityChip label={`${state.entities.demographics.age}yo`} color="violet" />
          )}
          {state.entities.demographics?.sex && (
            <EntityChip label={state.entities.demographics.sex} color="violet" />
          )}
          {state.entities.symptoms.map((s) => (
            <EntityChip key={s} label={s} color="amber" />
          ))}
          {state.entities.medications.map((m) => (
            <EntityChip
              key={m.name}
              label={
                m.dose?.includes("administered")
                  ? `${m.name} (given on scene)`
                  : m.name
              }
              color={m.dose?.includes("administered") ? "signal" : "cyan"}
            />
          ))}
          {state.entities.conditions.map((c) => (
            <EntityChip key={c} label={c} color="slate" />
          ))}
          {state.entities.allergies.map((a) => (
            <EntityChip key={a} label={`${a} allergy`} color="signal" />
          ))}
        </div>
      )}

      <SafetyAlertBanner safetyFlags={state.safetyFlags} entities={state.entities} />

      {/* ── Main panels ─────────────────────────────────────────────────────── */}
      <main className="grid flex-1 grid-rows-[1fr_auto] gap-4 overflow-hidden p-4">
        <div className="grid min-h-0 grid-cols-1 gap-4 lg:grid-cols-12">
          <div className="panel flex min-h-[280px] flex-col p-4 lg:col-span-3 lg:min-h-0">
            <TranscriptPanel lines={state.transcript} />
          </div>
          <div className="panel flex min-h-[280px] flex-col p-4 lg:col-span-5 lg:min-h-0">
            <TimelinePanel events={state.timeline} />
          </div>
          <div className="panel flex min-h-[280px] flex-col p-4 lg:col-span-4 lg:min-h-0">
            <InsightsPanel
              safetyFlags={state.safetyFlags}
              missingInfo={missingInfo}
              research={state.research}
              suggestedFollowUps={suggestedFollowUps}
            />
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
          <div className="panel p-4 lg:col-span-4">
            <VisionCapture
              active={!readOnly}
              readOnly={readOnly}
              encounterId={state.encounterId}
              visionItems={state.visionItems}
            />
          </div>
          <div className="panel p-4 lg:col-span-8">
            <SoapPanel soap={state.soap} />
          </div>
        </div>
      </main>

      {/* ── Footer ──────────────────────────────────────────────────────────── */}
      <footer className="flex items-center justify-end gap-6 border-t border-[var(--line)] bg-ink-850/80 px-6 py-3">
        <button
          onClick={handleHandoff}
          disabled={state.transcript.length === 0}
          className="shrink-0 rounded-lg bg-signal-500 px-6 py-2.5 text-sm font-semibold text-white shadow-glow transition-transform hover:-translate-y-0.5 active:translate-y-0 disabled:cursor-not-allowed disabled:opacity-30 disabled:shadow-none disabled:hover:translate-y-0"
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
  violet: "bg-violet-400/10 text-violet-200 border-violet-400/25",
  amber: "bg-amber-400/10 text-amber-200 border-amber-400/25",
  cyan: "bg-clinical-400/10 text-clinical-200 border-clinical-400/30",
  slate: "bg-white/5 text-[var(--text-muted)] border-[var(--line-strong)]",
  signal: "bg-signal-500/15 text-signal-200 border-signal-500/35",
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
      className={`animate-fade-in inline-block rounded-full border px-2.5 py-0.5 text-xs font-medium capitalize ${chipColors[color]}`}
    >
      {label}
    </span>
  );
}
