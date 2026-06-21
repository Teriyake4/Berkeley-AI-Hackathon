"use client";

import { useState } from "react";
import type { Citation, SafetyFlaggedPayload } from "@/types/events";

const severityConfig = {
  critical: {
    card: "border-signal-500/60 bg-signal-500/15 ring-1 ring-signal-500/40",
    label: "bg-signal-600 text-white",
    text: "text-signal-100",
    subtext: "text-signal-200/80",
    bar: "bg-signal-500",
  },
  high: {
    card: "border-signal-500/35 bg-signal-500/10",
    label: "bg-signal-500 text-white",
    text: "text-signal-100",
    subtext: "text-signal-200/75",
    bar: "bg-signal-500",
  },
  medium: {
    card: "border-amber-400/30 bg-amber-400/10",
    label: "bg-amber-400 text-ink-950",
    text: "text-amber-100",
    subtext: "text-amber-200/75",
    bar: "bg-amber-400",
  },
  low: {
    card: "border-clinical-400/25 bg-clinical-400/10",
    label: "bg-clinical-400 text-ink-950",
    text: "text-clinical-100",
    subtext: "text-clinical-200/75",
    bar: "bg-clinical-400",
  },
};

interface ResearchItem {
  query: string;
  findings: string;
  citations: Citation[];
}

