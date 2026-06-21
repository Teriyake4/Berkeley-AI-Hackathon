type Phase = "idle" | "scene" | "en_route" | "hospital";

const STAGES: { key: Exclude<Phase, "idle">; label: string; icon: string }[] = [
  { key: "scene", label: "Scene", icon: "📍" },
  { key: "en_route", label: "En route", icon: "🚑" },
  { key: "hospital", label: "Hospital", icon: "🏥" },
];

// Order index of each phase; "idle" is -1 so nothing is highlighted.
const PHASE_ORDER: Record<Phase, number> = {
  idle: -1,
  scene: 0,
  en_route: 1,
  hospital: 2,
};

export function TelemetryBar({ phase }: { phase: Phase }) {
  const current = PHASE_ORDER[phase] ?? -1;

  return (
    <div className="flex items-center w-full">
      {STAGES.map((stage, i) => {
        const isComplete = i < current;
        const isActive = i === current;
        const isDone = isComplete || isActive; // highlighted up to and including current
        const connectorActive = i < current; // line leading into stage i is "done"

        return (
          <div key={stage.key} className="flex items-center flex-1 last:flex-none">
            {/* Connector before this stage (skip before first) */}
            {i > 0 && (
              <div
                className={`h-0.5 flex-1 mx-1 rounded transition-colors ${
                  connectorActive ? "bg-emerald-500" : "bg-slate-200"
                }`}
              />
            )}
            <div className="flex items-center gap-1.5">
              <span
                className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold transition-colors ${
                  isActive
                    ? "bg-emerald-500 text-white ring-2 ring-emerald-200"
                    : isComplete
                      ? "bg-emerald-500 text-white"
                      : "bg-slate-200 text-slate-400"
                }`}
                aria-hidden
              >
                {isComplete ? "✓" : isActive ? "●" : i + 1}
              </span>
              <span
                className={`flex items-center gap-1 text-xs whitespace-nowrap transition-colors ${
                  isDone ? "font-semibold text-slate-800" : "text-slate-400"
                }`}
              >
                <span aria-hidden>{stage.icon}</span>
                {stage.label}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
