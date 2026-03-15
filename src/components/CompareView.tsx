/**
 * CompareView.tsx – Side-by-side company TOS comparison panel.
 *
 * Lets users select two companies and see a visual summary of each company's
 * key TOS dimensions (Data Practices, User Rights, Readability) side-by-side,
 * along with grade badges, summary points, and watchlist flags.
 */

import { useState, useCallback } from "react";
import { CheckCircle, XCircle, Info, Printer, Share2 } from "lucide-react";
import type { CompanyResult, SummaryPoint } from "../types";
import ScoreBadge, { scoreToGrade } from "./ScoreBadge";
import {
  deriveDataScore,
  deriveUserRightsScore,
  deriveReadabilityScore,
  deriveOverallScore,
} from "../utils/scoreUtils";
import { Card, Badge } from "./ui";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getCompanyScore(company: CompanyResult): number {
  if (typeof company.score === "number") return company.score;
  const history = company.history ?? [];
  const latest = history[history.length - 1];
  if (latest?.trustScore !== undefined) return latest.trustScore;
  const summary = company.latestSummary ?? company.summary ?? "";
  if (summary) return deriveOverallScore(summary);
  return 75;
}

interface Scores {
  dataPractices: number;
  userRights: number;
  readability: number;
  overall: number;
}

function getScores(company: CompanyResult): Scores {
  if (company.scores) {
    return {
      dataPractices: company.scores.dataPractices,
      userRights: company.scores.userRights,
      readability: company.scores.readability,
      overall: company.scores.overall,
    };
  }
  const summary = company.latestSummary ?? company.summary ?? "";
  if (summary) {
    return {
      dataPractices: deriveDataScore(summary),
      userRights: deriveUserRightsScore(summary),
      readability: deriveReadabilityScore(summary),
      overall: deriveOverallScore(summary),
    };
  }
  return {
    dataPractices: getCompanyScore(company),
    userRights: getCompanyScore(company),
    readability: getCompanyScore(company),
    overall: getCompanyScore(company),
  };
}

function barColor(score: number): string {
  if (score >= 70) return "bg-emerald-500";
  if (score >= 50) return "bg-amber-400";
  if (score >= 30) return "bg-orange-400";
  return "bg-rose-500";
}

function textColor(score: number): string {
  if (score >= 70) return "text-emerald-700";
  if (score >= 50) return "text-amber-700";
  if (score >= 30) return "text-orange-700";
  return "text-rose-700";
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

const DIMENSIONS = [
  { key: "dataPractices" as const, label: "Data Practices", icon: "🔒" },
  { key: "userRights" as const,    label: "User Rights",    icon: "⚖️" },
  { key: "readability" as const,   label: "Readability",    icon: "📖" },
];

function DimensionBar({
  label,
  icon,
  score,
}: {
  label: string;
  icon: string;
  score: number;
}) {
  const clamped = Math.max(0, Math.min(100, Math.round(score)));
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-gray-700 flex items-center gap-1">
          <span aria-hidden="true">{icon}</span>
          {label}
        </span>
        <span className={`text-xs font-bold ${textColor(clamped)}`}>{clamped}</span>
      </div>
      <div
        className="h-2 rounded-full bg-gray-100 overflow-hidden"
        role="progressbar"
        aria-valuenow={clamped}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`${label}: ${clamped} out of 100`}
      >
        <div
          className={`h-full rounded-full ${barColor(clamped)} transition-all duration-500`}
          style={{ width: `${clamped}%` }}
        />
      </div>
    </div>
  );
}

function PointIcon({ impact }: { impact: SummaryPoint["impact"] }) {
  if (impact === "positive")
    return <CheckCircle className="h-3.5 w-3.5 text-emerald-500 flex-shrink-0" aria-hidden="true" />;
  if (impact === "negative")
    return <XCircle className="h-3.5 w-3.5 text-rose-500 flex-shrink-0" aria-hidden="true" />;
  return <Info className="h-3.5 w-3.5 text-sky-500 flex-shrink-0" aria-hidden="true" />;
}

