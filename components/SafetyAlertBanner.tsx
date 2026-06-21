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
      className="mx-4 mt-3 rounded-xl border-2 border-red-500 bg-red-600 text-white shadow-lg animate-fade-in"
    >
      <div className="px-4 py-3 flex items-start gap-3">
        <span className="text-2xl shrink-0 animate-pulse" aria-hidden>
          🚨
        </span>
        <div className="flex-1 min-w-0">
          <p className="font-bold text-sm uppercase tracking-wide text-red-100">
            Safety Alert — Action Required
          </p>
          {primaryFlag ? (
            <>
              <p className="font-semibold text-base mt-0.5 leading-snug">
                {primaryFlag.concern}
              </p>
              <p className="text-sm text-red-100 mt-1 leading-relaxed">
                {primaryFlag.rationale}
              </p>
            </>
          ) : (
            <p className="font-semibold text-base mt-0.5">
              Documented allergies: {allergies.join(", ")} — verify all treatments before
              administration
            </p>
          )}
          {criticalFlags.length > 1 && (
            <p className="text-xs text-red-200 mt-2 font-medium">
              +{criticalFlags.length - 1} additional critical flag
              {criticalFlags.length - 1 !== 1 ? "s" : ""} — see AI Insights panel
            </p>
          )}
        </div>
        {allergies.length > 0 && (
          <div className="shrink-0 flex flex-col gap-1 items-end">
            {allergies.map((a) => (
              <span
                key={a}
                className="text-xs font-bold uppercase px-2 py-1 rounded bg-white text-red-700 border border-red-300"
              >
                ⚠ {a}
              </span>
            ))}
          </div>
        )}
        {allergies.length === 0 && activeMeds.length > 0 && criticalFlags.length > 0 && (
          <div className="shrink-0 flex flex-col gap-1 items-end">
            {activeMeds.slice(0, 3).map((m) => (
              <span
                key={m.name}
                className="text-xs font-bold uppercase px-2 py-1 rounded bg-white text-red-700 border border-red-300"
              >
                💊 {m.name}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
