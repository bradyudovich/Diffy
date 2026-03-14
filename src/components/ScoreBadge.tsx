/**
 * ScoreBadge.tsx – Displays a letter grade (A/B/C/D/F) inside a coloured circle.
 *
 * Grade colour mapping:
 *   A → green   (score ≥ 90)
 *   B → teal    (score ≥ 80)
 *   C → yellow  (score ≥ 70)
 *   D → orange  (score ≥ 50)
 *   F → red     (score < 50)
 */

interface Props {
  /** Letter grade string: "A", "B", "C", "D", or "F". */
  grade: string;
  /** Optional size variant. Defaults to "md". */
  size?: "sm" | "md" | "lg";
}

function gradeStyles(grade: string): { bg: string; text: string; ring: string } {
  switch (grade) {
    case "A": return { bg: "bg-green-500",  text: "text-white", ring: "ring-green-600" };
    case "B": return { bg: "bg-teal-500",   text: "text-white", ring: "ring-teal-600" };
    case "C": return { bg: "bg-yellow-400", text: "text-gray-900", ring: "ring-yellow-500" };
    case "D": return { bg: "bg-orange-500", text: "text-white", ring: "ring-orange-600" };
    default:  return { bg: "bg-red-600",    text: "text-white", ring: "ring-red-700" };
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
  if (score >= 80) return "B";
  if (score >= 70) return "C";
  if (score >= 50) return "D";
  return "F";
}
