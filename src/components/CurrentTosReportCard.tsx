/**
 * CurrentTosReportCard.tsx – "Current ToS Report Card" panel for the company detail view.
 *
 * Displays a first-class snapshot of a company's current Terms of Service posture
 * so users can understand the key risks without first selecting a change entry:
 *   • currentOverview   – plain-text AI overview (≤30 words)
 *   • currentSummaryPoints – AI key clauses with positive/negative/neutral icons
 *   • currentWatchlistHits – high-risk legal terms found in the live ToS
 *   • Scores breakdown + industry benchmark (via ScoreBreakdownPanel)
 */

import { useState, useId } from "react";
import {
  CheckCircle,
  XCircle,
  Info,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import type { CompanyResult, SummaryPoint } from "../types";
import { getGlossaryDefinition } from "../LegalGlossary";
import ScoreBreakdownPanel from "./ScoreBreakdownPanel";
import { Card, Badge, SectionHeader } from "./ui";

interface Props {
  company: CompanyResult;
}

// ---------------------------------------------------------------------------
// Shared sub-components (styled to match DiffViewer patterns)
// ---------------------------------------------------------------------------

/** Lightweight hover tooltip without external dependencies. */
function Tooltip({ content, children }: { content: string; children: React.ReactNode }) {
  const [visible, setVisible] = useState(false);
  const uid = useId();
  const id = `tos-tt-${uid}`;
  return (
    <span
      className="relative inline-block"
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
      onFocus={() => setVisible(true)}
      onBlur={() => setVisible(false)}
      aria-describedby={visible ? id : undefined}
    >
      {children}
      {visible && (
        <span
          id={id}
          role="tooltip"
          className="pointer-events-none absolute bottom-full left-1/2 z-10 mb-1.5 -translate-x-1/2 w-56 rounded-lg bg-gray-900 px-2.5 py-1.5 text-xs text-white shadow-lg"
        >
          {content}
          <span
            className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-gray-900"
            aria-hidden="true"
          />
        </span>
      )}
    </span>
  );
}

/** Impact icon for a key-clause row. */
function PointIcon({ impact }: { impact: SummaryPoint["impact"] }) {
  if (impact === "positive")
    return (
      <CheckCircle
        className="h-3.5 w-3.5 text-emerald-500 flex-shrink-0 mt-0.5"
        aria-hidden="true"
      />
    );
  if (impact === "negative")
    return (
      <XCircle
        className="h-3.5 w-3.5 text-rose-500 flex-shrink-0 mt-0.5"
        aria-hidden="true"
      />
    );
  return (
    <Info
      className="h-3.5 w-3.5 text-sky-500 flex-shrink-0 mt-0.5"
      aria-hidden="true"
    />
  );
}

/** Expandable key-clause row with optional verbatim quote reveal. */
function ClauseRow({ point }: { point: SummaryPoint }) {
  const [quoteOpen, setQuoteOpen] = useState(false);
  const hasQuote = !!point.quote;

  return (
    <li className="rounded-lg border border-gray-100 bg-white/70 px-3 py-2">
      <button
        type="button"
        className={[
          "flex items-start gap-2 text-left w-full",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-1 rounded",
          hasQuote ? "cursor-pointer" : "cursor-default",
        ].join(" ")}
        onClick={() => hasQuote && setQuoteOpen((v) => !v)}
        aria-expanded={hasQuote ? quoteOpen : undefined}
        disabled={!hasQuote}
      >
        <PointIcon impact={point.impact} />
        <span className="text-xs text-gray-800 leading-snug flex-1">{point.text}</span>
        {hasQuote && (
          <span className="flex-shrink-0 mt-0.5 text-gray-400 hover:text-gray-600 transition-colors">
            {quoteOpen ? (
              <ChevronUp className="h-3.5 w-3.5" aria-hidden="true" />
            ) : (
              <ChevronDown className="h-3.5 w-3.5" aria-hidden="true" />
            )}
          </span>
        )}
      </button>

      {hasQuote && quoteOpen && (
        <blockquote className="mt-2 rounded-md border-l-2 border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900 italic leading-snug">
          "{point.quote}"
        </blockquote>
      )}

      {point.case_id && point.case_id !== "other" && (
        <span className="mt-1 inline-block rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-500 font-mono">
          {point.case_id}
        </span>
      )}
    </li>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function CurrentTosReportCard({ company }: Props) {
  const {
    currentOverview,
    currentSummaryPoints = [],
    currentWatchlistHits = [],
    scores,
    tosUrl,
    tosVersion,
    lastChecked,
  } = company;

  const hasOverview = !!currentOverview;
  const hasClauses = currentSummaryPoints.length > 0;
  const hasFlags = currentWatchlistHits.length > 0;
  const hasScores = !!scores;

  // Nothing to show – caller should gate on hasCurrentTosData() before rendering
  if (!hasOverview && !hasClauses && !hasFlags && !hasScores) return null;

  return (
    <Card testId="current-tos-report-card" className="mb-6">
      <Card.Header
        icon="📋"
        title="Current ToS Report Card"
        subtitle={`Live snapshot of ${company.name}'s current Terms of Service posture`}
      />

      <Card.Body>
        {/* ── Versioning / source attribution ── */}
        {(tosUrl || lastChecked || tosVersion) && (
          <section aria-label="TOS version and source">
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gray-500 bg-gray-50 border border-gray-200 rounded-lg px-3 py-2">
              {tosUrl && (
                <a
                  href={tosUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-indigo-600 hover:text-indigo-800 transition-colors"
                  title="View the Terms of Service document this analysis is based on"
                >
                  📄 View source ToS
                </a>
              )}
              {tosVersion && (
                <span>
                  Version: <strong className="text-gray-700">{tosVersion}</strong>
                </span>
              )}
              {lastChecked && (
                <span>
                  Last analysed:{" "}
                  <strong className="text-gray-700">
                    {new Date(lastChecked).toLocaleDateString(undefined, {
                      year: "numeric",
                      month: "short",
                      day: "numeric",
                    })}
                  </strong>
                </span>
              )}
            </div>
          </section>
        )}
        {/* ── Overview ── */}
        {hasOverview && (
          <section aria-label="Overview">
            <SectionHeader icon="🔍" label="Overview" />
            <p className="text-sm text-gray-800 leading-relaxed bg-white/80 rounded-lg border border-gray-100 px-3 py-2">
              {currentOverview}
            </p>
          </section>
        )}

        {/* ── Key Clauses ── */}
        {hasClauses && (
          <section aria-label="Key Clauses">
            <SectionHeader icon="📌" label="Key Clauses" />
            {/* Impact legend */}
            <div className="flex items-center gap-3 mb-2 text-[10px] text-gray-400">
              <span className="flex items-center gap-1">
                <CheckCircle className="h-3 w-3 text-emerald-500" aria-hidden="true" />
                Positive
              </span>
              <span className="flex items-center gap-1">
                <XCircle className="h-3 w-3 text-rose-500" aria-hidden="true" />
                Negative
              </span>
              <span className="flex items-center gap-1">
                <Info className="h-3 w-3 text-sky-500" aria-hidden="true" />
                Neutral
              </span>
            </div>
            <ul className="space-y-2">
              {currentSummaryPoints.map((point, i) => (
                <ClauseRow key={`${point.case_id ?? "point"}-${i}`} point={point} />
              ))}
            </ul>
          </section>
        )}

        {/* ── Watchlist Flags ── */}
        {hasFlags && (
          <section aria-label="Watchlist Flags">
            <SectionHeader icon="⚠️" label="Watchlist Flags" />
            <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2">
              <p className="text-xs text-amber-700 mb-1.5">
                High-risk terms found in the currently-live ToS:
              </p>
              <div className="flex flex-wrap gap-1.5">
                {currentWatchlistHits.map((term) => {
                  const definition = getGlossaryDefinition(term);
                  const badge = (
                    <Badge key={term} intent="warning" className="cursor-help">
                      {term}
                    </Badge>
                  );
                  return definition ? (
                    <Tooltip key={term} content={definition}>
                      {badge}
                    </Tooltip>
                  ) : (
                    badge
                  );
                })}
              </div>
            </div>
          </section>
        )}

        {/* ── Scores Breakdown + Benchmark ── */}
        {hasScores && (
          <section aria-label="Score Breakdown">
            <ScoreBreakdownPanel scores={scores} />
          </section>
        )}
      </Card.Body>
    </Card>
  );
}
