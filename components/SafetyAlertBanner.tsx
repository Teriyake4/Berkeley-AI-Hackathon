import type { MedicalEntities, SafetyFlaggedPayload } from "@/types/events";

export function SafetyAlertBanner({
  safetyFlags,
  entities,
}: {
  safetyFlags: SafetyFlaggedPayload[];
  entities: MedicalEntities | null;
}) {
  const alertFlags = safetyFlags.filter(
    (f) => f.severity === "high" || f.severity === "critical"
  );
  const criticalFlags = alertFlags.filter(
    (f) =>
      f.severity === "critical" ||
      f.concern.includes("ALLERGY") ||
      f.concern.includes("CRITICAL") ||
      f.concern.includes("conflict") ||
      f.concern.includes("Warfarin") ||
      f.concern.includes("bleeding") ||
      f.concern.includes("limb injury") ||
      f.concern.includes("manipulation")
  );
  const allergies = entities?.allergies ?? [];
  const activeMeds = entities?.medications ?? [];

  if (criticalFlags.length === 0 && allergies.length === 0) {
    return null;
  }

  const primaryFlag = criticalFlags[0];

  return (
    <div
      role="alert"
      className="animate-fade-in mx-4 mt-3 overflow-hidden rounded-2xl border border-signal-500/50 bg-gradient-to-r from-signal-600/25 via-signal-500/15 to-ink-850 shadow-glow"
    >
      <div className="flex items-start gap-3 px-4 py-3">
        <span className="relative mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-signal-500 text-base font-black text-white">
          !
          <span className="absolute inset-0 animate-glow-pulse rounded-lg" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="font-mono text-[11px] font-semibold uppercase tracking-[0.18em] text-signal-300">
            Safety Alert — Action Required
          </p>
          {primaryFlag ? (
            <>
              <p className="mt-0.5 text-base font-semibold leading-snug text-white">
                {primaryFlag.concern}
              </p>
              <p className="mt-1 text-sm leading-relaxed text-signal-100/85">
                {primaryFlag.rationale}
              </p>
            </>
          ) : (
            <p className="mt-0.5 text-base font-semibold text-white">
              Documented allergies: {allergies.join(", ")} — verify all treatments before
              administration
            </p>
          )}
          {criticalFlags.length > 1 && (
            <p className="mt-2 font-mono text-[11px] font-medium text-signal-200/80">
              +{criticalFlags.length - 1} additional critical flag
              {criticalFlags.length - 1 !== 1 ? "s" : ""} — see AI Insights panel
            </p>
          )}
        </div>
        {allergies.length > 0 && (
          <div className="flex shrink-0 flex-col items-end gap-1">
            {allergies.map((a) => (
              <span
                key={a}
                className="rounded-md bg-white px-2 py-1 text-[11px] font-bold uppercase tracking-wide text-signal-700"
              >
                {a} allergy
              </span>
            ))}
          </div>
        )}
        {allergies.length === 0 && activeMeds.length > 0 && criticalFlags.length > 0 && (
          <div className="flex shrink-0 flex-col items-end gap-1">
            {activeMeds.slice(0, 3).map((m) => (
              <span
                key={m.name}
                className="rounded-md bg-white px-2 py-1 text-[11px] font-bold uppercase text-signal-700"
              >
                {m.name}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
