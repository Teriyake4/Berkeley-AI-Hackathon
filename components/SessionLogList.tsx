"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
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
    <div className="min-h-screen flex flex-col bg-slate-50">
      <header className="bg-ambulance-900 text-white px-6 py-4 flex items-center justify-between shadow-md">
        <div className="flex items-center gap-3">
          <span className="text-2xl" aria-hidden>
            🚑
          </span>
          <div>
            <h1 className="text-xl font-bold tracking-tight">Session Log</h1>
            <p className="text-ambulance-200 text-xs">Past encounters sorted by start time</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Link
            href="/"
            className="px-4 py-2 text-sm font-semibold rounded-lg bg-ambulance-500 text-white hover:bg-ambulance-400 transition-colors shadow-md"
          >
            New Session
          </Link>
          <Link
            href="/"
            className="px-3 py-2 text-sm font-medium rounded-lg bg-ambulance-800 text-ambulance-100 hover:bg-ambulance-700 border border-ambulance-700 transition-colors"
          >
            Live Dashboard
          </Link>
        </div>
      </header>

      <main className="flex-1 max-w-3xl w-full mx-auto p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide">
            Sessions
          </h2>
          <button
            type="button"
            onClick={loadSessions}
            className="text-sm text-ambulance-600 hover:text-ambulance-800 font-medium"
          >
            Refresh
          </button>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          {loading && (
            <p className="text-sm text-slate-400 italic p-6">Loading sessions…</p>
          )}
          {!loading && sessions.length === 0 && (
            <div className="p-8 text-center">
              <p className="text-slate-500 mb-4">No sessions recorded yet.</p>
              <Link
                href="/"
                className="inline-block px-4 py-2 text-sm font-semibold rounded-lg bg-ambulance-600 text-white hover:bg-ambulance-700"
              >
                Start New Session
              </Link>
            </div>
          )}
          {sessions.map((session) => (
            <Link
              key={session.encounterId}
              href={`/logs/${session.encounterId}`}
              className="block px-5 py-4 border-b border-slate-100 last:border-b-0 hover:bg-ambulance-50 transition-colors"
            >
              <div className="flex items-center justify-between gap-4">
                <div>
                  <div className="text-base font-medium text-slate-900">
                    {session.startedAt
                      ? formatStartTime(session.startedAt)
                      : "Unknown start time"}
                  </div>
                  <div className="flex items-center gap-2 mt-1.5">
                    <span
                      className={`text-xs px-2 py-0.5 rounded capitalize font-medium ${
                        session.mode === "demo"
                          ? "bg-blue-100 text-blue-800"
                          : session.mode === "live"
                            ? "bg-emerald-100 text-emerald-800"
                            : "bg-slate-100 text-slate-600"
                      }`}
                    >
                      {session.mode}
                    </span>
                    <span
                      className={`text-xs px-2 py-0.5 rounded capitalize font-medium ${
                        session.status === "active"
                          ? "bg-amber-100 text-amber-800"
                          : "bg-slate-100 text-slate-600"
                      }`}
                    >
                      {session.status}
                    </span>
                  </div>
                </div>
                <span className="text-slate-400 text-sm shrink-0">View →</span>
              </div>
            </Link>
          ))}
        </div>
      </main>
    </div>
  );
}
