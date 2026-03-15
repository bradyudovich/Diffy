/**
 * scoreUtils.ts – Utilities for parsing TOS summaries and deriving
 * multi-dimensional risk scores from text content.
 *
 * Used when the backend hasn't yet produced a structured `scores` object
 * (legacy v1 data) so the UI can still surface meaningful information.
 */

import type { CompanyResult } from "../types";

/** Parsed sections from a "[Category]: text" summary string. */
export type ParsedSummary = Record<string, string>;

/**
 * Parse the "[Category]: text" format used by the legacy summary field.
 * Returns an object keyed by category name.
 *
 * @example
 * parseSummary("[Data Rights]: Users retain ownership. [AI Usage]: Outputs may be inaccurate.")
 * // → { "Data Rights": "Users retain ownership.", "AI Usage": "Outputs may be inaccurate." }
 */
export function parseSummary(summary: string): ParsedSummary {
  if (!summary) return {};
  const result: ParsedSummary = {};
  const regex = /\[([^\]]+)\]:\s*([\s\S]*?)(?=\[|$)/g;
  let match;
  while ((match = regex.exec(summary)) !== null) {
    const key = match[1].trim();
    const value = match[2].replace(/\s+/g, " ").trim();
    if (key && value) {
      result[key] = value;
    }
  }
  return result;
}

/** Terms that suggest poor data practices (lower score). */
const DATA_NEGATIVE_TERMS = [
  "sell",
  "selling",
  "third party",
  "third-party",
  "share personal",
  "collect",
  "surveillance",
  "biometric",
  "transfer",
  "monetize",
  "advertising",
  "ads",
];

/** Terms that suggest good data practices (raise score). */
const DATA_POSITIVE_TERMS = [
  "retain ownership",
  "not sell",
  "no sell",
  "opt-out",
  "opt out",
  "transparent",
  "anonymized",
  "encrypted",
  "delete",
];

/** Terms that signal weakened user rights (lower score). */
const RIGHTS_NEGATIVE_TERMS = [
  "arbitration",
  "class action",
  "waive",
  "mandatory",
  "indemnify",
  "liability limited",
  "no liability",
  "hold harmless",
  "forfeit",
];

/** Terms that signal strong user rights (raise score). */
const RIGHTS_POSITIVE_TERMS = [
  "user rights",
  "users retain",
  "users own",
  "right to delete",
  "gdpr",
  "ccpa",
  "opt out",
  "appeal",
];

function countTerms(text: string, terms: string[]): number {
  const lower = text.toLowerCase();
  return terms.reduce((n, term) => n + (lower.includes(term) ? 1 : 0), 0);
}

/**
 * Derive a 0–100 data practices score from summary text.
 * Starts at 75, subtracts for negative signals, adds for positive ones.
 */
export function deriveDataScore(text: string): number {
  if (!text) return 75;
  const neg = countTerms(text, DATA_NEGATIVE_TERMS);
  const pos = countTerms(text, DATA_POSITIVE_TERMS);
  return Math.max(10, Math.min(100, 75 - neg * 7 + pos * 5));
}

/**
 * Derive a 0–100 user rights score from summary text.
 */
export function deriveUserRightsScore(text: string): number {
  if (!text) return 75;
  const neg = countTerms(text, RIGHTS_NEGATIVE_TERMS);
  const pos = countTerms(text, RIGHTS_POSITIVE_TERMS);
  return Math.max(10, Math.min(100, 75 - neg * 10 + pos * 5));
}

/**
 * Derive a simple readability / clarity score.
 * Shorter sentences and fewer legalese markers → higher score.
 */
export function deriveReadabilityScore(text: string): number {
  if (!text) return 70;
  const legalese = [
    "notwithstanding",
    "hereinafter",
    "indemnification",
    "pursuant",
    "aforementioned",
    "thereto",
    "hereof",
    "whereas",
  ];
  const hits = countTerms(text, legalese);
  // Prefer shorter summaries (more concise = clearer)
  const lengthPenalty = Math.min(20, Math.floor(text.length / 200));
  return Math.max(10, Math.min(100, 80 - hits * 8 - lengthPenalty));
}

