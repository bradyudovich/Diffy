import { useState } from "react";
import { CheckCircle, XCircle, Info, ChevronDown, ChevronUp } from "lucide-react";
import type { CompanyResult, SummaryPoint } from "../types";
import ScoreBadge, { scoreToGrade } from "./ScoreBadge";
import ScoreBreakdownPanel from "./ScoreBreakdownPanel";
import {
  parseSummary,
  deriveDataScore,
  deriveUserRightsScore,
  deriveReadabilityScore,
  deriveOverallScore,
} from "../utils/scoreUtils";

interface Props {
  company: CompanyResult;
  onSelectCompany: (company: CompanyResult) => void;
}

function getCompanyScore(company: CompanyResult): number {
  if (typeof company.score === "number") return company.score;
  const history = company.history ?? [];
  const latest = history[history.length - 1];
  if (latest?.trustScore !== undefined) return latest.trustScore;
  // Derive a score from the TOS summary text for legacy data
  const summary = company.latestSummary ?? company.summary ?? "";
  if (summary) return deriveOverallScore(summary);
  return 75; // neutral default when no data at all
}

function getScoreCardStyle(score: number): { bg: string; border: string; accent: string } {
  // Thresholds match the A–E grade scale: A≥90, B≥70, C≥50, D≥30, E<30
  if (score >= 70) return { bg: "bg-white", border: "border-gray-200", accent: "bg-emerald-500" };
  if (score >= 50) return { bg: "bg-amber-50/40", border: "border-amber-200", accent: "bg-amber-400" };
  if (score >= 30) return { bg: "bg-orange-50/40", border: "border-orange-200", accent: "bg-orange-400" };
  return { bg: "bg-rose-50/40", border: "border-rose-200", accent: "bg-rose-500" };
}

/** Pick the top 3 most impactful points: negatives first, then positives, then neutrals. */
function topPoints(points: SummaryPoint[]): SummaryPoint[] {
  const neg = points.filter((p) => p.impact === "negative");
  const pos = points.filter((p) => p.impact === "positive");
  const neu = points.filter((p) => p.impact === "neutral");
  return [...neg, ...pos, ...neu].slice(0, 3);
}

function PointIcon({ impact }: { impact: SummaryPoint["impact"] }) {
  if (impact === "positive")
    return <CheckCircle className="h-3.5 w-3.5 text-emerald-500 flex-shrink-0" aria-hidden="true" />;
  if (impact === "negative")
    return <XCircle className="h-3.5 w-3.5 text-rose-500 flex-shrink-0" aria-hidden="true" />;
  return <Info className="h-3.5 w-3.5 text-sky-500 flex-shrink-0" aria-hidden="true" />;
}

/** A single summary point with an expandable quote box. */
function PointRow({ point }: { point: SummaryPoint }) {
  const [quoteOpen, setQuoteOpen] = useState(false);
  const hasQuote = !!point.quote;

  return (
    <li className="flex flex-col gap-0.5">
      <button
        type="button"
        className={`flex items-start gap-1.5 text-left w-full group/point ${hasQuote ? "cursor-pointer" : "cursor-default"}`}
        onClick={() => hasQuote && setQuoteOpen((v) => !v)}
        aria-expanded={hasQuote ? quoteOpen : undefined}
        disabled={!hasQuote}
      >
        <PointIcon impact={point.impact} />
        <span className="text-xs text-gray-700 leading-tight font-[Inter,system-ui,sans-serif] flex-1">
          {point.text}
        </span>
        {hasQuote && (
          <span className="flex-shrink-0 mt-0.5 text-gray-400 group-hover/point:text-gray-600 transition-colors">
            {quoteOpen
              ? <ChevronUp className="h-3 w-3" aria-hidden="true" />
              : <ChevronDown className="h-3 w-3" aria-hidden="true" />}
          </span>
        )}
      </button>
      {hasQuote && quoteOpen && (
        <blockquote className="ml-5 mt-1 rounded-md border-l-2 border-amber-300 bg-amber-50 px-2.5 py-1.5 text-xs text-amber-900 italic leading-snug">
          "{point.quote}"
        </blockquote>
      )}
    </li>
  );
}

function CompanyLogo({ tosUrl, name }: { tosUrl: string; name: string }) {
  const [imgError, setImgError] = useState(false);
  const [useLocal, setUseLocal] = useState(true);
  let domain = "";
  try {
    const { hostname } = new URL(tosUrl);
    domain = hostname.replace(/^www\./, "");
  } catch {
    /* ignore */
  }
  if (!domain || imgError) {
    return (
      <span className="h-6 w-6 flex items-center justify-center text-base flex-shrink-0">
        🏢
      </span>
    );
  }
  const src = useLocal
    ? `/favicons/${domain}.png`
    : `https://www.google.com/s2/favicons?sz=32&domain=${domain}`;
  return (
    <img
      src={src}
      alt={`${name} logo`}
      className="h-6 w-6 object-contain flex-shrink-0"
      onError={() => {
        if (useLocal) {
          setUseLocal(false);
        } else {
          setImgError(true);
        }
      }}
    />
  );
}

