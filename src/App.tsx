import { useEffect, useState } from "react";
import type { CompanyResult, HistoryEntry, Results } from "./types";
import ServiceCardGrid from "./components/ServiceCardGrid";
import ChangeTimeline from "./components/ChangeTimeline";
import DiffViewer from "./components/DiffViewer";

const RESULTS_URL =
  "https://raw.githubusercontent.com/bradyudovich/Diffy/main/data/results.json";

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

  function handleSelectCompany(company: CompanyResult) {
    setSelectedCompany(company);
    // Pre-select the most recent history entry if available
    setSelectedEntry(
      company.history && company.history.length > 0
        ? company.history[company.history.length - 1]
        : null
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900">
      {/* Header */}
      <header className="bg-indigo-700 text-white py-6 shadow">
        <div className="max-w-6xl mx-auto px-4">
          <h1 className="text-3xl font-bold">Diffy</h1>
          <p className="mt-1 text-indigo-200 text-sm">
            Terms of Service change tracker
          </p>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-8">
        {/* Loading */}
        {loading && (
          <div className="flex items-center justify-center py-16 text-indigo-600">
            <svg className="animate-spin h-8 w-8 mr-3" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
            </svg>
            <span className="text-lg font-medium">Loading results…</span>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="rounded-lg bg-red-50 border border-red-200 p-6 text-red-700">
            <h2 className="text-lg font-semibold mb-1">Error loading data</h2>
            <p className="text-sm">{error}</p>
            <p className="text-xs mt-2 text-red-500">
              Check the browser console for detailed debug output (search for &quot;[DEBUG]&quot;).
            </p>
          </div>
        )}

        {/* Main content: card grid */}
        {results && !selectedCompany && (
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
                placeholder="Search companies…"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-4 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>

            {/* Category filter bar */}
            {categories.length > 0 && (
              <div className="flex flex-wrap gap-2 mb-6">
                {activeCategory && (
                  <button
                    onClick={() => setActiveCategory(null)}
                    className="rounded-full px-4 py-1.5 text-sm font-medium bg-gray-200 text-gray-700 hover:bg-gray-300 transition-colors"
                  >
                    ← All
                  </button>
                )}
                {categories.map((cat) => (
                  <button
                    key={cat}
                    onClick={() => setActiveCategory(activeCategory === cat ? null : cat)}
                    className={`rounded-full px-4 py-1.5 text-sm font-medium transition-colors ${
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

            {/* Service Card Grid */}
            <ServiceCardGrid
              companies={visibleCompanies}
              onSelectCompany={handleSelectCompany}
            />
          </>
        )}

        {/* Company detail view */}
        {results && selectedCompany && (
          <div>
            {/* Back button */}
            <button
              onClick={() => { setSelectedCompany(null); setSelectedEntry(null); }}
              className="mb-4 text-sm text-indigo-600 hover:text-indigo-800 flex items-center gap-1"
            >
              ← Back to all companies
            </button>

            <div className="mb-4 flex items-center gap-2">
              <h2 className="text-xl font-bold">{selectedCompany.name}</h2>
              {selectedCompany.category && (
                <span className="text-sm text-gray-500">
                  {CATEGORY_ICONS[selectedCompany.category] ?? "🏢"} {selectedCompany.category}
                </span>
              )}
              {selectedCompany.tosUrl && (
                <a
                  href={selectedCompany.tosUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="ml-auto text-gray-400 hover:text-gray-700 transition-colors"
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
                    className="w-5 h-5"
                  >
                    <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z" />
                  </svg>
                </a>
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
                  <DiffViewer
                    entry={selectedEntry}
                    companyName={selectedCompany.name}
                  />
                ) : (
                  <div className="flex items-center justify-center h-40 text-gray-400 text-sm rounded-xl border border-dashed border-gray-300">
                    Select a change from the timeline to view details.
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
