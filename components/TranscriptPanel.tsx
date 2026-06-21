import type { TranscriptLine } from "@/hooks/useEncounterEvents";
import { useEffect, useRef } from "react";

const speakerStyles: Record<string, string> = {
  paramedic: "bg-clinical-100 text-clinical-900",
  doctor: "bg-clinical-100 text-clinical-900",
  patient: "bg-slate-100 text-slate-800",
  bystander: "bg-violet-100 text-violet-800",
  console: "bg-emerald-100 text-emerald-800",
  unknown: "bg-gray-100 text-gray-700",
};

export function TranscriptPanel({ lines }: { lines: TranscriptLine[] }) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [lines.length]);

  return (
    <div className="flex flex-col h-full">
      <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-3">
        Live Transcript
      </h2>
      <div className="flex-1 overflow-y-auto space-y-2 pr-1">
        {lines.length === 0 && (
          <p className="text-slate-400 text-sm italic">Waiting for conversation…</p>
        )}
        {lines.map((line, i) => {
          const isConsole = line.speaker === "console";
          return (
            <div
              key={i}
              className={`animate-fade-in text-sm ${
                isConsole ? "italic text-emerald-700" : ""
              }`}
            >
              <span
                className={`inline-block text-xs font-medium px-2 py-0.5 rounded-full mr-2 capitalize ${
                  speakerStyles[line.speaker] ?? speakerStyles.unknown
                }`}
              >
                {isConsole ? "📷 Console" : line.speaker}
              </span>
              <span className={isConsole ? "text-emerald-700" : "text-slate-800"}>
                {line.text}
              </span>
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
