import { useState } from "react";
import type { HistoryEntry } from "../types";

interface Props {
  companyName: string;
  history: HistoryEntry[];
  onSelectEntry: (entry: HistoryEntry) => void;
  selectedEntry: HistoryEntry | null;
}

const VERDICT_STYLES = {
  Caution: { dot: "bg-red-500", label: "text-red-700", icon: "⚠️" },
  Neutral: { dot: "bg-blue-400", label: "text-blue-700", icon: "📋" },
  Good:    { dot: "bg-green-500", label: "text-green-700", icon: "✅" },
};

/** Flag filter options shown in the filter bar. */
type FlagFilter = "all" | "flagged" | "substantial" | "arbitration";

const FLAG_FILTER_LABELS: Record<FlagFilter, string> = {
  all:         "All",
  flagged:     "🚩 Flagged",
  substantial: "⚡ Substantial",
  arbitration: "⚖️ Arbitration",
};

/** Returns true when the entry matches the selected flag filter. */
function matchesFilter(entry: HistoryEntry, filter: FlagFilter): boolean {
  switch (filter) {
    case "all":
      return true;
    case "flagged":
      return (entry.watchlist_hits?.length ?? 0) > 0;
    case "substantial":
      return entry.changeIsSubstantial;
    case "arbitration": {
      const haystack = [
        ...(entry.watchlist_hits ?? []),
        entry.changeReason,
        entry.diffSummary?.UserRights ?? "",
        ...(entry.summaryPoints?.map((p) => p.text) ?? []),
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes("arbitration") || haystack.includes("class action") || haystack.includes("class-action");
    }
    default:
      return true;
  }
}

export default function ChangeTimeline({ companyName, history, onSelectEntry, selectedEntry }: Props) {
  const [activeFilter, setActiveFilter] = useState<FlagFilter>("all");

  if (history.length === 0) {
    return (
      <div className="text-gray-500 text-sm py-4 text-center">
        No changes tracked yet for {companyName}.
      </div>
    );
  }

  // Show most recent first, then apply the active filter
  const sorted = [...history].reverse();
  const filtered = sorted.filter((e) => matchesFilter(e, activeFilter));

  return (
    <div className="relative">
      <h3 className="text-sm font-semibold text-gray-700 mb-2 uppercase tracking-wide">
        Change Timeline — {companyName}
      </h3>

      {/* Flag filter bar */}
      <div className="flex flex-wrap gap-1 mb-3" role="group" aria-label="Filter timeline entries">
        {(Object.keys(FLAG_FILTER_LABELS) as FlagFilter[]).map((f) => (
          <button
            key={f}
            type="button"
            onClick={() => setActiveFilter(f)}
            className={`rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors ${
              activeFilter === f
                ? "bg-indigo-600 text-white"
                : "bg-gray-100 text-gray-600 hover:bg-indigo-50 hover:text-indigo-700"
            }`}
          >
            {FLAG_FILTER_LABELS[f]}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <p className="text-xs text-gray-400 py-3 text-center italic">
          No entries match the selected filter.
        </p>
      ) : (
        <div className="relative">
          {/* Vertical line scoped to the list */}
          <div className="absolute left-3 top-0 bottom-0 w-px bg-gray-200" aria-hidden />

          <ol className="space-y-3">
            {filtered.map((entry, idx) => {
              const styles = VERDICT_STYLES[entry.verdict] ?? VERDICT_STYLES.Good;
              const isSelected = selectedEntry === entry;
              const date = new Date(entry.timestamp);
              const hasFlags = (entry.watchlist_hits?.length ?? 0) > 0;

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
                      <span className={`text-xs font-semibold ${styles.label}`}>
                        {styles.icon} {entry.verdict}
                      </span>
                      {hasFlags && (
                        <span
                          className="text-xs text-amber-600 font-medium"
                          title={entry.watchlist_hits!.join(", ")}
                          aria-label={`${entry.watchlist_hits!.length} watchlist flag${entry.watchlist_hits!.length === 1 ? "" : "s"}`}
                        >
                          🚩 {entry.watchlist_hits!.length}
                        </span>
                      )}
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
                          .filter(([, v]) => v && v !== "No significant changes detected" && v !== "No significant change")
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
      )}
    </div>
  );
}
