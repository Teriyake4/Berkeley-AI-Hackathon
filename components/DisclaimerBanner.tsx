export function DisclaimerBanner() {
  return (
    <div className="flex items-center justify-center gap-2 border-b border-amber-400/20 bg-amber-400/[0.07] px-4 py-1.5 text-center font-mono text-[11px] tracking-wide text-amber-300/90">
      <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
      <span>
        <strong className="font-semibold text-amber-200">DEMO ONLY</strong> — not for
        clinical use. This tool does not provide medical advice.
      </span>
    </div>
  );
}
