/**
 * scoreUtils.ts – Utilities for parsing TOS summaries and deriving
 * multi-dimensional risk scores from text content.
 *
 * Used when the backend hasn't yet produced a structured `scores` object
 * (legacy v1 data) so the UI can still surface meaningful information.
 */

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
