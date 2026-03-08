import type { HistoryEntry } from "../types";

interface Props {
  entry: HistoryEntry;
  companyName: string;
}

const VERDICT_COLORS = {
  Caution: { bg: "bg-red-50", border: "border-red-300", title: "text-red-700" },
  Neutral: { bg: "bg-yellow-50", border: "border-yellow-300", title: "text-yellow-700" },
  Good:    { bg: "bg-green-50", border: "border-green-300", title: "text-green-700" },
};

const CATEGORY_ICONS: Record<string, string> = {
  Privacy: "🔒",
  DataOwnership: "🗂️",
  UserRights: "⚖️",
};

function HashBadge({ label, hash }: { label: string; hash: string | null }) {
  if (!hash) {
    return (
      <div className="min-w-0">
        <p className="text-xs text-gray-400">{label}</p>
        <p className="text-xs font-mono text-gray-300 italic">none</p>
      </div>
    );
  }
  return (
    <div className="min-w-0">
      <p className="text-xs text-gray-400">{label}</p>
      <p
        className="text-xs font-mono text-gray-600 truncate"
        title={hash}
      >
        {hash.slice(0, 16)}…
      </p>
    </div>
  );
}

export default function DiffViewer({ entry, companyName }: Props) {
  const colors = VERDICT_COLORS[entry.verdict] ?? VERDICT_COLORS.Good;
  const date = new Date(entry.timestamp).toLocaleString();

  return (
    <div className={`rounded-xl border shadow-sm ${colors.bg} ${colors.border}`}>
      {/* Header */}
      <div className="px-4 py-3 border-b border-current border-opacity-20">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div>
            <h3 className={`text-sm font-bold ${colors.title}`}>
              {companyName} — {entry.verdict} Change
            </h3>
            <p className="text-xs text-gray-500 mt-0.5">{date}</p>
          </div>
          {entry.changeReason && (
            <span className="rounded-full bg-white/70 border px-3 py-0.5 text-xs text-gray-600">
              {entry.changeReason}
            </span>
          )}
        </div>

        {/* Hash row */}
        <div className="flex gap-6 mt-2 flex-wrap">
          <HashBadge label="Previous hash" hash={entry.previous_hash} />
          <HashBadge label="Current hash" hash={entry.current_hash} />
        </div>
      </div>

      {/* AI-labeled breakdown */}
      {entry.diffSummary && (
        <div className="px-4 py-3">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
            AI-Labeled Breakdown
          </p>
          <div className="space-y-2">
            {(["Privacy", "DataOwnership", "UserRights"] as const).map((key) => {
              const val = entry.diffSummary[key];
              const isChanged = val && val !== "No significant change";
              return (
                <div key={key} className="flex gap-2 items-start">
                  <span className="text-base flex-shrink-0 mt-0.5">
                    {CATEGORY_ICONS[key]}
                  </span>
                  <div className="min-w-0">
                    <p className="text-xs font-semibold text-gray-600">{key}</p>
                    <p
                      className={`text-xs mt-0.5 ${
                        isChanged ? "text-gray-800" : "text-gray-400 italic"
                      }`}
                    >
                      {val || "No significant change"}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Metadata footer */}
      <div className="px-4 py-2 border-t border-current border-opacity-10 flex items-center gap-3 flex-wrap">
        <span
          className={`text-xs font-medium px-2 py-0.5 rounded-full bg-white/60 border ${
            entry.changeIsSubstantial ? "text-red-600" : "text-gray-500"
          }`}
        >
          {entry.changeIsSubstantial ? "Substantive change" : "Minor change"}
        </span>
        <span className="text-xs text-gray-400 font-mono">
          SHA-256: {entry.current_hash.slice(0, 20)}…
        </span>
      </div>
    </div>
  );
}
