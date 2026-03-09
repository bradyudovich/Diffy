/**
 * Leaderboard.tsx – "Top Rated" and "Recently Flagged" sidebar.
 *
 * "Top Rated"       – companies sorted by highest Diffy score (best privacy
 *                     posture first).
 * "Recently Flagged" – companies whose latest history entry has a "Caution"
 *                      verdict, sorted by most-recently changed.
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

function getLatestVerdict(company: CompanyResult): string | undefined {
  const history = company.history ?? [];
  return history[history.length - 1]?.verdict;
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
      : clamped >= 40
      ? "bg-yellow-100 text-yellow-800 border-yellow-300"
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
}

function LeaderboardRow({ company, rank, onSelect }: LeaderboardRowProps) {
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
          <span className="truncate text-sm font-medium text-gray-800 group-hover:text-indigo-700">
            {company.name}
          </span>
        </span>
        <ScorePill score={score} />
      </button>
    </li>
  );
}

export default function Leaderboard({ companies, onSelectCompany }: Props) {
  const topRated = [...companies]
    .sort((a, b) => getCompanyScore(b) - getCompanyScore(a))
    .slice(0, 5);

  const recentlyFlagged = [...companies]
    .filter((c) => getLatestVerdict(c) === "Caution")
    .sort((a, b) => getLatestTimestamp(b) - getLatestTimestamp(a))
    .slice(0, 5);

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

      {/* Recently Flagged */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-100 bg-red-50">
          <h3 className="text-sm font-semibold text-red-800 flex items-center gap-1.5">
            <span aria-hidden="true">⚠️</span> Recently Flagged
          </h3>
          <p className="text-xs text-red-600 mt-0.5">Latest Caution verdicts</p>
        </div>
        {recentlyFlagged.length === 0 ? (
          <p className="px-4 py-3 text-xs text-gray-400 italic">No flagged companies.</p>
        ) : (
          <ul className="divide-y divide-gray-50 py-1">
            {recentlyFlagged.map((company) => (
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