/**
 * Derive an overall score from the full summary string, combining the
 * three dimension sub-scores with equal weight.
 */
export function deriveOverallScore(summary: string): number {
  const d = deriveDataScore(summary);
  const r = deriveUserRightsScore(summary);
  const c = deriveReadabilityScore(summary);
  return Math.round((d + r + c) / 3);
}

/** Return a qualitative rank label relative to an industry average. */
export function benchmarkLabel(score: number, industryAvg: number): string {
  if (score >= industryAvg + 15) return "Top Tier";
  if (score >= industryAvg + 5) return "Above Average";
  if (score >= industryAvg - 5) return "Average";
  if (score >= industryAvg - 15) return "Below Average";
  return "Needs Improvement";
}

/** Compute the mean score across an array of numeric values. */
export function mean(values: number[]): number {
  if (values.length === 0) return 0;
  return values.reduce((s, v) => s + v, 0) / values.length;
}

/**
 * Returns true when the company has at least one "current ToS" field so the
 * CurrentTosReportCard has something to render.
 */
export function hasCurrentTosData(company: CompanyResult): boolean {
  return !!(
    company.currentOverview ||
    (company.currentSummaryPoints && company.currentSummaryPoints.length > 0) ||
    (company.currentWatchlistHits && company.currentWatchlistHits.length > 0) ||
    company.scores
  );
}

/**
 * Returns true when the company is considered to be missing meaningful TOS
 * tracking data: no history entries have been captured AND no current AI
 * summary is available.  These companies are shown in a distinct
 * "Missing TOS Data" section instead of the main card grid.
 */
export function hasMissingTosData(company: CompanyResult): boolean {
  const hasHistory = Array.isArray(company.history) && company.history.length > 0;
  const hasCurrent = !!(
    company.currentOverview ||
    (company.currentSummaryPoints && company.currentSummaryPoints.length > 0)
  );
  return !hasHistory && !hasCurrent;
}

/**
 * Returns a structured description of the scoring methodology used by Diffy.
 * This is the single source of truth referenced by the HowRatingsModal.
 */
export function getRatingMethodology() {
  return {
    dimensions: [
      {
        name: "Data Practices",
        weight: "1/3",
        description:
          "Measures how a company handles your personal data. Penalises terms like 'sell', 'third-party sharing', 'surveillance', and 'biometric'. Rewards terms like 'retain ownership', 'not sell', 'opt-out', and 'encrypted'.",
        baseScore: 75,
        negativeAdjustment: -7,
        positiveAdjustment: +5,
      },
      {
        name: "User Rights",
        weight: "1/3",
        description:
          "Measures how well user rights are protected. Penalises forced arbitration, class-action waivers, and indemnification clauses. Rewards GDPR/CCPA compliance, right-to-delete provisions, and appeal mechanisms.",
        baseScore: 75,
        negativeAdjustment: -10,
        positiveAdjustment: +5,
      },
      {
        name: "Readability",
        weight: "1/3",
        description:
          "Measures how plain-English and concise the ToS document is. Penalises legalese words ('notwithstanding', 'hereinafter', 'pursuant', etc.) and length.",
        baseScore: 80,
        negativeAdjustment: -8,
        positiveAdjustment: 0,
      },
    ],
    grades: [
      { grade: "A", range: "90–100", label: "Excellent", color: "emerald" },
      { grade: "B", range: "70–89",  label: "Good",      color: "teal" },
      { grade: "C", range: "50–69",  label: "Fair",      color: "amber" },
      { grade: "D", range: "30–49",  label: "Poor",      color: "orange" },
      { grade: "E", range: "0–29",   label: "Very Poor", color: "rose" },
    ],
    notes: [
      "Scores are derived from AI-generated summary points or, for legacy data, from keyword analysis of the plain-text summary.",
      "The overall score is the unweighted average of the three dimension scores.",
      "Scores are not legal advice. They are automated estimates for informational purposes only.",
      "Source data comes from Diffy's automated scraper which monitors each company's ToS URL daily.",
    ],
  };
}
