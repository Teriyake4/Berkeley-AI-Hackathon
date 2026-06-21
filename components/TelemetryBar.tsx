type Phase = "idle" | "scene" | "en_route" | "hospital";

const STAGES: { key: Exclude<Phase, "idle">; label: string }[] = [
  { key: "scene", label: "Scene" },
  { key: "en_route", label: "En route" },
  { key: "hospital", label: "Hospital" },
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
    <div className="flex items-center gap-3">
      <span className="panel-label hidden shrink-0 sm:block">Telemetry</span>
      <div className="flex w-full items-center">
        {STAGES.map((stage, i) => {
          const isComplete = i < current;
          const isActive = i === current;
          const isDone = isComplete || isActive;
          const connectorActive = i < current;

          return (
            <div key={stage.key} className="flex flex-1 items-center last:flex-none">
              {i > 0 && (
                <div
                  className={`mx-1.5 h-px flex-1 rounded transition-colors ${
                    connectorActive ? "bg-vitals-400/60" : "bg-[var(--line-strong)]"
                  }`}
                />
              )}
              <div className="flex items-center gap-1.5">
                <span
                  className={`flex h-5 w-5 items-center justify-center rounded-full font-mono text-[10px] font-semibold transition-colors ${
                    isActive
                      ? "bg-clinical-400 text-ink-950 ring-2 ring-clinical-400/30"
                      : isComplete
                        ? "bg-vitals-400 text-ink-950"
                        : "bg-ink-700 text-[var(--text-faint)]"
                  }`}
                  aria-hidden
                >
                  {isComplete ? "✓" : isActive ? "●" : i + 1}
                </span>
                <span
                  className={`whitespace-nowrap text-xs transition-colors ${
                    isDone
                      ? "font-semibold text-[var(--text)]"
                      : "text-[var(--text-faint)]"
                  }`}
                >
                  {stage.label}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
