/**
 * ScoreGauge.tsx – Visual Red→Yellow→Green gauge for trust scores (0–100).
 */

interface Props {
  /** Trust score between 0 and 100 (inclusive). */
  score: number;
  /** Optional size variant. Defaults to "md". */
  size?: "sm" | "md" | "lg";
}

function scoreColor(score: number): { fg: string; bg: string; label: string } {
  if (score >= 70) return { fg: "text-green-700", bg: "bg-green-500", label: "Good" };
  if (score >= 40) return { fg: "text-yellow-700", bg: "bg-yellow-400", label: "Fair" };
  return { fg: "text-red-700", bg: "bg-red-500", label: "Poor" };
}

const SIZE_MAP = {
  sm: { outer: "w-12 h-12", text: "text-xs", sub: "text-[9px]" },
  md: { outer: "w-16 h-16", text: "text-sm", sub: "text-[10px]" },
  lg: { outer: "w-20 h-20", text: "text-base", sub: "text-xs" },
};

export default function ScoreGauge({ score, size = "md" }: Props) {
  const clamped = Math.max(0, Math.min(100, Math.round(score)));
  const { fg, bg, label } = scoreColor(clamped);
  const dims = SIZE_MAP[size];

  // Arc parameters (SVG semi-circle gauge)
  const radius = 36;
  const circumference = Math.PI * radius; // half-circle arc length
  const filled = (clamped / 100) * circumference;
  const gap = circumference - filled;

  // Gradient stop colours (red → yellow → green)
  const gradientId = `gauge-grad-${clamped}`;

  return (
    <div
      className={`relative flex flex-col items-center justify-center ${dims.outer}`}
      title={`Trust Score: ${clamped}/100 – ${label}`}
      aria-label={`Trust score ${clamped} out of 100`}
    >
      <svg viewBox="0 0 80 48" className="w-full h-full" aria-hidden="true">
        <defs>
          <linearGradient id={gradientId} x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#ef4444" />
            <stop offset="50%" stopColor="#facc15" />
            <stop offset="100%" stopColor="#22c55e" />
          </linearGradient>
        </defs>

        {/* Track (grey background arc) */}
        <path
          d="M 4 44 A 36 36 0 0 1 76 44"
          fill="none"
          stroke="#e5e7eb"
          strokeWidth="8"
          strokeLinecap="round"
        />

        {/* Filled arc */}
        <path
          d="M 4 44 A 36 36 0 0 1 76 44"
          fill="none"
          stroke={`url(#${gradientId})`}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={`${filled} ${gap}`}
        />

        {/* Score text */}
        <text
          x="40"
          y="38"
          textAnchor="middle"
          dominantBaseline="auto"
          className={`font-bold fill-current ${fg}`}
          style={{ fontSize: size === "sm" ? 12 : size === "lg" ? 16 : 14 }}
        >
          {clamped}
        </text>
      </svg>

      {/* Label below SVG */}
      <span
        className={`-mt-1 font-semibold leading-none ${dims.sub} ${fg}`}
      >
        {label}
      </span>

      {/* Coloured dot indicator */}
      <span
        className={`absolute top-0 right-0 h-2 w-2 rounded-full ${bg}`}
        aria-hidden="true"
      />
    </div>
  );
}
