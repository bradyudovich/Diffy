import { useState } from "react";
import type { HistoryEntry } from "../types";
import VerdictBadge from "./VerdictBadge";
import RawDiffView from "./RawDiffView";

interface Props {
  entry: HistoryEntry;
  companyName: string;
  /** Raw text of the previous version, used for the Raw Changes tab. */
  previousRawText?: string;
  /** Raw text of the current version, used for the Raw Changes tab. */
  currentRawText?: string;
}

const WRAPPER_COLORS = {
  Caution: { bg: "bg-red-50", border: "border-red-300" },
  Neutral: { bg: "bg-blue-50", border: "border-blue-200" },
  Good:    { bg: "bg-green-50", border: "border-green-300" },
};

const CATEGORY_ICONS: Record<string, string> = {
  Privacy: "🔒",
  DataOwnership: "🗂️",
  UserRights: "⚖️",
};

const NO_CHANGE = "No significant changes detected";

type TabId = "summary" | "raw";

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

function AccordionRow({
  categoryKey,
  value,
}: {
  categoryKey: "Privacy" | "DataOwnership" | "UserRights";
  value: string;
}) {
  const [open, setOpen] = useState(true);
  const isChanged = value && value !== NO_CHANGE && value !== "No significant change";

  return (
    <div className="rounded-lg border border-gray-200 bg-white/70">
      <button
        type="button"
        className="flex w-full items-center justify-between px-3 py-2 text-left"
        onClick={() => setOpen((prev) => !prev)}
        aria-expanded={open}
      >
        <span className="flex items-center gap-2 text-xs font-semibold text-gray-700">
          <span aria-hidden="true">{CATEGORY_ICONS[categoryKey]}</span>
          {categoryKey}
          {isChanged && (
            <span className="rounded-full bg-amber-100 px-1.5 py-0.5 text-amber-700 font-medium">
              changed
            </span>
          )}
        </span>
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 20 20"
          fill="currentColor"
          className={`h-4 w-4 text-gray-400 transition-transform ${open ? "rotate-180" : ""}`}
        >
          <path
            fillRule="evenodd"
            d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z"
            clipRule="evenodd"
          />
        </svg>
      </button>

      {open && (
        <div className="border-t border-gray-100 px-3 py-2">
          <p
            className={`text-xs leading-relaxed ${
              isChanged ? "text-gray-800" : "text-gray-400 italic"
            }`}
          >
            {value || NO_CHANGE}
          </p>
        </div>
      )}
    </div>
  );
}

export default function DiffViewer({ entry, companyName, previousRawText = "", currentRawText = "" }: Props) {
  const [activeTab, setActiveTab] = useState<TabId>("summary");
  const colors = WRAPPER_COLORS[entry.verdict] ?? WRAPPER_COLORS.Good;
  const date = new Date(entry.timestamp).toLocaleString();

  return (
    <div className={`rounded-xl border shadow-sm ${colors.bg} ${colors.border}`}>
      {/* Header */}
      <div className="px-4 py-3 border-b border-current border-opacity-20">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold text-gray-800">
                {companyName}
              </h3>
              <VerdictBadge verdict={entry.verdict} />
            </div>
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

      {/* Tab bar */}
      <div className="flex border-b border-current border-opacity-10 px-4 pt-2 gap-1">
        {(["summary", "raw"] as TabId[]).map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => setActiveTab(tab)}
            className={`px-3 py-1.5 text-xs font-medium rounded-t-md transition-colors ${
              activeTab === tab
                ? "bg-white/80 text-indigo-700 border border-b-white border-gray-200 -mb-px"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            {tab === "summary" ? "AI Summary" : "Raw Changes"}
          </button>
        ))}
      </div>

      {/* Tab: AI-labeled breakdown */}
      {activeTab === "summary" && (
        <div className="px-4 py-3">
          {entry.diffSummary && (
            <>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                AI-Labeled Breakdown
              </p>
              <div className="space-y-2">
                {(["Privacy", "DataOwnership", "UserRights"] as const).map((key) => (
                  <AccordionRow
                    key={key}
                    categoryKey={key}
                    value={entry.diffSummary[key]}
                  />
                ))}
              </div>
            </>
          )}

          {/* Watchlist hits */}
          {entry.watchlist_hits && entry.watchlist_hits.length > 0 && (
            <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2">
              <p className="text-xs font-semibold text-amber-700 mb-1.5">
                ⚠️ High-Risk Terms Detected
              </p>
              <div className="flex flex-wrap gap-1.5">
                {entry.watchlist_hits.map((term) => (
                  <span
                    key={term}
                    className="rounded-full bg-amber-100 border border-amber-300 px-2 py-0.5 text-xs font-medium text-amber-800"
                  >
                    {term}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tab: Raw diff */}
      {activeTab === "raw" && (
        <div className="px-4 py-3">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
            Raw Text Changes
          </p>
          <RawDiffView oldText={previousRawText} newText={currentRawText} />
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
        {entry.changeMagnitude !== undefined && (
          <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-white/60 border text-gray-600">
            {entry.changeMagnitude.toFixed(1)}% changed
          </span>
        )}
        <span className="text-xs text-gray-400 font-mono">
          SHA-256: {entry.current_hash.slice(0, 20)}…
        </span>
      </div>
    </div>
  );
}

