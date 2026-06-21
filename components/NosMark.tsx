/**
 * Nos brand mark — a heartbeat trace breaking through a medical cross,
 * in emergency-signal red. Used in headers and the homepage hero.
 */
export function NosMark({
  size = 28,
  className = "",
}: {
  size?: number;
  className?: string;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 40 40"
      fill="none"
      className={className}
      aria-hidden
    >
      <rect
        x="1.25"
        y="1.25"
        width="37.5"
        height="37.5"
        rx="11"
        fill="#0d1320"
        stroke="url(#nos-edge)"
        strokeWidth="1.5"
      />
      {/* faint medical cross */}
      <path
        d="M20 9.5v21M9.5 20h21"
        stroke="rgba(255,255,255,0.10)"
        strokeWidth="3.5"
        strokeLinecap="round"
      />
      {/* heartbeat trace */}
      <path
        d="M6 21.5h6l2.5-7 4 13 3.5-9 2 3h6.5"
        stroke="#ff4536"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <defs>
        <linearGradient id="nos-edge" x1="0" y1="0" x2="40" y2="40">
          <stop stopColor="#ff6452" stopOpacity="0.7" />
          <stop offset="1" stopColor="#22d4ec" stopOpacity="0.5" />
        </linearGradient>
      </defs>
    </svg>
  );
}
