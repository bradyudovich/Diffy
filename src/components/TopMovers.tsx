/**
 * TopMovers.tsx – Top/bottom performers and biggest score-change movers.
 *
 * Displays three horizontally-scrollable card columns on mobile, collapsing
 * into a three-column grid on wider screens:
 *   • Top Performers   – highest current scores
 *   • Bottom Performers – lowest current scores (candidates for review)
 *   • Top Movers        – largest absolute score change across history
 *
 * Keyboard navigable: every row is a focusable <button>.
 * Aria labelled: the section and each group is labelled for screen readers.
 */

import type { CompanyResult } from "../types";

interface Props {
  companies: CompanyResult[];
  onSelectCompany: (company: CompanyResult) => void;
}

// ── helpers ──────────────────────────────────────────────────────────────────

/** Neutral default score used when no score or history data is available. */
const DEFAULT_SCORE = 75;

/** Fallback trust score used when reading history entries without explicit data. */
const HISTORY_FALLBACK_SCORE = 65;

function getScore(c: CompanyResult): number {
  if (typeof c.score === "number") return c.score;
  const latest = (c.history ?? []).at(-1);
  return latest?.trustScore ?? DEFAULT_SCORE;
}

function getScoreDelta(c: CompanyResult): number | null {
  const history = c.history ?? [];
  if (history.length < 2) return null;
  const sorted = [...history].sort(
    (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
  );
  const earliest = sorted[0].trustScore ?? HISTORY_FALLBACK_SCORE;
  const latest   = sorted.at(-1)!.trustScore ?? HISTORY_FALLBACK_SCORE;
  return latest - earliest;
}

// ── sub-components ────────────────────────────────────────────────────────────

function ScorePill({ score }: { score: number }) {
  const clamped = Math.max(0, Math.min(100, Math.round(score)));
  const color =
    clamped >= 70
      ? "bg-emerald-100 text-emerald-800 border-emerald-200"
      : clamped >= 50
      ? "bg-amber-100 text-amber-800 border-amber-200"
      : "bg-rose-100 text-rose-800 border-rose-200";
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-semibold ${color}`}
    >
      {clamped}
    </span>
  );
}

interface RowProps {
  company: CompanyResult;
  rank: number;
  sub?: string;
  onSelect: (c: CompanyResult) => void;
}

function MoverRow({ company, rank, sub, onSelect }: RowProps) {
  const score = getScore(company);
  return (
    <li>
      <button
        type="button"
        onClick={() => onSelect(company)}
        className="w-full flex items-center justify-between gap-2 px-3 py-2 text-left rounded-lg
                   hover:bg-indigo-50 focus-visible:outline-none focus-visible:ring-2
                   focus-visible:ring-indigo-500 focus-visible:ring-offset-1
                   transition-colors group"
        aria-label={`${company.name}, score ${Math.round(score)}${sub ? `, ${sub}` : ""}`}
      >
        <span className="flex items-center gap-2 min-w-0">
          <span
            className="flex-shrink-0 w-5 text-center text-xs font-bold text-gray-400"
            aria-hidden="true"
          >
            {rank}
          </span>
          <span className="min-w-0">
            <span className="block truncate text-sm font-medium text-gray-800 group-hover:text-indigo-700 transition-colors">
              {company.name}
            </span>
            {sub && (
              <span className="block text-xs text-gray-400">{sub}</span>
            )}
          </span>
        </span>
        <ScorePill score={score} />
      </button>
    </li>
  );
}

interface PanelProps {
  title: string;
  icon: string;
  headerClass: string;
  ariaLabel: string;
  children: React.ReactNode;
}

function Panel({ title, icon, headerClass, ariaLabel, children }: PanelProps) {
  return (
    <section
      className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden flex flex-col"
      aria-label={ariaLabel}
    >
      <div className={`px-4 py-3 border-b border-gray-100 ${headerClass}`}>
        <h3 className="text-sm font-semibold flex items-center gap-1.5">
          <span aria-hidden="true">{icon}</span>
          {title}
        </h3>
      </div>
      <ul className="divide-y divide-gray-50 py-1 flex-1">{children}</ul>
    </section>
  );
}

// ── main export ───────────────────────────────────────────────────────────────

export default function TopMovers({ companies, onSelectCompany }: Props) {
  if (companies.length === 0) return null;

  const topPerformers = [...companies]
    .sort((a, b) => getScore(b) - getScore(a))
    .slice(0, 5);

  const bottomPerformers = [...companies]
    .sort((a, b) => getScore(a) - getScore(b))
    .slice(0, 5);

  const movers = [...companies]
    .map((c) => ({ company: c, delta: getScoreDelta(c) }))
    .filter(({ delta }) => delta !== null)
    .sort((a, b) => Math.abs(b.delta as number) - Math.abs(a.delta as number))
    .slice(0, 5);

  const hasMoverData = movers.length > 0;

  return (
    <section
      className="mb-6 animate-slide-up"
      aria-labelledby="top-movers-heading"
    >
      <h2
        id="top-movers-heading"
        className="text-xs font-bold uppercase tracking-widest text-gray-400 mb-3"
      >
        Performers &amp; Movers
      </h2>
      <div className={`grid gap-4 ${hasMoverData ? "lg:grid-cols-3" : "lg:grid-cols-2"}`}>
        {/* Top Performers */}
        <Panel
          title="Top Performers"
          icon="🏆"
          headerClass="bg-emerald-50"
          ariaLabel="Top performers by Diffy score"
        >
          {topPerformers.map((c, i) => (
            <MoverRow
              key={c.name}
              company={c}
              rank={i + 1}
              onSelect={onSelectCompany}
            />
          ))}
        </Panel>

        {/* Bottom Performers */}
        <Panel
          title="Needs Review"
          icon="⚠️"
          headerClass="bg-rose-50"
          ariaLabel="Companies with the lowest Diffy scores"
        >
          {bottomPerformers.map((c, i) => (
            <MoverRow
              key={c.name}
              company={c}
              rank={i + 1}
              onSelect={onSelectCompany}
            />
          ))}
        </Panel>

        {/* Top Movers – only rendered when history data is available */}
        {hasMoverData && (
          <Panel
            title="Top Movers"
            icon="📈"
            headerClass="bg-sky-50"
            ariaLabel="Companies with the biggest score changes over time"
          >
            {movers.map(({ company, delta }, i) => {
              const d = delta as number;
              const sign = d >= 0 ? "+" : "";
              return (
                <MoverRow
                  key={company.name}
                  company={company}
                  rank={i + 1}
                  sub={`${sign}${Math.round(d)} pts`}
                  onSelect={onSelectCompany}
                />
              );
            })}
          </Panel>
        )}
      </div>
    </section>
  );
}
