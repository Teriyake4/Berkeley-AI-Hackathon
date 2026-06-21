"use client";

import { useCallback } from "react";
import type { HandoffReport } from "@/types/events";
import type { TranscriptLine } from "@/hooks/useEncounterEvents";

export function HandoffModal({
  open,
  onClose,
  transcript,
  report,
  loading,
}: {
  open: boolean;
  onClose: () => void;
  transcript: TranscriptLine[];
  report: HandoffReport | null;
  loading: boolean;
}) {
  const handlePrint = useCallback(() => {
    window.print();
  }, []);

  const handleCopy = useCallback(async () => {
    if (!report) return;
    const text = buildPlainText(report);
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      /* ignore */
    }
  }, [report]);

  if (!open) return null;

  const rawTranscript = transcript.map((l) => `[${l.speaker}] ${l.text}`).join("\n");

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink-950/85 p-4 backdrop-blur-sm animate-fade-in">
      <div className="bg-ink-850 rounded-2xl shadow-panel max-w-5xl w-full max-h-[92vh] overflow-hidden flex flex-col ring-1 ring-white/10">

        {/* Header */}
        <div className="px-6 py-4 border-b border-[var(--line)] flex items-center justify-between">
          <div>
            <h2 className="font-display text-lg font-extrabold tracking-tight text-[var(--text)]">
              Ambulance → Hospital Handoff
            </h2>
            {report?.generatedAt && (
              <p className="mt-0.5 font-mono text-[11px] text-[var(--text-faint)] uppercase tracking-[0.1em]">
                Generated {new Date(report.generatedAt).toLocaleString()}
              </p>
            )}
          </div>
          <div className="flex items-center gap-2">
            {report && (
              <>
                <button
                  onClick={handleCopy}
                  className="text-xs px-3 py-1.5 rounded-lg border border-[var(--line-strong)] text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-white/5 transition-colors font-medium"
                >
                  Copy
                </button>
                <button
                  onClick={handlePrint}
                  className="text-xs px-3 py-1.5 rounded-lg border border-[var(--line-strong)] text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-white/5 transition-colors font-medium"
                >
                  Print
                </button>
              </>
            )}
            <button
              onClick={onClose}
              className="ml-1 text-[var(--text-faint)] hover:text-[var(--text)] text-2xl leading-none w-8 h-8 flex items-center justify-center rounded-full hover:bg-white/8 transition-colors"
              aria-label="Close"
            >
              ×
            </button>
          </div>
        </div>

        {/* Loading state */}
        {loading && (
          <div className="flex-1 flex flex-col items-center justify-center p-12 text-[var(--text-faint)]">
            <div className="w-8 h-8 border-2 border-ink-600 border-t-clinical-400 rounded-full animate-spin mb-4" />
            <p className="text-sm font-medium text-[var(--text-muted)]">Generating handoff report…</p>
            <p className="text-xs text-[var(--text-faint)] mt-1">Claude is synthesizing the encounter</p>
          </div>
        )}

        {/* Main content — before/after split */}
        {!loading && report && (
          <div className="flex-1 overflow-hidden flex flex-col md:flex-row">

            {/* Left — raw transcript */}
            <div className="md:w-[38%] p-6 border-r border-[var(--line)] overflow-y-auto bg-ink-900">
              <h3 className="panel-label mb-3 flex items-center gap-2">
                <span className="bg-ink-700 text-[var(--text-faint)] text-[10px] px-1.5 py-0.5 rounded font-bold tracking-wider">BEFORE</span>
                Raw Transcript
              </h3>
              <pre className="text-xs text-[var(--text-faint)] whitespace-pre-wrap font-mono leading-relaxed">
                {rawTranscript || "No transcript captured."}
              </pre>
            </div>

            {/* Right — structured report */}
            <div className="md:flex-1 p-6 overflow-y-auto bg-ink-850">
              <h3 className="panel-label mb-4 flex items-center gap-2">
                <span className="bg-clinical-500/20 text-clinical-300 text-[10px] px-1.5 py-0.5 rounded font-bold tracking-wider border border-clinical-500/30">AFTER</span>
                Structured Handoff · Receiving ED
              </h3>

              {/* Patient summary */}
              <section className="mb-5">
                <h4 className="panel-label mb-1.5">Patient Summary</h4>
                <p className="text-sm text-[var(--text-muted)] leading-relaxed bg-ink-800 border border-[var(--line)] rounded-lg p-3">
                  {report.patientSummary}
                </p>
              </section>

              {/* Allergies — prominent */}
              <section className="mb-5">
                <h4 className="panel-label mb-1.5 flex items-center gap-1.5 text-signal-400">
                  <span className="h-1.5 w-1.5 rounded-full bg-signal-500" /> Allergies
                </h4>
                {(report.allergies ?? []).length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {(report.allergies ?? []).map((a, i) => (
                      <span
                        key={i}
                        className="text-xs bg-signal-500/15 text-signal-200 border border-signal-500/35 rounded-full px-3 py-1 font-bold capitalize"
                      >
                        {a}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-[var(--text-faint)] italic">NKDA — no known drug allergies</p>
                )}
              </section>

              {/* Timeline */}
              {report.timeline.length > 0 && (
                <section className="mb-5">
                  <h4 className="panel-label mb-2">Key Events</h4>
                  <ol className="relative border-l border-clinical-500/25 ml-2 space-y-3">
                    {report.timeline.map((entry) => (
                      <li key={entry.id} className="ml-4">
                        <span className="absolute -left-1.5 mt-1 h-3 w-3 rounded-full bg-clinical-400 ring-4 ring-ink-850" />
                        <time className="text-xs text-[var(--text-faint)] font-mono">
                          {new Date(entry.timestamp).toLocaleTimeString([], {
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </time>
                        <p
                          className={`text-sm leading-snug ${
                            entry.source === "safety"
                              ? "text-signal-300 font-medium"
                              : "text-[var(--text-muted)]"
                          }`}
                        >
                          {entry.summary.replace(/^⚠\s*/, "")}
                        </p>
                      </li>
                    ))}
                  </ol>
                </section>
              )}

              {/* Current medications */}
              {report.currentMedications.length > 0 && (
                <section className="mb-5">
                  <h4 className="panel-label mb-2">Current Medications</h4>
                  <div className="flex flex-wrap gap-2">
                    {report.currentMedications.map((m, i) => (
                      <span
                        key={i}
                        className={`text-xs rounded-full px-3 py-1 font-medium capitalize border ${
                          m.source === "vision"
                            ? "bg-vitals-400/10 text-vitals-400 border-vitals-400/25"
                            : "bg-clinical-500/10 text-clinical-300 border-clinical-500/25"
                        }`}
                      >
                        {m.name}
                        {m.dose ? ` — ${m.dose}` : ""}
                        <span className="ml-1.5 text-[10px] font-normal opacity-60">
                          {m.source === "vision" ? "camera" : "stated"}
                        </span>
                      </span>
                    ))}
                  </div>
                </section>
              )}

              {/* Outstanding questions */}
              {report.outstandingQuestions.length > 0 && (
                <section className="mb-5">
                  <h4 className="panel-label mb-2">Outstanding Questions</h4>
                  <ul className="space-y-1.5">
                    {report.outstandingQuestions.map((q, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-[var(--text-muted)]">
                        <span className="text-amber-400 mt-0.5 shrink-0 font-bold">?</span>
                        {q}
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {/* Recommended actions */}
              {report.recommendedActions.length > 0 && (
                <section>
                  <h4 className="panel-label mb-2">Recommended Actions</h4>
                  <ol className="space-y-1.5 list-none">
                    {report.recommendedActions.map((a, i) => (
                      <li key={i} className="flex items-start gap-2.5 text-sm text-[var(--text-muted)]">
                        <span className="bg-clinical-500/20 text-clinical-300 border border-clinical-500/30 text-xs rounded-full h-5 w-5 flex items-center justify-center shrink-0 font-bold mt-0.5">
                          {i + 1}
                        </span>
                        {a}
                      </li>
                    ))}
                  </ol>
                </section>
              )}
            </div>
          </div>
        )}

        {/* Footer disclaimer */}
        {report && (
          <div className="px-6 py-2.5 border-t border-[var(--line)] bg-ink-900 text-[var(--text-faint)] text-xs text-center font-mono tracking-wide">
            Demo purposes only — not for clinical use. Always verify with a licensed clinician.
          </div>
        )}
      </div>
    </div>
  );
}

function buildPlainText(report: HandoffReport): string {
  const lines: string[] = [
    "AMBULANCE → HOSPITAL HANDOFF REPORT",
    `Generated: ${new Date(report.generatedAt).toLocaleString()}`,
    "",
    "PATIENT SUMMARY",
    report.patientSummary,
    "",
    "ALLERGIES",
    (report.allergies ?? []).length > 0
      ? (report.allergies ?? []).map((a) => `  ! ${a}`).join("\n")
      : "  NKDA (no known drug allergies)",
    "",
  ];

  if (report.currentMedications.length > 0) {
    lines.push("CURRENT MEDICATIONS");
    report.currentMedications.forEach((m) =>
      lines.push(
        `  - ${m.name}${m.dose ? ` (${m.dose})` : ""}${
          m.source === "vision" ? " [camera-identified]" : ""
        }`
      )
    );
    lines.push("");
  }

  if (report.outstandingQuestions.length > 0) {
    lines.push("OUTSTANDING QUESTIONS");
    report.outstandingQuestions.forEach((q) => lines.push(`  ? ${q}`));
    lines.push("");
  }

  if (report.recommendedActions.length > 0) {
    lines.push("RECOMMENDED ACTIONS");
    report.recommendedActions.forEach((a, i) => lines.push(`  ${i + 1}. ${a}`));
    lines.push("");
  }

  lines.push("Demo only — not for clinical use.");
  return lines.join("\n");
}
