/**
 * MissingTosSection.tsx – Displays companies that lack TOS tracking data.
 *
 * Shows a clearly-labelled "Missing TOS Data" section on the main dashboard
 * when one or more companies have no history entries and no current AI summary.
 * Explains why these companies are separated and how users can help fill gaps.
 */

import { AlertTriangle, ExternalLink, Clock } from "lucide-react";
import type { CompanyResult } from "../types";

interface Props {
  companies: CompanyResult[];
}

export default function MissingTosSection({ companies }: Props) {
  if (companies.length === 0) return null;

  return (
    <section aria-labelledby="missing-tos-heading" className="mt-10">
      {/* Section header */}
      <div className="mb-4 rounded-xl bg-amber-50 border border-amber-200 px-4 py-3 flex items-start gap-3">
        <AlertTriangle
          className="h-5 w-5 text-amber-500 shrink-0 mt-0.5"
          aria-hidden="true"
        />
        <div>
          <h2
            id="missing-tos-heading"
            className="text-sm font-semibold text-amber-800"
          >
            Missing TOS Data ({companies.length}{" "}
            {companies.length === 1 ? "company" : "companies"})
          </h2>
          <p className="text-xs text-amber-700 mt-1 leading-relaxed">
            The companies below have a Terms of Service URL on record but
            Diffy hasn't yet captured a successful analysis (no change history
            and no current AI summary). This can happen when the page requires
            authentication, blocks automated access, or was added to the
            watchlist after the most recent scraper run. They are listed here
            for transparency — click the link to read their ToS directly.
          </p>
          <p className="text-xs text-amber-600 mt-1">
            You can help fill these gaps by{" "}
            <a
              href="https://github.com/bradyudovich/Diffy/issues/new?labels=missing-tos&template=missing_tos.md"
              target="_blank"
              rel="noopener noreferrer"
              className="underline hover:text-amber-800 transition-colors"
            >
              opening a GitHub issue
            </a>{" "}
            with the correct ToS URL.
          </p>
        </div>
      </div>

      {/* Company list */}
      <ul
        className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3"
        aria-label="Companies with missing TOS data"
      >
        {companies.map((company) => (
          <li
            key={company.name}
            className="rounded-xl border border-amber-200 bg-white px-4 py-3 shadow-sm flex flex-col gap-1.5"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="font-semibold text-sm text-gray-800 truncate">
                {company.name}
              </span>
              {company.category && (
                <span className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded-full shrink-0">
                  {company.category}
                </span>
              )}
            </div>

            {company.tosUrl && (
              <a
                href={company.tosUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-xs text-indigo-600 hover:text-indigo-800 transition-colors truncate"
                title={company.tosUrl}
              >
                <ExternalLink className="h-3 w-3 shrink-0" aria-hidden="true" />
                <span className="truncate">View Terms of Service</span>
              </a>
            )}

            {company.lastChecked ? (
              <p className="flex items-center gap-1 text-xs text-gray-400">
                <Clock className="h-3 w-3 shrink-0" aria-hidden="true" />
                Last checked:{" "}
                {new Date(company.lastChecked).toLocaleDateString(undefined, {
                  year: "numeric",
                  month: "short",
                  day: "numeric",
                })}
              </p>
            ) : (
              <p className="text-xs text-gray-400 italic">Never checked</p>
            )}

            <span
              className="inline-flex items-center gap-1 text-xs text-amber-700 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-full w-fit"
              aria-label="No TOS analysis available"
            >
              <AlertTriangle className="h-3 w-3 shrink-0" aria-hidden="true" />
              No analysis available
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
