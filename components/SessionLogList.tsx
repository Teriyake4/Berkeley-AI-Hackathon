"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { NosMark } from "@/components/NosMark";
import type { SessionSummary } from "@/types/session";

function formatStartTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

export function SessionLogList() {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [loading, setLoading] = useState(true);

  const loadSessions = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/sessions");
      if (!res.ok) return;
      const data = (await res.json()) as { sessions: SessionSummary[] };
      setSessions(data.sessions ?? []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  return (
    <div className="flex min-h-screen flex-col bg-ink-900 text-[var(--text)]">
      <header className="flex items-center justify-between border-b border-[var(--line)] bg-ink-850/90 px-6 py-3.5 backdrop-blur">
        <Link href="/" className="flex items-center gap-3">
          <NosMark size={32} />
          <div>
            <h1 className="font-display text-xl font-extrabold leading-none tracking-tight">
              Session Log
            </h1>
            <p className="mt-0.5 font-mono text-[10px] uppercase tracking-[0.16em] text-[var(--text-faint)]">
              Past encounters · newest first
            </p>
          </div>
        </Link>
        <div className="flex items-center gap-3">
          <Link
            href="/dashboard"
            className="rounded-lg border border-[var(--line-strong)] px-3 py-2 text-sm font-medium text-[var(--text-muted)] transition-colors hover:bg-white/5 hover:text-white"
          >
            Live Console
          </Link>
          <Link
            href="/dashboard"
            className="rounded-lg bg-signal-500 px-4 py-2 text-sm font-semibold text-white shadow-glow transition-transform hover:-translate-y-0.5"
          >
            New Session
          </Link>
        </div>
      </header>

      <main className="mx-auto w-full max-w-3xl flex-1 p-6">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="panel-label">Sessions</h2>
          <button
            type="button"
            onClick={loadSessions}
            className="font-mono text-xs text-clinical-300 transition-colors hover:text-clinical-200"
          >
            ↻ Refresh
          </button>
        </div>

        <div className="overflow-hidden rounded-2xl border border-[var(--line)] bg-ink-850">
          {loading && (
            <p className="p-6 font-mono text-sm text-[var(--text-faint)]">
              Loading sessions…
            </p>
          )}
          {!loading && sessions.length === 0 && (
            <div className="p-10 text-center">
              <p className="mb-4 text-[var(--text-muted)]">No sessions recorded yet.</p>
              <Link
                href="/dashboard"
                className="inline-block rounded-lg bg-signal-500 px-4 py-2 text-sm font-semibold text-white shadow-glow"
              >
                Start New Session
              </Link>
            </div>
          )}
          {sessions.map((session) => (
            <Link
              key={session.encounterId}
              href={`/logs/${session.encounterId}`}
              className="block border-b border-[var(--line)] px-5 py-4 transition-colors last:border-b-0 hover:bg-white/[0.03]"
            >
              <div className="flex items-center justify-between gap-4">
                <div>
                  <div className="text-base font-medium text-[var(--text)]">
                    {session.startedAt
                      ? formatStartTime(session.startedAt)
                      : "Unknown start time"}
                  </div>
                  <div className="mt-1.5 flex items-center gap-2">
                    <span
                      className={`rounded px-2 py-0.5 font-mono text-[11px] font-medium capitalize ${
                        session.mode === "demo"
                          ? "bg-clinical-400/15 text-clinical-200"
                          : session.mode === "live"
                            ? "bg-vitals-400/15 text-vitals-400"
                            : "bg-white/5 text-[var(--text-faint)]"
                      }`}
                    >
                      {session.mode}
                    </span>
                    <span
                      className={`rounded px-2 py-0.5 font-mono text-[11px] font-medium capitalize ${
                        session.status === "active"
                          ? "bg-amber-400/15 text-amber-300"
                          : "bg-white/5 text-[var(--text-faint)]"
                      }`}
                    >
                      {session.status}
                    </span>
                  </div>
                </div>
                <span className="shrink-0 font-mono text-sm text-[var(--text-faint)]">
                  View →
                </span>
              </div>
            </Link>
          ))}
        </div>
      </main>
    </div>
  );
}
