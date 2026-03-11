import { useState } from "react";
import type { CompanyResult } from "../types";
import VerdictBadge from "./VerdictBadge";
import ScoreGauge from "./ScoreGauge";

interface Props {
  company: CompanyResult;
  onSelectCompany: (company: CompanyResult) => void;
}

function getLatestVerdict(company: CompanyResult): "Good" | "Neutral" | "Caution" {
  if (!company.history || company.history.length === 0) return "Good";
  return company.history[company.history.length - 1].verdict;
}

function getCompanyScore(company: CompanyResult): number {
  if (typeof company.score === "number") return company.score;
  const history = company.history ?? [];
  const latest = history[history.length - 1];
  return latest?.trustScore ?? 100;
}

function getScoreCardStyle(score: number): { bg: string; border: string; label: string } {
  if (score >= 85) return { bg: "bg-green-50", border: "border-green-200", label: "OK" };
  if (score >= 70) return { bg: "bg-yellow-50", border: "border-yellow-300", label: "Caution" };
  return { bg: "bg-red-50", border: "border-red-400", label: "Alert" };
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
  const verdict = getLatestVerdict(company);
  const latestEntry = company.history?.[company.history.length - 1];
  // trustScore: entry-level score used to render the ScoreGauge (undefined = no gauge shown)
  const trustScore = latestEntry?.trustScore;
  // score: best available company-level score used for card background color
  const score = getCompanyScore(company);
  const { bg, border } = getScoreCardStyle(score);

  return (
    <li
      className={`group relative rounded-lg border shadow-sm cursor-pointer transition-all duration-150 hover:shadow-lg hover:-translate-y-1 ${bg} ${border}`}
      onClick={() => onSelectCompany(company)}
    >
      <div className="p-4">
        {/* Header row */}
        <div className="flex items-center gap-2 mb-2 pr-20">
          <CompanyLogo tosUrl={company.tosUrl} name={company.name} />
          <h2 className="text-sm font-semibold truncate font-[Inter,system-ui,sans-serif]">
            {company.name}
          </h2>
        </div>

        {/* Verdict badge + Trust Score gauge */}
        <span className="absolute top-3 right-3 flex flex-col items-center gap-1">
          <VerdictBadge verdict={verdict} />
          {trustScore !== undefined && (
            <ScoreGauge score={trustScore} size="sm" />
          )}
        </span>

        {/* Category */}
        {company.category && (
          <p className="text-xs text-gray-500 mb-1">{company.category}</p>
        )}

        {/* Latest summary – truncated to 2 lines */}
        {company.latestSummary && (
          <p className="text-xs text-gray-600 line-clamp-2 mt-1 font-[Inter,system-ui,sans-serif]">
            {company.latestSummary}
          </p>
        )}

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

