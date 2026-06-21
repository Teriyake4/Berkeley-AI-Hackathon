import type { TranscriptLine } from "@/types/session";

const speakerStyles: Record<string, string> = {
  paramedic: "bg-clinical-400/15 text-clinical-200 border-clinical-400/25",
  doctor: "bg-clinical-400/15 text-clinical-200 border-clinical-400/25",
  patient: "bg-white/[0.06] text-[var(--text-muted)] border-[var(--line-strong)]",
  bystander: "bg-violet-400/12 text-violet-200 border-violet-400/25",
  console: "bg-vitals-400/12 text-vitals-400 border-vitals-400/25",
  unknown: "bg-white/5 text-[var(--text-faint)] border-[var(--line)]",
};

export function TranscriptPanel({ lines }: { lines: TranscriptLine[] }) {
  return (
    <div className="flex h-full flex-col">
      <h2 className="panel-label mb-3">Live Transcript</h2>
      <div className="flex-1 space-y-2.5 overflow-y-auto pr-1">
        {lines.length === 0 && (
          <p className="font-mono text-sm text-[var(--text-faint)]">
            Waiting for conversation…
          </p>
        )}
        {lines.map((line, i) => {
          const isConsole = line.speaker === "console";
          return (
            <div
              key={i}
              className={`animate-fade-in text-sm leading-relaxed ${
                isConsole ? "italic" : ""
              }`}
            >
              <span
                className={`mr-2 inline-block rounded-full border px-2 py-0.5 text-[11px] font-medium capitalize ${
                  speakerStyles[line.speaker] ?? speakerStyles.unknown
                }`}
              >
                {isConsole ? "Console" : line.speaker}
              </span>
              <span className={isConsole ? "text-vitals-400" : "text-[var(--text)]"}>
                {line.text}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
