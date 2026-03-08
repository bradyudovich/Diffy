/**
 * LegalGlossary.ts – Plain-English definitions for high-risk legal terms
 * tracked in watchlist.json.
 */

export const LEGAL_GLOSSARY: Record<string, string> = {
  Arbitration:
    "You cannot sue this company in court; disputes must be resolved through a private arbitration process, often limiting your legal options.",
  "Class Action":
    "You waive your right to join with other users in a collective lawsuit against the company.",
  "Sub-processor":
    "Third-party companies that the service shares your data with to provide its features.",
  Biometric:
    "The company may collect uniquely identifying physical data such as fingerprints, face scans, or voice prints.",
  Mandatory:
    "Certain terms are non-negotiable; you must accept them to use the service.",
  Waiver:
    "You give up specific legal rights that would otherwise protect you as a user or consumer.",
  Indemnify:
    "You agree to compensate the company for costs or damages that arise from your use of the service.",
  Surveillance:
    "The company may monitor your activity, communications, or behaviour on or off the platform.",
  Tracking:
    "The company tracks your behaviour, location, or device across sessions and possibly across other sites.",
  Sell:
    "The company may sell your personal data or usage information to third parties.",
  "Third Party":
    "Your data or content may be shared with or accessible by external companies or services.",
  Retention:
    "The company keeps your data for a defined (or indefinite) period, even after you delete your account.",
  Profiling:
    "The company builds a detailed profile about you based on your behaviour, preferences, or demographics.",
};

/**
 * Look up the plain-English definition for a watchlist term.
 * Returns `undefined` if the term is not in the glossary.
 */
export function getGlossaryDefinition(term: string): string | undefined {
  // Exact match first
  if (term in LEGAL_GLOSSARY) return LEGAL_GLOSSARY[term];
  // Case-insensitive fallback
  const lower = term.toLowerCase();
  for (const [key, def] of Object.entries(LEGAL_GLOSSARY)) {
    if (key.toLowerCase() === lower) return def;
  }
  return undefined;
}
