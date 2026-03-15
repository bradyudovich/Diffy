import { useEffect, useState, useMemo } from "react";
import { HelmetProvider, Helmet } from "react-helmet-async";
import type { CompanyResult, HistoryEntry, Results } from "./types";
import ServiceCardGrid from "./components/ServiceCardGrid";
import ChangeTimeline from "./components/ChangeTimeline";
import DiffViewer from "./components/DiffViewer";
import DiffViewerErrorBoundary from "./components/DiffViewerErrorBoundary";
import About from "./components/About";
import Leaderboard from "./components/Leaderboard";
import ScoreBreakdownPanel from "./components/ScoreBreakdownPanel";
import TrendChart from "./components/TrendChart";
import {
  parseSummary,
  deriveDataScore,
  deriveUserRightsScore,
  deriveReadabilityScore,
  deriveOverallScore,
  mean,
} from "./utils/scoreUtils";

const RESULTS_URL =
  import.meta.env.DEV
    ? "/Diffy/data/results.json"
    : "https://raw.githubusercontent.com/bradyudovich/Diffy/main/data/results.json";

const CATEGORY_ICONS: Record<string, string> = {
  AI: "🤖",
  Social: "💬",
  Productivity: "⚡",
  Retail: "🛒",
  Streaming: "🎬",
  Services: "🛎️",
  Finance: "💳",
  Auto: "🚘",
  Travel: "✈️",
  Tech: "💻",
};

/** Normalise v1 (legacy) company records to the v2 schema so the UI always
 *  receives a consistent shape regardless of which version of results.json
 *  is loaded from raw.githubusercontent.com. */
function normaliseLegacyCompany(c: CompanyResult): CompanyResult {
  if (Array.isArray(c.history) && c.history.length > 0) return c;

  // V1 record: synthesise a single history entry when the company was "changed"
  const history: HistoryEntry[] = [];
  if (c.changed && c.changeReason) {
    history.push({
      previous_hash: null,
      current_hash: "legacy",
      timestamp: c.lastChecked ?? new Date().toISOString(),
      verdict: "Neutral",
      diffSummary: {
        Privacy: c.summary ?? "",
        DataOwnership: "No significant changes detected",
        UserRights: "No significant changes detected",
      },
      changeIsSubstantial: c.changeIsSubstantial ?? false,
      changeReason: c.changeReason ?? "",
    });
  }
  return { ...c, history, latestSummary: c.latestSummary ?? c.summary };
}

