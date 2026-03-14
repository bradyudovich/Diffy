/**
 * ServiceClassBadge.tsx – Displays a service class grade (A–E) in the style
 * of ToS;DR's iconic "Class" labels.
 *
 * Grade semantics:
 *   A (Very Good)  – score ≥ 90
 *   B (Good)       – score ≥ 70
 *   C (Fair)       – score ≥ 50
 *   D (Bad)        – score ≥ 30
 *   E (Very Bad)   – score < 30
 *
 * Uses soft, neutral palette so as not to alarm users unnecessarily.
 */

interface Props {
  /** Letter grade: "A", "B", "C", "D", or "E". */
  grade: string;
  /** Optional size variant. Defaults to "md". */
  size?: "sm" | "md" | "lg";
  /** Show the full class label (e.g. "Class A") instead of just the letter. */
  showLabel?: boolean;
}

interface GradeStyle {
  bg: string;
  text: string;
  border: string;
  label: string;
}

function gradeStyles(grade: string): GradeStyle {
  switch (grade) {
    case "A":
      return {
        bg: "bg-emerald-50",
        text: "text-emerald-700",
        border: "border-emerald-300",
        label: "Very Good",
      };
    case "B":
      return {
        bg: "bg-teal-50",
        text: "text-teal-700",
        border: "border-teal-300",
        label: "Good",
      };
    case "C":
      return {
        bg: "bg-amber-50",
        text: "text-amber-700",
        border: "border-amber-300",
        label: "Fair",
      };
    case "D":
      return {
        bg: "bg-orange-50",
        text: "text-orange-700",
        border: "border-orange-300",
        label: "Bad",
      };
    default: // "E"
      return {
        bg: "bg-rose-50",
        text: "text-rose-700",
        border: "border-rose-300",
        label: "Very Bad",
      };
  }
}

const SIZE_MAP = {
  sm: {
    outer: "h-10 w-10",
    letter: "text-lg font-bold",
    badge: "px-2 py-0.5 text-xs",
  },
  md: {
    outer: "h-14 w-14",
    letter: "text-2xl font-bold",
    badge: "px-2.5 py-1 text-sm",
  },
  lg: {
    outer: "h-20 w-20",
    letter: "text-4xl font-bold",
    badge: "px-3 py-1 text-base",
  },
};

/** Derive a letter grade from a numeric trust score (0–100).
 *  Thresholds mirror `get_letter_grade()` in scraper/monitor.py.
 */
export function scoreToClassGrade(score: number): string {
  if (score >= 90) return "A";
  if (score >= 70) return "B";
  if (score >= 50) return "C";
  if (score >= 30) return "D";
  return "E";
}

export default function ServiceClassBadge({
  grade,
  size = "md",
  showLabel = false,
}: Props) {
  const { bg, text, border, label } = gradeStyles(grade);
  const dims = SIZE_MAP[size];

  if (showLabel) {
    return (
      <span
        className={`inline-flex items-center gap-1.5 rounded-md border ${bg} ${text} ${border} ${dims.badge} font-semibold`}
        title={`Class ${grade} – ${label}`}
        aria-label={`Class ${grade}: ${label}`}
      >
        <span className="font-black">Class {grade}</span>
        <span className="font-normal opacity-75">·</span>
        <span className="font-normal">{label}</span>
      </span>
    );
  }

  return (
    <span
      className={`inline-flex flex-col items-center justify-center rounded-xl border-2 ${bg} ${text} ${border} ${dims.outer} select-none`}
      title={`Class ${grade} – ${label}`}
      aria-label={`Class ${grade}: ${label}`}
    >
      <span className={`leading-none ${dims.letter}`}>{grade}</span>
    </span>
  );
}
