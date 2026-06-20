import type { TimelineEntry } from "@/lib/events";

const sourceStyles: Record<string, string> = {
  safety: "bg-red-500 ring-red-200",
  extraction: "bg-clinical-500 ring-clinical-100",
  manual: "bg-slate-400 ring-slate-100",
};

export function TimelinePanel({ events }: { events: TimelineEntry[] }) {
  const sorted = [...events].sort((a, b) => a.timestamp.localeCompare(b.timestamp));

  return (
    <div className="flex flex-col h-full">
      <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-3 flex items-center gap-2">
        Patient Timeline
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
              const dot = sourceStyles[event.source ?? "extraction"] ?? sourceStyles.extraction;
              const isSafety = event.source === "safety";
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
                    className={`text-sm mt-0.5 leading-snug ${
                      isSafety
                        ? "text-red-700 font-semibold"
                        : "text-slate-800"
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
