import type { SoapNote } from "@/types/events";

const sections: Array<{ key: keyof SoapNote; label: string; tag: string }> = [
  { key: "subjective", label: "Subjective", tag: "S" },
  { key: "objective", label: "Objective", tag: "O" },
  { key: "assessment", label: "Assessment", tag: "A" },
  { key: "plan", label: "Plan", tag: "P" },
];

export function SoapPanel({ soap }: { soap: SoapNote | null }) {
  return (
    <div>
      <h2 className="panel-label mb-3">Live PCR · SOAP Note</h2>
      {!soap ? (
        <p className="font-mono text-sm text-[var(--text-faint)]">
          Documentation agent will populate this patient care report…
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {sections.map(({ key, label, tag }) => (
            <div
              key={key}
              className="animate-fade-in rounded-xl border border-[var(--line)] bg-ink-900/50 p-3.5"
            >
              <h3 className="mb-1.5 flex items-center gap-2">
                <span className="flex h-5 w-5 items-center justify-center rounded-md bg-clinical-400/15 font-mono text-xs font-bold text-clinical-300">
                  {tag}
                </span>
                <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-[var(--text-muted)]">
                  {label}
                </span>
              </h3>
              <p className="text-sm leading-relaxed text-[var(--text)]">
                {soap[key] || "—"}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