export default function App() {
  const [results, setResults] = useState<Results | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filter / search state
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  // Drill-down state: selected company and selected history entry
  const [selectedCompany, setSelectedCompany] = useState<CompanyResult | null>(null);
  const [selectedEntry, setSelectedEntry] = useState<HistoryEntry | null>(null);

  // About / FAQ page
  const [showAbout, setShowAbout] = useState(false);

  useEffect(() => {
    const url = `${RESULTS_URL}?t=${Date.now()}`;
    console.debug("[DEBUG] Fetching results from:", url);
    fetch(url)
      .then((res) => {
        console.debug("[DEBUG] Response status:", res.status, res.statusText);
        if (!res.ok) throw new Error(`HTTP ${res.status} ${res.statusText}`);
        return res.text();
      })
      .then((text) => {
        console.debug(
          "[DEBUG] Payload length:",
          text.length,
          "| preview:",
          text.slice(0, 120).replace(/\n/g, " ")
        );
        let parsed: Results;
        try {
          parsed = JSON.parse(text) as Results;
        } catch (parseErr) {
          const snippet = text.slice(0, 120).replace(/\n/g, " ");
          console.error("[DEBUG] JSON parse failed:", parseErr, "| snippet:", snippet);
          throw new Error(
            `Failed to parse results (${parseErr instanceof Error ? parseErr.message : String(parseErr)}). ` +
              `Response starts with: ${text.slice(0, 120)}`
          );
        }
        // Normalise legacy v1 records so components always get v2 shape
        parsed.companies = (parsed.companies ?? []).map(normaliseLegacyCompany);
        return parsed;
      })
      .then((data) => {
        setResults(data);
        setLoading(false);
      })
      .catch((err: unknown) => {
        console.error("[DEBUG] Error loading results. URL:", url, "| Error:", err);
        setError(err instanceof Error ? err.message : String(err));
        setLoading(false);
      });
  }, []);

  const categories = results
    ? [...new Set(results.companies.map((c) => c.category).filter(Boolean) as string[])]
    : [];

  const visibleCompanies = results
    ? results.companies.filter((c) => {
        const matchesCategory = !activeCategory || c.category === activeCategory;
        const matchesSearch =
          !searchQuery ||
          c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
          (c.category ?? "").toLowerCase().includes(searchQuery.toLowerCase());
        return matchesCategory && matchesSearch;
      })
    : [];

  /** Aggregate stats derived from current results for the header banner. */
  const globalStats = useMemo(() => {
    if (!results) return null;
    const companies = results.companies;
    const scores = companies.map((c) => {
      if (typeof c.score === "number") return c.score;
      const summary = c.latestSummary ?? c.summary ?? "";
      return summary ? deriveOverallScore(summary) : 75;
    });
    const industryAvg = Math.round(mean(scores));
    const flagged = companies.filter((c) => {
      const s = typeof c.score === "number" ? c.score : deriveOverallScore(c.latestSummary ?? c.summary ?? "");
      return s < 50;
    }).length;
    const totalChanges = companies.reduce((n, c) => n + (c.history?.length ?? 0), 0);
    return { industryAvg, flagged, totalChanges, total: companies.length };
  }, [results]);

  function handleSelectCompany(company: CompanyResult) {
    setSelectedCompany(company);
    // Pre-select the most recent history entry if available
    setSelectedEntry(
      company.history && company.history.length > 0
        ? company.history[company.history.length - 1]
        : null
    );
  }

  function handleShowAbout() {
    setShowAbout(true);
    setSelectedCompany(null);
    setSelectedEntry(null);
  }

  const pageTitle = selectedCompany
    ? `See what changed in ${selectedCompany.name}'s Terms of Service - Diffy`
    : "Diffy – Terms of Service Change Tracker";

  const pageDescription = selectedCompany
    ? `Stay informed about ${selectedCompany.name} Terms of Service updates. Diffy monitors ToS changes and alerts you to high-risk legal terms.`
    : "Diffy monitors Terms of Service changes across popular platforms and alerts you when important policies are updated.";

  return (
    <HelmetProvider>
      <Helmet>
        <title>{pageTitle}</title>
        <meta name="description" content={pageDescription} />
      </Helmet>
      <div className="min-h-screen bg-gray-50 text-gray-900">
      {/* Header */}
      <header className="bg-gradient-to-r from-indigo-700 to-indigo-900 text-white shadow-lg">
        <div className="max-w-6xl mx-auto px-4 py-5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div
                className="h-10 w-10 rounded-xl bg-white/10 border border-white/20 flex items-center justify-center text-xl font-black cursor-pointer select-none"
                onClick={() => { setSelectedCompany(null); setSelectedEntry(null); setShowAbout(false); }}
                title="Home"
              >
                D
              </div>
              <div>
                <h1
                  className="text-2xl font-bold leading-none cursor-pointer hover:text-indigo-200 transition-colors"
                  onClick={() => { setSelectedCompany(null); setSelectedEntry(null); setShowAbout(false); }}
                >
                  Diffy
                </h1>
                <p className="text-indigo-300 text-xs mt-0.5 leading-none">
                  Terms of Service intelligence platform
                </p>
              </div>
            </div>
            <button
              onClick={handleShowAbout}
              className="text-sm text-indigo-200 hover:text-white transition-colors underline-offset-2 hover:underline"
            >
              About / FAQ
            </button>
          </div>

          {/* Stats bar – shown when data is loaded and on the main list view */}
          {globalStats && !selectedCompany && !showAbout && (
            <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="rounded-lg bg-white/10 border border-white/15 px-3 py-2 text-center">
                <p className="text-2xl font-black text-white leading-none">{globalStats.total}</p>
                <p className="text-indigo-300 text-xs mt-0.5">Companies tracked</p>
              </div>
              <div className="rounded-lg bg-white/10 border border-white/15 px-3 py-2 text-center">
                <p className="text-2xl font-black text-white leading-none">{globalStats.industryAvg}</p>
                <p className="text-indigo-300 text-xs mt-0.5">Industry avg score</p>
              </div>
              <div className="rounded-lg bg-white/10 border border-white/15 px-3 py-2 text-center">
                <p className="text-2xl font-black leading-none text-rose-300">{globalStats.flagged}</p>
                <p className="text-indigo-300 text-xs mt-0.5">Companies flagged</p>
              </div>
              <div className="rounded-lg bg-white/10 border border-white/15 px-3 py-2 text-center">
                <p className="text-2xl font-black text-white leading-none">{globalStats.totalChanges}</p>
                <p className="text-indigo-300 text-xs mt-0.5">TOS changes logged</p>
              </div>
            </div>
          )}
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-8">
        {/* About / FAQ page */}
        {showAbout && (
          <About onBack={() => setShowAbout(false)} />
        )}
        {/* Loading */}
        {!showAbout && loading && (
          <div className="flex items-center justify-center py-16 text-indigo-600">
            <svg className="animate-spin h-8 w-8 mr-3" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
            </svg>
            <span className="text-lg font-medium">Loading results…</span>
          </div>
        )}

        {/* Error */}
        {!showAbout && error && (
          <div className="rounded-lg bg-red-50 border border-red-200 p-6 text-red-700">
            <h2 className="text-lg font-semibold mb-1">Error loading data</h2>
            <p className="text-sm">{error}</p>
            <p className="text-xs mt-2 text-red-500">
              Check the browser console for detailed debug output (search for &quot;[DEBUG]&quot;).
            </p>
          </div>
        )}

        {/* Main content: card grid */}
        {!showAbout && results && !selectedCompany && (
          <>
            {results.updatedAt && (
              <p className="text-xs text-gray-500 mb-4">
                Last updated: {new Date(results.updatedAt).toLocaleString()}
                {results.schemaVersion && (
                  <span className="ml-2 text-indigo-400">v{results.schemaVersion}</span>
                )}
              </p>
            )}

            {/* Search */}
            <div className="mb-4">
              <input
                type="text"
                placeholder="Search 500+ company legal updates..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-4 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 font-[Inter,system-ui,sans-serif]"
              />
            </div>

            {/* Category filter bar – horizontally scrollable on mobile */}
            {categories.length > 0 && (
              <div className="flex overflow-x-auto gap-2 mb-6 pb-1 md:flex-wrap md:overflow-x-visible md:pb-0 scrollbar-none">
                {activeCategory && (
                  <button
                    onClick={() => setActiveCategory(null)}
                    className="flex-shrink-0 rounded-full px-4 py-1.5 text-sm font-medium bg-gray-200 text-gray-700 hover:bg-gray-300 transition-colors"
                  >
                    ← All
                  </button>
                )}
                {categories.map((cat) => (
                  <button
                    key={cat}
                    onClick={() => setActiveCategory(activeCategory === cat ? null : cat)}
                    className={`flex-shrink-0 rounded-full px-4 py-1.5 text-sm font-medium transition-colors ${
                      activeCategory === cat
                        ? "bg-indigo-600 text-white"
                        : "bg-white border border-gray-300 text-gray-700 hover:bg-indigo-50"
                    }`}
                  >
                    {CATEGORY_ICONS[cat] ?? "🏢"} {cat}
                  </button>
                ))}
              </div>
            )}

            {/* Two-column layout: card grid + leaderboard sidebar */}
            <div className="grid gap-6 lg:grid-cols-[1fr_220px]">
              <div>
                <ServiceCardGrid
                  companies={visibleCompanies}
                  onSelectCompany={handleSelectCompany}
                />
              </div>
              <Leaderboard
                companies={results.companies}
                onSelectCompany={handleSelectCompany}
              />
            </div>
          </>
        )}

        {/* Company detail view */}
        {!showAbout && results && selectedCompany && (
          <div>
            {/* Back button */}
            <button
              onClick={() => { setSelectedCompany(null); setSelectedEntry(null); }}
              className="mb-4 text-sm text-indigo-600 hover:text-indigo-800 flex items-center gap-1"
            >
              ← Back to all companies
            </button>

            {/* Company header banner */}
            <div className="mb-6 rounded-xl bg-gradient-to-r from-indigo-50 to-purple-50 border border-indigo-100 p-4">
              <div className="flex items-start justify-between gap-4 flex-wrap">
                <div>
                  <h2 className="text-2xl font-bold text-gray-900">{selectedCompany.name}</h2>
                  {selectedCompany.category && (
                    <span className="text-sm text-gray-500 mt-0.5 block">
                      {CATEGORY_ICONS[selectedCompany.category] ?? "🏢"} {selectedCompany.category}
                    </span>
                  )}
                  {selectedCompany.tosUrl && (
                    <a
                      href={selectedCompany.tosUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mt-2 inline-flex items-center gap-1 text-xs text-indigo-600 hover:text-indigo-800 transition-colors"
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
                        className="w-3.5 h-3.5"
                      >
                        <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z" />
                      </svg>
                      View Terms of Service
                    </a>
                  )}
                </div>

                {/* Score breakdown panel for selected company */}
                {(() => {
                  const summaryText = selectedCompany.latestSummary ?? selectedCompany.summary ?? "";
                  const derivedScores = !selectedCompany.scores && summaryText
                    ? {
                        dataPractices: deriveDataScore(summaryText),
                        userRights: deriveUserRightsScore(summaryText),
                        readability: deriveReadabilityScore(summaryText),
                        overall: deriveOverallScore(summaryText),
                      }
                    : undefined;
                  if (!selectedCompany.scores && !derivedScores) return null;
                  return (
                    <div className="w-full sm:w-64">
                      <ScoreBreakdownPanel
                        scores={selectedCompany.scores}
                        derived={derivedScores}
                      />
                    </div>
                  );
                })()}
              </div>

              {/* Score trend chart (if history available) */}
              {selectedCompany.history && selectedCompany.history.length > 1 && (
                <div className="mt-4">
                  <p className="text-xs font-semibold text-indigo-700 mb-1">Score Trend</p>
                  <TrendChart
                    history={selectedCompany.history}
                    width={400}
                    height={72}
                    showLabels
                  />
                </div>
              )}

              {/* Current TOS summary when no history */}
              {(!selectedCompany.history || selectedCompany.history.length === 0) && (selectedCompany.latestSummary || selectedCompany.summary) && (
                <div className="mt-4 rounded-lg border border-indigo-200 bg-white/70 px-4 py-3">
                  <p className="text-xs font-semibold text-indigo-700 uppercase tracking-wide mb-2">
                    📋 Current TOS Summary
                  </p>
                  {(() => {
                    const summaryText = selectedCompany.latestSummary ?? selectedCompany.summary ?? "";
                    const sections = parseSummary(summaryText);
                    const keys = Object.keys(sections);
                    if (keys.length > 0) {
                      return (
                        <dl className="space-y-2">
                          {keys.map((key) => (
                            <div key={key}>
                              <dt className="text-xs font-semibold text-gray-700">{key}</dt>
                              <dd className="text-xs text-gray-600 mt-0.5 leading-relaxed">{sections[key]}</dd>
                            </div>
                          ))}
                        </dl>
                      );
                    }
                    return <p className="text-xs text-gray-600 leading-relaxed">{summaryText}</p>;
                  })()}
                </div>
              )}
            </div>

            <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
              {/* Left: timeline */}
              <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-4">
                <ChangeTimeline
                  companyName={selectedCompany.name}
                  history={selectedCompany.history ?? []}
                  onSelectEntry={setSelectedEntry}
                  selectedEntry={selectedEntry}
                />
              </div>

              {/* Right: diff viewer */}
              <div>
                {selectedEntry ? (
                  <DiffViewerErrorBoundary entry={selectedEntry} tosUrl={selectedCompany.tosUrl}>
                    <DiffViewer
                      entry={selectedEntry}
                      companyName={selectedCompany.name}
                    />
                  </DiffViewerErrorBoundary>
                ) : (
                  <div className="flex flex-col items-center justify-center h-40 text-gray-400 text-sm rounded-xl border border-dashed border-gray-300 gap-2">
                    <span className="text-2xl">📋</span>
                    {(selectedCompany.history?.length ?? 0) === 0
                      ? "No TOS changes have been tracked yet for this company."
                      : "Select a change from the timeline to view details."}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
    </HelmetProvider>
  );
}