export function InsightsPanel({
  safetyFlags,
  missingInfo,
  research,
  suggestedFollowUps,
}: {
  safetyFlags: SafetyFlaggedPayload[];
  missingInfo: string[];
  research: ResearchItem[];
  suggestedFollowUps: string[];
}) {
  const [expandedFlags, setExpandedFlags] = useState<Set<string>>(new Set());

  const toggleFlag = (key: string) => {
    setExpandedFlags((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const NREMT_PREFIX = "NREMT gap:";
  const realFlags = safetyFlags.filter((f) => !f.concern.startsWith(NREMT_PREFIX));
  const nremtFlags = safetyFlags.filter((f) => f.concern.startsWith(NREMT_PREFIX));

  const sortedFlags = [...realFlags].sort((a, b) => {
    const order = { critical: 0, high: 1, medium: 2, low: 3 };
    return order[a.severity] - order[b.severity];
  });

  return (
    <div className="flex h-full flex-col">
      <h2 className="panel-label mb-3">AI Insights</h2>
      <div className="flex-1 space-y-5 overflow-y-auto pr-0.5">

        {/* Safety Flags */}
        <section>
          <h3 className="panel-label mb-2 flex items-center gap-1.5 normal-case tracking-[0.14em]">
            Safety Flags
            {realFlags.length > 0 && (
              <span className="rounded-full bg-signal-500 px-1.5 py-0.5 text-[10px] font-bold leading-none text-white">
                {realFlags.length}
              </span>
            )}
          </h3>
          {sortedFlags.length === 0 ? (
            <p className="font-mono text-sm text-[var(--text-faint)]">No concerns flagged yet</p>
          ) : (
            sortedFlags.map((flag, i) => {
              const cfg = severityConfig[flag.severity];
              const key = flag.flaggedAt ?? String(i);
              const expanded = expandedFlags.has(key);
              const hasDetail =
                !!flag.rationale ||
                !!flag.clarifyingQuestion ||
                (flag.recommendedActions != null && flag.recommendedActions.length > 0);

              return (
                <div
                  key={i}
                  className={`animate-fade-in relative mb-2 overflow-hidden rounded-xl border pl-4 ${cfg.card}`}
                >
                  <span className={`absolute inset-y-0 left-0 w-1 ${cfg.bar}`} />

                  {/* Always-visible header — click to expand */}
                  <button
                    type="button"
                    onClick={() => hasDetail && toggleFlag(key)}
                    className={`w-full p-3 text-left ${hasDetail ? "cursor-pointer" : "cursor-default"}`}
                    aria-expanded={hasDetail ? expanded : undefined}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span
                        className={`rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide ${cfg.label}`}
                      >
                        {flag.severity}
                      </span>
                      {hasDetail && (
                        <span
                          className={`shrink-0 text-xs text-[var(--text-faint)] transition-transform duration-200 ${
                            expanded ? "rotate-180" : ""
                          }`}
                        >
                          ▾
                        </span>
                      )}
                    </div>
                    <p className={`mt-1.5 text-sm font-semibold leading-snug ${cfg.text}`}>
                      {flag.concern}
                    </p>
                  </button>

                  {/* Collapsible detail */}
                  {expanded && hasDetail && (
                    <div className="px-3 pb-3">
                      {flag.rationale && (
                        <p className={`text-xs leading-relaxed ${cfg.subtext}`}>
                          {flag.rationale}
                        </p>
                      )}
                      {flag.clarifyingQuestion && (
                        <p className="mt-2 rounded-lg border border-[var(--line-strong)] bg-ink-900/60 px-2 py-1 text-xs font-medium text-[var(--text-muted)]">
                          &ldquo;{flag.clarifyingQuestion}&rdquo;
                        </p>
                      )}
                      {flag.recommendedActions && flag.recommendedActions.length > 0 && (
                        <ul className="mt-2 space-y-1">
                          {flag.recommendedActions.map((action, j) => (
                            <li
                              key={j}
                              className="flex items-start gap-1.5 text-xs text-[var(--text-muted)]"
                            >
                              <span className="mt-0.5 shrink-0 text-vitals-400">&#8594;</span>
                              <span>{action}</span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </section>

        {/* NREMT Reminders */}
        {nremtFlags.length > 0 && (
          <section>
            <h3 className="panel-label mb-2 flex items-center gap-1.5 normal-case tracking-[0.14em]">
              NREMT Reminders
              <span className="rounded-full bg-amber-400 px-1.5 py-0.5 text-[10px] font-bold leading-none text-ink-950">
                {nremtFlags.length}
              </span>
            </h3>
            <ul className="space-y-1.5 rounded-xl border border-amber-400/25 bg-amber-400/[0.07] p-3">
              {nremtFlags.map((flag, i) => (
                <li
                  key={i}
                  className="animate-fade-in flex items-start gap-2 text-sm text-[var(--text-muted)]"
                >
                  <span className="mt-0.5 shrink-0 text-amber-400">&#9744;</span>
                  <div className="min-w-0 flex-1">
                    <p className="leading-snug text-[var(--text)]">
                      {flag.concern.replace(NREMT_PREFIX, "").trim()}
                    </p>
                    {flag.rationale && (
                      <p className="mt-0.5 text-xs leading-relaxed text-[var(--text-faint)]">
                        {flag.rationale}
                      </p>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* Missing Information */}
        {missingInfo.length > 0 && (
          <section>
            <h3 className="panel-label mb-2 normal-case tracking-[0.14em]">Missing Information</h3>
            <ul className="space-y-1.5">
              {missingInfo.map((item) => (
                <li
                  key={item}
                  className="flex items-center gap-2 text-sm text-[var(--text-muted)]"
                >
                  <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-amber-400" />
                  {item}
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* Suggested Follow-Up Questions */}
        {suggestedFollowUps.length > 0 && (
          <section>
            <h3 className="panel-label mb-2 normal-case tracking-[0.14em]">Suggested Questions</h3>
            <ul className="space-y-1.5">
              {suggestedFollowUps.map((q) => (
                <li
                  key={q}
                  className="animate-fade-in flex items-start gap-2 rounded-lg border border-[var(--line)] bg-ink-900/50 px-3 py-2 text-sm text-[var(--text-muted)]"
                >
                  <span className="mt-0.5 shrink-0 font-mono text-clinical-400">?</span>
                  {q}
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* Research Citations */}
        <section>
          <h3 className="panel-label mb-2 flex items-center gap-1.5 normal-case tracking-[0.14em]">
            Research
            {research.length > 0 && (
              <span className="rounded-full bg-clinical-400 px-1.5 py-0.5 text-[10px] font-bold leading-none text-ink-950">
                {research.length}
              </span>
            )}
          </h3>
          {research.length === 0 ? (
            <p className="font-mono text-sm text-[var(--text-faint)]">Research agent idle</p>
          ) : (
            research.map((r, i) => (
              <div
                key={i}
                className="animate-fade-in mb-4 border-b border-[var(--line)] pb-4 last:mb-0 last:border-0 last:pb-0"
              >
                <p className="mb-1 font-mono text-[11px] font-semibold uppercase tracking-wide text-clinical-300">
                  {r.query}
                </p>
                <p className="mb-2 text-sm leading-relaxed text-[var(--text-muted)]">
                  {r.findings}
                </p>
                <div className="space-y-2">
                  {r.citations.map((c, j) => (
                    <div
                      key={j}
                      className="rounded-lg border border-[var(--line)] bg-ink-900/50 px-2.5 py-1.5"
                    >
                      <a
                        href={c.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="group flex items-start gap-1.5"
                      >
                        <span className="mt-0.5 shrink-0 text-xs text-clinical-400">&#8599;</span>
                        <span className="text-xs font-medium leading-snug text-clinical-200 group-hover:underline">
                          {c.title}
                        </span>
                      </a>
                      {c.snippet && (
                        <p className="mt-1 pl-4 text-[11px] leading-snug text-[var(--text-faint)]">
                          {c.snippet}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))
          )}
        </section>
      </div>
    </div>
  );
}
