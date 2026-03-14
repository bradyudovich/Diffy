/**
 * ScoreBadge.tsx – Displays a letter grade (A/B/C/D/E) inside a coloured circle.
 *
 * Grade colour mapping (soft, neutral palette):
 *   A → emerald  (score ≥ 90)
 *   B → teal     (score ≥ 70)
 *   C → amber    (score ≥ 50)
 *   D → orange   (score ≥ 30)
 *   E → rose     (score < 30)
 */

interface Props {
  /** Letter grade string: "A", "B", "C", "D", or "E". */
  grade: string;
  /** Optional size variant. Defaults to "md". */
  size?: "sm" | "md" | "lg";
}

function gradeStyles(grade: string): { bg: string; text: string; ring: string } {
  switch (grade) {
    case "A": return { bg: "bg-emerald-100", text: "text-emerald-800", ring: "ring-emerald-300" };
    case "B": return { bg: "bg-teal-100",    text: "text-teal-800",    ring: "ring-teal-300" };
    case "C": return { bg: "bg-amber-100",   text: "text-amber-800",   ring: "ring-amber-300" };
    case "D": return { bg: "bg-orange-100",  text: "text-orange-800",  ring: "ring-orange-300" };
    default:  return { bg: "bg-rose-100",    text: "text-rose-800",    ring: "ring-rose-300" };
  }
}

const SIZE_MAP = {
  sm: { circle: "h-9 w-9",  font: "text-base font-black" },
  md: { circle: "h-12 w-12", font: "text-xl font-black" },
  lg: { circle: "h-16 w-16", font: "text-3xl font-black" },
};

export default function ScoreBadge({ grade, size = "md" }: Props) {
  const { bg, text, ring } = gradeStyles(grade);
  const dims = SIZE_MAP[size];

  return (
    <span
      className={`inline-flex items-center justify-center rounded-full ring-2 ${bg} ${text} ${ring} ${dims.circle}`}
      title={`Trust Grade: ${grade}`}
      aria-label={`Trust grade ${grade}`}
    >
      <span className={dims.font}>{grade}</span>
    </span>
  );
}

/** Derive a letter grade from a numeric trust score (0–100).
 *  Thresholds mirror `get_letter_grade()` in scraper/monitor.py.
 */
export function scoreToGrade(score: number): string {
  if (score >= 90) return "A";
  if (score >= 70) return "B";
  if (score >= 50) return "C";
  if (score >= 30) return "D";
  return "E";
}

