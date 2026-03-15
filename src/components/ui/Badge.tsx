/**
 * Badge.tsx – Reusable badge / chip primitive.
 *
 * Intents:
 *   positive – emerald (good clause, A/B grade indicators)
 *   negative – rose    (bad clause, E grade indicators)
 *   neutral  – sky     (informational)
 *   warning  – amber   (watchlist flags, caution notices)
 *   grade    – maps to the A-E grade colour scale via the `grade` prop
 *   default  – gray    (generic tag)
 *
 * Usage:
 *   <Badge intent="positive">Positive</Badge>
 *   <Badge intent="grade" grade="A">A</Badge>
 */

import type { ReactNode } from "react";

type Intent = "positive" | "negative" | "neutral" | "warning" | "grade" | "default";

interface Props {
  /** Semantic colour intent. Defaults to "default". */
  intent?: Intent;
  /**
   * Required when intent="grade". Letter grade string: "A" | "B" | "C" | "D" | "E".
   * Ignored for all other intents.
   */
  grade?: string;
  children: ReactNode;
  className?: string;
}

const INTENT_CLASSES: Record<Exclude<Intent, "grade">, string> = {
  positive: "bg-emerald-100 text-emerald-800 border-emerald-200",
  negative: "bg-rose-100 text-rose-800 border-rose-200",
  neutral:  "bg-sky-100 text-sky-800 border-sky-200",
  warning:  "bg-amber-100 text-amber-800 border-amber-300",
  default:  "bg-gray-100 text-gray-600 border-gray-200",
};

function gradeClasses(grade = ""): string {
  switch (grade) {
    case "A": return "bg-emerald-100 text-emerald-800 border-emerald-300";
    case "B": return "bg-teal-100 text-teal-800 border-teal-300";
    case "C": return "bg-amber-100 text-amber-800 border-amber-300";
    case "D": return "bg-orange-100 text-orange-800 border-orange-300";
    default:  return "bg-rose-100 text-rose-800 border-rose-300";
  }
}

export default function Badge({
  intent = "default",
  grade,
  children,
  className = "",
}: Props) {
  const colorClasses =
    intent === "grade" ? gradeClasses(grade) : INTENT_CLASSES[intent];

  return (
    <span
      className={[
        "inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium",
        colorClasses,
        className,
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {children}
    </span>
  );
}
