import type { SoapNote } from "@/types/events";

const sections: Array<{ key: keyof SoapNote; label: string }> = [
  { key: "subjective", label: "S — Subjective" },
  { key: "objective", label: "O — Objective" },
  { key: "assessment", label: "A — Assessment" },
  { key: "plan", label: "P — Plan" },
];

export function SoapPanel({ soap }: { soap: SoapNote | null }) {
  return (
    <div>
      <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-3">
        Live SOAP Note
      </h2>
      {!soap ? (
        <p className="text-slate-400 text-sm italic">Documentation agent will populate this…</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {sections.map(({ key, label }) => (
            <div key={key} className="rounded-lg border border-slate-200 bg-white p-3 animate-fade-in">
              <h3 className="text-xs font-bold text-clinical-700 mb-1">{label}</h3>
              <p className="text-sm text-slate-700 leading-relaxed">{soap[key] || "—"}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
