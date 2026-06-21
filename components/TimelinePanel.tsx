import type { TimelineEntry } from "@/types/events";

const sourceStyles: Record<string, string> = {
  extraction: "bg-clinical-500 ring-clinical-100",
  safety: "bg-red-500 ring-red-200",
  telemetry: "bg-indigo-500 ring-indigo-100",
  audio: "bg-purple-500 ring-purple-100",
  vision: "bg-emerald-500 ring-emerald-100",
  manual: "bg-slate-400 ring-slate-100",
};

const sourceIcons: Record<string, string> = {
  extraction: "🩺",
  safety: "🚨",
  telemetry: "📍",
  audio: "🔊",
  vision: "📷",
  manual: "✎",
};

export function TimelinePanel({ events }: { events: TimelineEntry[] }) {
  const sorted = [...events].sort((a, b) => a.timestamp.localeCompare(b.timestamp));

  return (
    <div className="flex flex-col h-full">
      <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-3 flex items-center gap-2">
        Encounter Timeline
        {events.length > 0 && (
          <span className="ml-auto text-xs font-normal text-slate-400 normal-case">
            {events.length} event{events.length !== 1 ? "s" : ""}
          </span>
        )}
      </h2>
      <div className="flex-1 overflow-y-auto">
        {sorted.length === 0 ? (
          <p className="text-slate-400 text-sm italic">Timeline builds as agents extract facts…</p>
        ) : (
          <ol className="relative border-l-2 border-clinical-100 ml-2 space-y-4">
            {sorted.map((event) => {
              const src = (event.source as string) ?? "extraction";
              const dot = sourceStyles[src] ?? sourceStyles.extraction;
              const icon = sourceIcons[src] ?? sourceIcons.extraction;
              const isSafety = src === "safety";
              return (
                <li key={event.id} className="ml-5 animate-fade-in">
                  <span
                    className={`absolute -left-2 mt-0.5 h-4 w-4 rounded-full ring-4 ring-white ${dot}`}
                  />
                  <time className="text-xs text-slate-400 font-mono">
                    {new Date(event.timestamp).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </time>
                  <p
                    className={`text-sm mt-0.5 leading-snug flex items-start gap-1.5 ${
                      isSafety ? "text-red-700 font-semibold" : "text-slate-800"
                    }`}
                  >
                    <span className="shrink-0 leading-snug" aria-hidden>
                      {icon}
                    </span>
                    <span>{isSafety ? event.summary : event.summary.replace(/^⚠\s*/, "")}</span>
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
