import type { Verdict } from "../types";

interface Props {
  verdict: Verdict;
}

const VERDICT_STYLES: Record<Verdict, { bg: string; text: string; border: string; icon: string }> = {
  Caution: { bg: "bg-red-100", text: "text-red-800", border: "border-red-300", icon: "⚠️" },
  Neutral: { bg: "bg-blue-100", text: "text-blue-700", border: "border-blue-300", icon: "📋" },
  Good:    { bg: "bg-green-100", text: "text-green-800", border: "border-green-300", icon: "✅" },
};

export default function VerdictBadge({ verdict }: Props) {
  const styles = VERDICT_STYLES[verdict] ?? VERDICT_STYLES.Good;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${styles.bg} ${styles.text} ${styles.border}`}
    >
      <span aria-hidden="true">{styles.icon}</span>
      {verdict}
    </span>
  );
}
