import { useState } from "react";
import type { CompanyResult } from "../types";

interface Props {
  companies: CompanyResult[];
  onSelectCompany: (company: CompanyResult) => void;
}

const VERDICT_CONFIG = {
  Caution: { bg: "bg-red-50", border: "border-red-400", badge: "bg-red-200 text-red-800", icon: "⚠️" },
  Neutral: { bg: "bg-yellow-50", border: "border-yellow-400", badge: "bg-yellow-200 text-yellow-800", icon: "📋" },
  Good:    { bg: "bg-green-50", border: "border-green-200", badge: "bg-green-100 text-green-700", icon: "✅" },
};

function getLatestVerdict(company: CompanyResult): "Good" | "Neutral" | "Caution" {
  if (!company.history || company.history.length === 0) return "Good";
  return company.history[company.history.length - 1].verdict;
}

function CompanyLogo({ tosUrl, name }: { tosUrl: string; name: string }) {
  const [imgError, setImgError] = useState(false);
  let src = "";
  try {
    const { hostname } = new URL(tosUrl);
    const domain = hostname.replace(/^www\./, "");
    src = `https://www.google.com/s2/favicons?sz=32&domain=${domain}`;
  } catch {
    /* ignore */
  }
  if (!src || imgError) {
    return (
      <span className="h-6 w-6 flex items-center justify-center text-base flex-shrink-0">
        🏢
      </span>
    );
  }
  return (
    <img
      src={src}
      alt={`${name} logo`}
      className="h-6 w-6 object-contain flex-shrink-0"
      onError={() => setImgError(true)}
    />
  );
}

export default function ServiceCardGrid({ companies, onSelectCompany }: Props) {
  if (companies.length === 0) {
    return <p className="text-gray-500 text-sm">No companies match your filter.</p>;
  }

  return (
    <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {companies.map((company) => {
        const verdict = getLatestVerdict(company);
        const cfg = VERDICT_CONFIG[verdict] ?? VERDICT_CONFIG.Good;
        const latestEntry = company.history?.[company.history.length - 1];

        return (
          <li
            key={company.name}
            className={`relative rounded-lg border shadow-sm cursor-pointer hover:shadow-md transition-shadow ${cfg.bg} ${cfg.border}`}
            onClick={() => onSelectCompany(company)}
          >
            <div className="p-4">
              {/* Header row */}
              <div className="flex items-center gap-2 mb-2 pr-16">
                <CompanyLogo tosUrl={company.tosUrl} name={company.name} />
                <h2 className="text-sm font-semibold truncate">{company.name}</h2>
              </div>

              {/* Verdict badge */}
              <span
                className={`absolute top-3 right-3 rounded-full px-2 py-0.5 text-xs font-medium ${cfg.badge}`}
              >
                {cfg.icon} {verdict}
              </span>

              {/* Category */}
              {company.category && (
                <p className="text-xs text-gray-500 mb-1">{company.category}</p>
              )}

              {/* Latest summary */}
              {company.latestSummary && (
                <p className="text-xs text-gray-600 line-clamp-2 mt-1">
                  {company.latestSummary}
                </p>
              )}

              {/* Last change */}
              {latestEntry && (
                <p className="text-xs text-gray-400 mt-2">
                  Last change: {new Date(latestEntry.timestamp).toLocaleDateString()}
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
          </li>
        );
      })}
    </ul>
  );
}
