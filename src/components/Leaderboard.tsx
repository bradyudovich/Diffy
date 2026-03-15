/**
 * Leaderboard.tsx – "Top Rated" and "Recently Flagged" sidebar.
 *
 * "Top Rated"        – companies sorted by highest Diffy score (best privacy
 *                      posture first).
 * "Recently Changed" – companies with the most recent history entries, showing
 *                      their current score so users can spot freshly changed TOS.
 * "Needs Review"     – companies with a score below 70, sorted by lowest score.
 */

import type { CompanyResult } from "../types";

interface Props {
  companies: CompanyResult[];
  onSelectCompany: (company: CompanyResult) => void;
}

function getCompanyScore(company: CompanyResult): number {
  if (typeof company.score === "number") return company.score;
  const history = company.history ?? [];
  const latest = history[history.length - 1];
  return latest?.trustScore ?? 100;
}

function getLatestTimestamp(company: CompanyResult): number {
  const history = company.history ?? [];
  const ts = history[history.length - 1]?.timestamp;
  return ts ? new Date(ts).getTime() : 0;
}

function ScorePill({ score }: { score: number }) {
  const clamped = Math.max(0, Math.min(100, Math.round(score)));
  const color =
    clamped >= 70
      ? "bg-green-100 text-green-800 border-green-300"
      : clamped >= 50
      ? "bg-amber-100 text-amber-800 border-amber-300"
      : "bg-red-100 text-red-800 border-red-300";
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-semibold ${color}`}
      title={`Diffy score: ${clamped}/100`}
    >
      {clamped}
    </span>
  );
}

interface LeaderboardRowProps {
  company: CompanyResult;
  rank?: number;
  onSelect: (c: CompanyResult) => void;
  /** Extra label shown below the company name. */
  subLabel?: string;
}

function LeaderboardRow({ company, rank, onSelect, subLabel }: LeaderboardRowProps) {
  const score = getCompanyScore(company);
  return (
    <li>
      <button
        type="button"
        onClick={() => onSelect(company)}
        className="w-full flex items-center justify-between gap-2 px-3 py-2 text-left rounded-lg hover:bg-indigo-50 transition-colors group"
      >
        <span className="flex items-center gap-2 min-w-0">
          {rank !== undefined && (
            <span className="flex-shrink-0 w-5 text-center text-xs font-bold text-gray-400">
              {rank}
            </span>
          )}
          <span className="min-w-0">
            <span className="block truncate text-sm font-medium text-gray-800 group-hover:text-indigo-700">
              {company.name}
            </span>
            {subLabel && (
              <span className="block text-xs text-gray-400">{subLabel}</span>
            )}
          </span>
        </span>
        <ScorePill score={score} />
      </button>
    </li>
  );
}

export default function Leaderboard({ companies, onSelectCompany }: Props) {
  const topRated = [...companies]
    .filter((c) => typeof c.score === "number" || (c.history?.length ?? 0) > 0)
    .sort((a, b) => getCompanyScore(b) - getCompanyScore(a))
    .slice(0, 5);

  // Companies with history sorted by most-recent change
  const recentlyChanged = [...companies]
    .filter((c) => getLatestTimestamp(c) > 0)
    .sort((a, b) => getLatestTimestamp(b) - getLatestTimestamp(a))
    .slice(0, 4);

  // Companies with score below 70 ordered by worst score first
  const needsReview = [...companies]
    .filter((c) => (typeof c.score === "number" || (c.history?.length ?? 0) > 0) && getCompanyScore(c) < 70)
    .sort((a, b) => getCompanyScore(a) - getCompanyScore(b))
    .slice(0, 4);

  return (
    <aside className="space-y-4">
      {/* Top Rated */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-100 bg-green-50">
          <h3 className="text-sm font-semibold text-green-800 flex items-center gap-1.5">
            <span aria-hidden="true">🏆</span> Top Rated
          </h3>
          <p className="text-xs text-green-600 mt-0.5">Highest Diffy scores</p>
        </div>
        {topRated.length === 0 ? (
          <p className="px-4 py-3 text-xs text-gray-400 italic">No data yet.</p>
        ) : (
          <ul className="divide-y divide-gray-50 py-1">
            {topRated.map((company, i) => (
              <LeaderboardRow
                key={company.name}
                company={company}
                rank={i + 1}
                onSelect={onSelectCompany}
              />
            ))}
          </ul>
        )}
      </div>

      {/* Recently Changed */}
      {recentlyChanged.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-100 bg-blue-50">
            <h3 className="text-sm font-semibold text-blue-800 flex items-center gap-1.5">
              <span aria-hidden="true">🕐</span> Recently Changed
            </h3>
            <p className="text-xs text-blue-600 mt-0.5">Latest TOS updates</p>
          </div>
          <ul className="divide-y divide-gray-50 py-1">
            {recentlyChanged.map((company) => {
              const ts = getLatestTimestamp(company);
              const dateLabel = ts
                ? new Date(ts).toLocaleDateString(undefined, { month: "short", day: "numeric" })
                : "";
              return (
                <LeaderboardRow
                  key={company.name}
                  company={company}
                  onSelect={onSelectCompany}
                  subLabel={dateLabel}
                />
              );
            })}
          </ul>
        </div>
      )}

      {/* Needs Review */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-100 bg-red-50">
          <h3 className="text-sm font-semibold text-red-800 flex items-center gap-1.5">
            <span aria-hidden="true">⚠️</span> Needs Review
          </h3>
          <p className="text-xs text-red-600 mt-0.5">Score below 70</p>
        </div>
        {needsReview.length === 0 ? (
          <p className="px-4 py-3 text-xs text-gray-400 italic">No flagged companies.</p>
        ) : (
          <ul className="divide-y divide-gray-50 py-1">
            {needsReview.map((company) => (
              <LeaderboardRow
                key={company.name}
                company={company}
                onSelect={onSelectCompany}
              />
            ))}
          </ul>
        )}
      </div>
    </aside>
  );
}

