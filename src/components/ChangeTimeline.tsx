import type { HistoryEntry } from "../types";

interface Props {
  companyName: string;
  history: HistoryEntry[];
  onSelectEntry: (entry: HistoryEntry) => void;
  selectedEntry: HistoryEntry | null;
}

const VERDICT_STYLES = {
  Caution: { dot: "bg-red-500", label: "text-red-700", icon: "⚠️" },
  Neutral: { dot: "bg-yellow-400", label: "text-yellow-700", icon: "📋" },
  Good:    { dot: "bg-green-500", label: "text-green-700", icon: "✅" },
};

export default function ChangeTimeline({ companyName, history, onSelectEntry, selectedEntry }: Props) {
  if (history.length === 0) {
    return (
      <div className="text-gray-500 text-sm py-4 text-center">
        No changes tracked yet for {companyName}.
      </div>
    );
  }

  // Show most recent first
  const sorted = [...history].reverse();

  return (
    <div className="relative">
      <h3 className="text-sm font-semibold text-gray-700 mb-3 uppercase tracking-wide">
        Change Timeline — {companyName}
      </h3>

      {/* Vertical line */}
      <div className="absolute left-3 top-10 bottom-0 w-px bg-gray-200" aria-hidden />

      <ol className="space-y-3">
        {sorted.map((entry, idx) => {
          const styles = VERDICT_STYLES[entry.verdict] ?? VERDICT_STYLES.Good;
          const isSelected = selectedEntry === entry;
          const date = new Date(entry.timestamp);

          return (
            <li
              key={idx}
              className={`relative flex gap-4 cursor-pointer rounded-lg px-3 py-2 transition-colors ${
                isSelected
                  ? "bg-indigo-50 ring-1 ring-indigo-300"
                  : "hover:bg-gray-50"
              }`}
              onClick={() => onSelectEntry(entry)}
            >
              {/* Dot */}
              <div
                className={`mt-1 h-3 w-3 rounded-full flex-shrink-0 ${styles.dot}`}
                title={entry.verdict}
              />

              <div className="min-w-0 flex-1">
                {/* Date + verdict */}
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-xs font-medium text-gray-700">
                    {date.toLocaleDateString(undefined, {
                      year: "numeric",
                      month: "short",
                      day: "numeric",
                    })}
                  </span>
                  <span
                    className={`text-xs font-semibold ${styles.label}`}
                  >
                    {styles.icon} {entry.verdict}
                  </span>
                </div>

                {/* Change reason */}
                {entry.changeReason && (
                  <p className="text-xs text-gray-500 mt-0.5 truncate">
                    {entry.changeReason}
                  </p>
                )}

                {/* Abbreviated diff summary */}
                {entry.diffSummary && (
                  <p className="text-xs text-gray-400 mt-0.5 truncate">
                    {Object.entries(entry.diffSummary)
                      .filter(([, v]) => v && v !== "No significant change")
                      .map(([k]) => k)
                      .join(", ") || "No flagged categories"}
                  </p>
                )}

                {/* Hash snippet */}
                <p className="text-xs font-mono text-gray-300 mt-0.5">
                  {entry.current_hash.slice(0, 12)}…
                </p>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
