import { useState } from "react";
import { CheckCircle, XCircle, Info, ChevronDown, ChevronUp } from "lucide-react";
import type { CompanyResult, SummaryPoint } from "../types";
import ScoreBadge, { scoreToGrade } from "./ScoreBadge";

interface Props {
  company: CompanyResult;
  onSelectCompany: (company: CompanyResult) => void;
}

function getCompanyScore(company: CompanyResult): number {
  if (typeof company.score === "number") return company.score;
  const history = company.history ?? [];
  const latest = history[history.length - 1];
  return latest?.trustScore ?? 100;
}

function getScoreCardStyle(score: number): { bg: string; border: string } {
  // Thresholds match the A–E grade scale: A≥90, B≥70, C≥50, D≥30, E<30
  if (score >= 70) return { bg: "bg-gray-50", border: "border-gray-200" };
  if (score >= 50) return { bg: "bg-amber-50/50", border: "border-amber-200" };
  if (score >= 30) return { bg: "bg-orange-50/50", border: "border-orange-200" };
  return { bg: "bg-rose-50/50", border: "border-rose-200" };
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
  const trustScore = latestEntry?.trustScore ?? company.score ?? 100;
  const score = getCompanyScore(company);
  const { bg, border } = getScoreCardStyle(score);
  const grade =
    latestEntry?.letterGrade ?? scoreToGrade(trustScore);

  // Prefer summaryPoints from the company root, then from the latest history entry
  const rawPoints =
    company.summaryPoints ??
    latestEntry?.summaryPoints ??
    [];
  const displayPoints = topPoints(rawPoints);

  return (
    <li
      className={`group relative rounded-lg border shadow-sm cursor-pointer transition-all duration-150 hover:shadow-lg hover:-translate-y-1 ${bg} ${border}`}
      onClick={() => onSelectCompany(company)}
    >
      <div className="p-4">
        {/* Header row */}
        <div className="flex items-center gap-2 mb-2 pr-14">
          <CompanyLogo tosUrl={company.tosUrl} name={company.name} />
          <h2 className="text-sm font-semibold truncate font-[Inter,system-ui,sans-serif]">
            {company.name}
          </h2>
        </div>

        {/* Score badge (letter grade) – top-right */}
        <span className="absolute top-3 right-3">
          <ScoreBadge grade={grade} size="sm" />
        </span>

        {/* Category */}
        {company.category && (
          <p className="text-xs text-gray-500 mb-2">{company.category}</p>
        )}

        {/* Summary points – top 3, with impact icons and expandable quotes */}
        {displayPoints.length > 0 ? (
          <ul className="space-y-1.5 mt-1">
            {displayPoints.map((point, i) => (
              <PointRow key={i} point={point} />
            ))}
          </ul>
        ) : company.latestSummary ? (
          /* Fallback for data without summaryPoints yet */
          <p className="text-xs text-gray-600 line-clamp-2 mt-1 font-[Inter,system-ui,sans-serif]">
            {company.latestSummary}
          </p>
        ) : null}

        {/* Last Changed timestamp */}
        {latestEntry && (
          <p className="text-xs text-gray-400 mt-2">
            Last Changed:{" "}
            {new Date(latestEntry.timestamp).toLocaleDateString(undefined, {
              year: "numeric",
              month: "short",
              day: "numeric",
            })}
          </p>
        )}

        {/* Change count */}
        {company.history && company.history.length > 0 && (
          <p className="text-xs text-indigo-500 mt-1">
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
          className="absolute bottom-3 right-3 text-gray-400 hover:text-gray-700 transition-colors"
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

      {/* View History button – fades in on hover */}
      <div className="absolute bottom-3 left-1/2 -translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity duration-150 pointer-events-none group-hover:pointer-events-auto">
        <span className="inline-flex items-center gap-1 rounded-full bg-indigo-600 px-3 py-1 text-xs font-semibold text-white shadow-sm">
          View History
        </span>
      </div>
    </li>
  );
}