function CompanyColumn({
  company,
  onSelectCompany,
}: {
  company: CompanyResult;
  onSelectCompany: (c: CompanyResult) => void;
}) {
  const score = getCompanyScore(company);
  const scores = getScores(company);
  const grade = company.history?.[company.history.length - 1]?.letterGrade ?? scoreToGrade(score);

  const points = (
    company.currentSummaryPoints ??
    company.summaryPoints ??
    company.history?.[company.history.length - 1]?.summaryPoints ??
    []
  ).slice(0, 5);

  const watchlistHits = (
    company.currentWatchlistHits ??
    company.history?.[company.history.length - 1]?.watchlist_hits ??
    []
  ).slice(0, 6);

  return (
    <div className="flex-1 min-w-0 rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
      {/* Company header */}
      <div className="bg-gradient-to-r from-indigo-50 to-purple-50 px-4 py-3 border-b border-indigo-100">
        <div className="flex items-center justify-between gap-2">
          <div className="min-w-0">
            <button
              type="button"
              onClick={() => onSelectCompany(company)}
              className="text-sm font-bold text-gray-900 truncate hover:text-indigo-700 transition-colors
                         focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 rounded"
            >
              {company.name}
            </button>
            {company.category && (
              <p className="text-xs text-gray-500 mt-0.5">{company.category}</p>
            )}
          </div>
          <ScoreBadge grade={grade} size="sm" />
        </div>
        <p className="text-lg font-bold text-indigo-700 mt-1">{Math.round(score)}<span className="text-xs font-normal text-gray-500">/100</span></p>
      </div>

      {/* Score bars */}
      <div className="px-4 py-3 space-y-2 border-b border-gray-100">
        {DIMENSIONS.map((dim) => (
          <DimensionBar
            key={dim.key}
            label={dim.label}
            icon={dim.icon}
            score={scores[dim.key]}
          />
        ))}
      </div>

      {/* Key points */}
      {points.length > 0 && (
        <div className="px-4 py-3 border-b border-gray-100">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Key Clauses</p>
          <ul className="space-y-1.5">
            {points.map((point, i) => (
              <li key={i} className="flex items-start gap-1.5">
                <PointIcon impact={point.impact} />
                <span className="text-xs text-gray-700 leading-tight">{point.text}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Watchlist hits */}
      {watchlistHits.length > 0 && (
        <div className="px-4 py-3">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">⚠️ Watchlist</p>
          <div className="flex flex-wrap gap-1">
            {watchlistHits.map((hit) => (
              <Badge key={hit} intent="warning">{hit}</Badge>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Winner highlight row
// ---------------------------------------------------------------------------

function WinnerRow({ label, icon, scoreA, scoreB, nameA, nameB }: {
  label: string;
  icon: string;
  scoreA: number;
  scoreB: number;
  nameA: string;
  nameB: string;
}) {
  const a = Math.round(scoreA);
  const b = Math.round(scoreB);
  const diff = Math.abs(a - b);
  const winner = a > b ? nameA : b > a ? nameB : null;
  return (
    <tr className="border-b border-gray-100 last:border-b-0">
      <td className="px-3 py-2 text-xs font-medium text-gray-700">
        <span aria-hidden="true">{icon}</span> {label}
      </td>
      <td className={`px-3 py-2 text-xs font-bold text-center ${textColor(a)} ${winner === nameA ? "bg-emerald-50" : ""}`}>
        {a}{winner === nameA && <span className="ml-1 text-emerald-600">✓</span>}
      </td>
      <td className={`px-3 py-2 text-xs font-bold text-center ${textColor(b)} ${winner === nameB ? "bg-emerald-50" : ""}`}>
        {b}{winner === nameB && <span className="ml-1 text-emerald-600">✓</span>}
      </td>
      <td className="px-3 py-2 text-xs text-gray-500 text-center">
        {diff === 0 ? "Tied" : `+${diff} for ${winner}`}
      </td>
    </tr>
  );
}

// ---------------------------------------------------------------------------
// Company selector
// ---------------------------------------------------------------------------

function CompanySelector({
  companies,
  selected,
  onChange,
  label,
  exclude,
}: {
  companies: CompanyResult[];
  selected: CompanyResult | null;
  onChange: (c: CompanyResult | null) => void;
  label: string;
  exclude?: CompanyResult | null;
}) {
  const [query, setQuery] = useState("");
  const filtered = companies
    .filter((c) => c !== exclude)
    .filter((c) => !query || c.name.toLowerCase().includes(query.toLowerCase()))
    .slice(0, 30);

  return (
    <div className="flex-1 min-w-0">
      <label className="block text-xs font-semibold text-gray-600 mb-1">{label}</label>
      {selected ? (
        <div className="flex items-center gap-2 rounded-lg border border-indigo-300 bg-indigo-50 px-3 py-2">
          <span className="flex-1 text-sm font-medium text-indigo-900 truncate">{selected.name}</span>
          <button
            type="button"
            onClick={() => onChange(null)}
            aria-label={`Remove ${selected.name}`}
            className="text-indigo-400 hover:text-indigo-700 transition-colors text-xs
                       focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 rounded"
          >
            ✕
          </button>
        </div>
      ) : (
        <div className="relative">
          <input
            type="search"
            placeholder="Search company…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm
                       focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500
                       transition-shadow"
            aria-label={`${label}: search for a company`}
          />
          {query && (
            <ul
              className="absolute z-20 mt-1 w-full rounded-lg border border-gray-200 bg-white shadow-lg max-h-48 overflow-y-auto"
              role="listbox"
              aria-label={`${label} options`}
            >
              {filtered.length === 0 ? (
                <li className="px-3 py-2 text-xs text-gray-400 italic">No results</li>
              ) : (
                filtered.map((c) => (
                  <li key={c.name} role="option" aria-selected={false}>
                    <button
                      type="button"
                      className="w-full text-left px-3 py-2 text-sm hover:bg-indigo-50 transition-colors
                                 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-inset"
                      onClick={() => { onChange(c); setQuery(""); }}
                    >
                      {c.name}
                      {c.category && (
                        <span className="ml-1 text-xs text-gray-400">({c.category})</span>
                      )}
                    </button>
                  </li>
                ))
              )}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main export
// ---------------------------------------------------------------------------

interface Props {
  companies: CompanyResult[];
  onSelectCompany: (company: CompanyResult) => void;
}

export default function CompareView({ companies, onSelectCompany }: Props) {
  const [companyA, setCompanyA] = useState<CompanyResult | null>(null);
  const [companyB, setCompanyB] = useState<CompanyResult | null>(null);
  const [shareStatus, setShareStatus] = useState<"idle" | "copied" | "shown">("idle");
  const [shareUrl, setShareUrl] = useState("");

  const handlePrint = useCallback(() => {
    window.print();
  }, []);

  const handleShare = useCallback(async () => {
    const params = new URLSearchParams();
    if (companyA) params.set("compareA", companyA.name);
    if (companyB) params.set("compareB", companyB.name);
    const url = `${window.location.origin}${window.location.pathname}?${params.toString()}`;
    setShareUrl(url);
    try {
      await navigator.clipboard.writeText(url);
      setShareStatus("copied");
      setTimeout(() => setShareStatus("idle"), 3000);
    } catch {
      setShareStatus("shown");
    }
  }, [companyA, companyB]);

  const scoresA = companyA ? getScores(companyA) : null;
  const scoresB = companyB ? getScores(companyB) : null;
  const canCompare = !!(companyA && companyB);

  return (
    <div className="animate-fade-in" aria-label="Company comparison tool">
      <div className="mb-6">
        <h2 className="text-xl font-bold text-gray-900 mb-1">Compare Companies</h2>
        <p className="text-sm text-gray-500">
          Select two companies to compare their TOS posture side-by-side.
        </p>
      </div>

      {/* Company selectors */}
      <Card className="mb-6 no-print">
        <Card.Body className="!space-y-0">
          <div className="flex flex-col sm:flex-row gap-4 items-start">
            <CompanySelector
              companies={companies}
              selected={companyA}
              onChange={setCompanyA}
              label="Company A"
              exclude={companyB}
            />
            <div className="flex items-center justify-center sm:mt-5 text-gray-400 font-bold text-lg select-none" aria-hidden="true">
              vs
            </div>
            <CompanySelector
              companies={companies}
              selected={companyB}
              onChange={setCompanyB}
              label="Company B"
              exclude={companyA}
            />
          </div>
        </Card.Body>
      </Card>

      {/* Comparison result */}
      {canCompare && (
        <>
          {/* Action buttons */}
          <div className="flex gap-2 mb-4 no-print">
            <button
              type="button"
              onClick={handlePrint}
              className="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white
                         px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 transition-colors
                         focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-1 shadow-sm"
              aria-label="Print comparison report"
            >
              <Printer className="h-3.5 w-3.5" aria-hidden="true" />
              Print / Save PDF
            </button>
            <button
              type="button"
              onClick={handleShare}
              className="inline-flex items-center gap-1.5 rounded-lg border border-indigo-300 bg-indigo-50
                         px-3 py-1.5 text-xs font-medium text-indigo-700 hover:bg-indigo-100 transition-colors
                         focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-1 shadow-sm"
              aria-label="Copy shareable link to comparison"
            >
              <Share2 className="h-3.5 w-3.5" aria-hidden="true" />
              Share Link
            </button>
          </div>

          {/* Share notification – accessible inline message */}
          {shareStatus === "copied" && (
            <div
              role="status"
              aria-live="polite"
              className="mb-4 flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-800 no-print"
            >
              <CheckCircle className="h-3.5 w-3.5 text-emerald-600 flex-shrink-0" aria-hidden="true" />
              Link copied to clipboard!
            </div>
          )}
          {shareStatus === "shown" && (
            <div
              role="status"
              aria-live="polite"
              className="mb-4 rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-2 no-print"
            >
              <p className="text-xs text-indigo-700 mb-1 font-medium">Copy this link to share:</p>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  readOnly
                  value={shareUrl}
                  className="flex-1 text-xs bg-white border border-indigo-200 rounded px-2 py-1 text-indigo-900 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  aria-label="Shareable comparison link"
                  onFocus={(e) => e.target.select()}
                />
                <button
                  type="button"
                  onClick={() => setShareStatus("idle")}
                  className="text-xs text-indigo-500 hover:text-indigo-700 transition-colors
                             focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 rounded"
                  aria-label="Dismiss share link"
                >
                  ✕
                </button>
              </div>
            </div>
          )}

          {/* Side-by-side columns */}
          <div className="flex flex-col sm:flex-row gap-4 mb-6">
            <CompanyColumn company={companyA!} onSelectCompany={onSelectCompany} />
            <CompanyColumn company={companyB!} onSelectCompany={onSelectCompany} />
          </div>

          {/* Head-to-head summary table */}
          <Card>
            <Card.Header
              icon="📊"
              title="Head-to-Head Summary"
              subtitle={`${companyA!.name} vs ${companyB!.name}`}
            />
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 text-left">
                    <th className="px-3 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wide">Dimension</th>
                    <th className="px-3 py-2 text-xs font-semibold text-gray-700 text-center">{companyA!.name}</th>
                    <th className="px-3 py-2 text-xs font-semibold text-gray-700 text-center">{companyB!.name}</th>
                    <th className="px-3 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wide text-center">Edge</th>
                  </tr>
                </thead>
                <tbody>
                  <WinnerRow
                    label="Overall Score"
                    icon="🏅"
                    scoreA={scoresA!.overall}
                    scoreB={scoresB!.overall}
                    nameA={companyA!.name}
                    nameB={companyB!.name}
                  />
                  {DIMENSIONS.map((dim) => (
                    <WinnerRow
                      key={dim.key}
                      label={dim.label}
                      icon={dim.icon}
                      scoreA={scoresA![dim.key]}
                      scoreB={scoresB![dim.key]}
                      nameA={companyA!.name}
                      nameB={companyB!.name}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}

      {!canCompare && (
        <div className="flex flex-col items-center justify-center h-40 text-gray-400 text-sm rounded-xl border border-dashed border-gray-300 gap-2">
          <span className="text-2xl" aria-hidden="true">⚖️</span>
          Select two companies above to start comparing
        </div>
      )}
    </div>
  );
}
