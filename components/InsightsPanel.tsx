import type { SafetyFlaggedPayload } from "@/lib/events";
import type { Citation } from "@/lib/events";

const severityConfig = {
  high: {
    card: "border-red-300 bg-red-50",
    label: "bg-red-500 text-white",
    text: "text-red-900",
    subtext: "text-red-700",
    icon: "🚨",
  },
  medium: {
    card: "border-amber-300 bg-amber-50",
    label: "bg-amber-500 text-white",
    text: "text-amber-900",
    subtext: "text-amber-700",
    icon: "⚠️",
  },
  low: {
    card: "border-blue-200 bg-blue-50",
    label: "bg-blue-500 text-white",
    text: "text-blue-900",
    subtext: "text-blue-700",
    icon: "ℹ️",
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
  const sortedFlags = [...safetyFlags].sort((a, b) => {
    const order = { high: 0, medium: 1, low: 2 };
    return order[a.severity] - order[b.severity];
  });

  return (
    <div className="flex flex-col h-full">
      <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-3">
        AI Insights
      </h2>
      <div className="flex-1 overflow-y-auto space-y-4 pr-0.5">

        {/* Safety Flags */}
        <section>
          <h3 className="text-xs font-semibold text-slate-500 uppercase mb-2 flex items-center gap-1.5">
            Safety Flags
            {safetyFlags.length > 0 && (
              <span className="bg-red-500 text-white text-xs rounded-full px-1.5 py-0.5 font-bold leading-none">
                {safetyFlags.length}
              </span>
            )}
          </h3>
          {sortedFlags.length === 0 ? (
            <p className="text-sm text-slate-400 italic">No concerns flagged yet</p>
          ) : (
            sortedFlags.map((flag, i) => {
              const cfg = severityConfig[flag.severity];
              return (
                <div
                  key={i}
                  className={`rounded-lg border p-3 mb-2 animate-fade-in ${cfg.card}`}
                >
                  <div className="flex items-start gap-2">
                    <span className="text-sm">{cfg.icon}</span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span
                          className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded ${cfg.label}`}
                        >
                          {flag.severity}
                        </span>
                      </div>
                      <p className={`text-sm font-semibold leading-snug ${cfg.text}`}>
                        {flag.concern}
                      </p>
                      <p className={`text-xs mt-1 leading-relaxed ${cfg.subtext}`}>
                        {flag.rationale}
                      </p>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </section>

        {/* Missing Information */}
        {missingInfo.length > 0 && (
          <section>
            <h3 className="text-xs font-semibold text-slate-500 uppercase mb-2">
              Missing Information
            </h3>
            <ul className="space-y-1.5">
              {missingInfo.map((item) => (
                <li key={item} className="flex items-center gap-2 text-sm text-slate-600">
                  <span className="h-2 w-2 rounded-full bg-amber-400 shrink-0" />
                  {item}
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* Suggested Follow-Up Questions */}
        {suggestedFollowUps.length > 0 && (
          <section>
            <h3 className="text-xs font-semibold text-slate-500 uppercase mb-2">
              Suggested Questions
            </h3>
            <ul className="space-y-1.5">
              {suggestedFollowUps.map((q) => (
                <li
                  key={q}
                  className="flex items-start gap-2 text-sm text-slate-700 bg-slate-50 rounded-lg px-3 py-2 border border-slate-200 animate-fade-in"
                >
                  <span className="text-clinical-500 mt-0.5 shrink-0">?</span>
                  {q}
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* Research Citations */}
        <section>
          <h3 className="text-xs font-semibold text-slate-500 uppercase mb-2 flex items-center gap-1.5">
            Research
            {research.length > 0 && (
              <span className="bg-clinical-500 text-white text-xs rounded-full px-1.5 py-0.5 font-bold leading-none">
                {research.length}
              </span>
            )}
          </h3>
          {research.length === 0 ? (
            <p className="text-sm text-slate-400 italic">Research agent idle</p>
          ) : (
            research.map((r, i) => (
              <div
                key={i}
                className="mb-4 pb-4 border-b border-slate-100 last:border-0 last:pb-0 last:mb-0 animate-fade-in"
              >
                <p className="text-xs font-semibold text-clinical-700 mb-1 uppercase tracking-wide">
                  {r.query}
                </p>
                <p className="text-sm text-slate-700 leading-relaxed mb-2">{r.findings}</p>
                <div className="space-y-1">
                  {r.citations.map((c, j) => (
                    <a
                      key={j}
                      href={c.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-start gap-1.5 group"
                    >
                      <span className="text-clinical-400 mt-0.5 shrink-0 text-xs">↗</span>
                      <span className="text-xs text-clinical-600 group-hover:underline leading-snug">
                        {c.title}
                      </span>
                    </a>
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
