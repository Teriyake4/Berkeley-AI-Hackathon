import type { TimelineEntry } from "@/types/events";

const sourceStyles: Record<string, string> = {
  extraction: "bg-clinical-400",
  safety: "bg-signal-500",
  telemetry: "bg-indigo-400",
  audio: "bg-violet-400",
  vision: "bg-vitals-400",
  manual: "bg-slate-400",
};

const sourceLabels: Record<string, string> = {
  extraction: "extract",
  safety: "safety",
  telemetry: "gps",
  audio: "audio",
  vision: "vision",
  manual: "note",
};

export function TimelinePanel({ events }: { events: TimelineEntry[] }) {
  const sorted = [...events].sort((a, b) => a.timestamp.localeCompare(b.timestamp));

  return (
    <div className="flex h-full flex-col">
      <h2 className="panel-label mb-3 flex items-center gap-2">
        Encounter Timeline
        {events.length > 0 && (
          <span className="ml-auto font-mono text-[11px] normal-case tracking-normal text-[var(--text-faint)]">
            {events.length} event{events.length !== 1 ? "s" : ""}
          </span>
        )}
      </h2>
      <div className="flex-1 overflow-y-auto">
        {sorted.length === 0 ? (
          <p className="font-mono text-sm text-[var(--text-faint)]">
            Timeline builds as agents extract facts…
          </p>
        ) : (
          <ol className="relative ml-2 space-y-4 border-l border-[var(--line-strong)]">
            {sorted.map((event) => {
              const src = (event.source as string) ?? "extraction";
              const dot = sourceStyles[src] ?? sourceStyles.extraction;
              const tag = sourceLabels[src] ?? "extract";
              const isSafety = src === "safety";
              const isDangerous =
                isSafety ||
                /\ballerg(y|ic)\b|despite.*allerg|critical|do not administer|bleeding risk|drug interaction/i.test(
                  event.summary
                );
              return (
                <li key={event.id} className="animate-fade-in ml-5">
                  <span
                    className={`absolute -left-[5px] mt-1 h-2.5 w-2.5 rounded-full ring-4 ring-ink-850 ${
                      isDangerous ? sourceStyles.safety : dot
                    } ${isDangerous ? "shadow-[0_0_8px_1px_rgba(255,69,54,0.7)]" : ""}`}
                  />
                  <div className="flex items-center gap-2">
                    <time className="font-mono text-[11px] text-[var(--text-faint)]">
                      {new Date(event.timestamp).toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </time>
                    <span className="font-mono text-[9px] uppercase tracking-widest text-[var(--text-faint)]">
                      {tag}
                    </span>
                  </div>
                  <p
                    className={`mt-0.5 text-sm leading-snug ${
                      isDangerous
                        ? "font-semibold text-signal-200"
                        : "text-[var(--text)]"
                    }`}
                  >
                    {isSafety ? event.summary : event.summary.replace(/^⚠\s*/, "")}
                  </p>
                </li>
              );
            })}
          </ol>
        )}
      </div>
    </div>
  );
}
