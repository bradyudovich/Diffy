/** Verdict for a ToS change entry. */
export type Verdict = "Good" | "Neutral" | "Caution";

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
}

/** Per-company result from the scanner, v2 schema. */
export interface CompanyResult {
  name: string;
  category?: string;
  tosUrl: string;
  lastChecked?: string;
  /** Plain-text summary of the most recent change (backward compat). */
  latestSummary?: string;
  /** Chronological history of all substantive changes. */
  history: HistoryEntry[];

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