export default function ServiceCard({ company, onSelectCompany }: Props) {
  const latestEntry = company.history?.[company.history.length - 1];
  const trustScore = latestEntry?.trustScore ?? company.score ?? undefined;
  const score = getCompanyScore(company);
  const { bg, border, accent } = getScoreCardStyle(score);
  const grade =
    latestEntry?.letterGrade ?? scoreToGrade(score);

  // Prefer summaryPoints from the company root, then from the latest history entry
  const rawPoints =
    company.summaryPoints ??
    latestEntry?.summaryPoints ??
    [];
  const displayPoints = topPoints(rawPoints);

  // Summary text for legacy v1 data
  const summaryText = company.latestSummary ?? company.summary ?? "";
  const parsedSections = summaryText ? parseSummary(summaryText) : {};
  const sectionKeys = Object.keys(parsedSections).slice(0, 2);

  // Derived multi-dimensional scores (used when backend scores not available)
  const derivedScores =
    !company.scores && summaryText
      ? {
          dataPractices: deriveDataScore(summaryText),
          userRights: deriveUserRightsScore(summaryText),
          readability: deriveReadabilityScore(summaryText),
          overall: score,
        }
      : undefined;

  const hasScoreBreakdown = !!(company.scores || derivedScores);

  return (
    <li
      className={`group relative rounded-xl border shadow-sm cursor-pointer transition-all duration-200 hover:shadow-xl hover:-translate-y-1 overflow-hidden ${bg} ${border}`}
      onClick={() => onSelectCompany(company)}
    >
      {/* Coloured left accent strip */}
      <div className={`absolute left-0 top-0 bottom-0 w-1 ${accent}`} aria-hidden="true" />

      <div className="pl-5 pr-4 pt-4 pb-3">
        {/* Header row */}
        <div className="flex items-center gap-2 mb-2 pr-10">
          <CompanyLogo tosUrl={company.tosUrl} name={company.name} />
          <h2 className="text-sm font-semibold truncate font-[Inter,system-ui,sans-serif]">
            {company.name}
          </h2>
        </div>

        {/* Score badge (letter grade) – top-right */}
        <span className="absolute top-3 right-3">
          <ScoreBadge grade={grade} size="sm" />
        </span>

        {/* Category + score numeric */}
        <div className="flex items-center gap-2 mb-2">
          {company.category && (
            <span className="text-xs text-gray-500">{company.category}</span>
          )}
          {trustScore !== undefined && (
            <span className="text-xs font-semibold text-gray-400">
              · {Math.round(trustScore)}/100
            </span>
          )}
        </div>

        {/* Summary points – top 3, with impact icons and expandable quotes */}
        {displayPoints.length > 0 ? (
          <ul className="space-y-1.5 mt-1">
            {displayPoints.map((point, i) => (
              <PointRow key={i} point={point} />
            ))}
          </ul>
        ) : sectionKeys.length > 0 ? (
          /* Parsed legacy summary sections */
          <ul className="space-y-1 mt-1">
            {sectionKeys.map((key) => (
              <li key={key} className="flex items-start gap-1.5">
                <Info className="h-3.5 w-3.5 text-sky-400 flex-shrink-0 mt-0.5" aria-hidden="true" />
                <span className="text-xs text-gray-600 leading-tight font-[Inter,system-ui,sans-serif]">
                  <strong className="text-gray-700">{key}:</strong>{" "}
                  {parsedSections[key]}
                </span>
              </li>
            ))}
          </ul>
        ) : summaryText ? (
          /* Plain-text fallback */
          <p className="text-xs text-gray-600 line-clamp-2 mt-1 font-[Inter,system-ui,sans-serif]">
            {summaryText}
          </p>
        ) : null}

        {/* Score breakdown bars (compact) */}
        {hasScoreBreakdown && (
          <ScoreBreakdownPanel
            scores={company.scores}
            derived={derivedScores}
            compact
          />
        )}

        {/* Footer row */}
        <div className="flex items-center justify-between mt-2">
          <div>
            {latestEntry ? (
              <p className="text-xs text-gray-400">
                Changed{" "}
                {new Date(latestEntry.timestamp).toLocaleDateString(undefined, {
                  year: "numeric",
                  month: "short",
                  day: "numeric",
                })}
              </p>
            ) : company.lastChecked ? (
              <p className="text-xs text-gray-400">
                Checked{" "}
                {new Date(company.lastChecked).toLocaleDateString(undefined, {
                  year: "numeric",
                  month: "short",
                  day: "numeric",
                })}
              </p>
            ) : null}
            {company.history && company.history.length > 0 && (
              <p className="text-xs text-indigo-500">
                {company.history.length} change{company.history.length !== 1 ? "s" : ""} tracked
              </p>
            )}
          </div>

          {/* ToS link */}
          {company.tosUrl && (
            <a
              href={company.tosUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-gray-300 hover:text-gray-600 transition-colors"
              onClick={(e) => e.stopPropagation()}
              aria-label="View Terms of Service"
              title="View Terms of Service"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="w-4 h-4"
              >
                <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z" />
              </svg>
            </a>
          )}
        </div>
      </div>

      {/* View Details button – fades in on hover */}
      <div className="absolute bottom-3 left-1/2 -translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity duration-150 pointer-events-none group-hover:pointer-events-auto">
        <span className="inline-flex items-center gap-1 rounded-full bg-indigo-600 px-3 py-1 text-xs font-semibold text-white shadow-sm whitespace-nowrap">
          View Details →
        </span>
      </div>
    </li>
  );
}

