/** Verdict for a ToS change entry. */
export type Verdict = "Good" | "Neutral" | "Caution";

/** Impact level for a summary point. */
export type PointImpact = "positive" | "negative" | "neutral";

/** Multi-dimensional scoring breakdown for a company. */
export interface DiversifiedScores {
  /** Overall Diffy score (0–100), same as the top-level `score` field. */
  overall: number;
  /** Data handling quality score (0–100), based on Privacy and DataOwnership cases. */
  dataPractices: number;
  /** User rights protection score (0–100), based on UserRights cases. */
  userRights: number;
  /** Clarity / user-friendliness score (0–100), derived from the ratio of positive
   *  to negative summary points. */
  readability: number;
  /** Qualitative comparison to the industry average (e.g. "Top Tier", "Average"). */
  benchmarkRank?: string;
  /** Industry-average overall score across all tracked companies. */
  industryAvg?: number;
}

/** A single actionable point from the AI analysis. */
export interface SummaryPoint {
  text: string;
  impact: PointImpact;
  /** Standardized case identifier from cases.json (e.g. "data-training"). */
  case_id?: string;
  /** Verbatim quote from the ToS text that supports this point. */
  quote?: string;
}

/** Structured AI breakdown of a change, keyed by legal category. */
export interface DiffSummary {
  Privacy: string;
  DataOwnership: string;
  UserRights: string;
}

/** One entry in a company's version history. */
export interface HistoryEntry {
  previous_hash: string | null;
  current_hash: string;
  timestamp: string;
  verdict: Verdict;
  diffSummary: DiffSummary;
  changeIsSubstantial: boolean;
  changeReason: string;
  /** Percentage of text that changed (0.0–100.0), e.g. 14.2 for 14.2% difference. */
  changeMagnitude?: number;
  /** High-risk legal terms found in the diff text. */
  watchlist_hits?: string[];
  /** Trust score (0–100) computed from verdict and watchlist hits. */
  trustScore?: number;
  /** Letter grade derived from trustScore (A/B/C/D/F). */
  letterGrade?: string;
  /** Array of AI-generated summary points with impact labels. */
  summaryPoints?: SummaryPoint[];
}

/** Per-company result from the scanner, v2 schema. */
export interface CompanyResult {
  name: string;
  category?: string;
  tosUrl: string;
  lastChecked?: string;
  /** Plain-text summary of the most recent change (backward compat). */
  latestSummary?: string;
  /** Array of AI-generated summary points for the most recent change. */
  summaryPoints?: SummaryPoint[];
  /** Chronological history of all substantive changes. */
  history: HistoryEntry[];
  /**
   * Diffy score (0–100) derived from the latest history entry.
   * Computed by calculate_score() in scraper/monitor.py.
   */
  score?: number;
  /**
   * Multi-dimensional scoring breakdown.
   * Computed by calculate_diversified_scores() in scraper/monitor.py.
   */
  scores?: DiversifiedScores;
  /** Relative URL to the cached favicon, e.g. "/favicons/openai.com.png". */
  favicon_url?: string;

  // Legacy v1 fields kept for backward compat when loading old data
  changed?: boolean;
  changeIsSubstantial?: boolean;
  changeReason?: string;
  summary?: string;
}

/** Top-level results.json structure. */
export interface Results {
  schemaVersion?: string;
  updatedAt?: string;
  companies: CompanyResult[];
}
