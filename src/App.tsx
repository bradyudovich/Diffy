import { useEffect, useState } from "react";

interface CompanyResult {
  name: string;
  category?: string;
  tosUrl: string;
  lastChecked?: string;
  changed?: boolean;
  changeIsSubstantial?: boolean;
  summary?: string;
}

interface Results {
  updatedAt?: string;
  companies: CompanyResult[];
}

const RESULTS_URL =
  "https://raw.githubusercontent.com/bradyudovich/Diffy/main/data/results.json";

const GOOGLE_FAVICON_BASE = "https://www.google.com/s2/favicons?sz=32&domain=";

function getLogoUrl(tosUrl: string): string {
  try {
    const { hostname } = new URL(tosUrl);
    const domain = hostname.replace(/^www\./, "");
    return `${GOOGLE_FAVICON_BASE}${domain}`;
  } catch {
    return "";
  }
}

function CompanyLogo({ tosUrl, name }: { tosUrl: string; name: string }) {
  const [imgError, setImgError] = useState(false);
  const src = getLogoUrl(tosUrl);
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

export default function App() {
  const [results, setResults] = useState<Results | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCompany, setSelectedCompany] = useState<CompanyResult | null>(null);

  useEffect(() => {
    const url = `${RESULTS_URL}?t=${Date.now()}`;
    // DEBUG: log the URL being fetched to confirm the correct endpoint is used.
    // Remove this log once the "string did not match expected pattern" error is resolved.
    console.debug("[DEBUG] Fetching results from:", url);
    fetch(url)
      .then((res) => {
        // DEBUG: log response status to distinguish network failures from parse errors.
        console.debug("[DEBUG] Response status:", res.status, res.statusText);
        if (!res.ok) throw new Error(`HTTP ${res.status} ${res.statusText}`);
        // Read as text first so we can inspect the raw payload if JSON parsing fails.
        return res.text();
      })
      .then((text) => {
        // DEBUG: log payload size and a short preview to help spot truncated or
        // HTML error pages being returned instead of valid JSON.
        // Remove this block once the root cause has been confirmed.
        console.debug(
          "[DEBUG] Response payload length:",
          text.length,
          "| preview:",
          text.slice(0, 120).replace(/\n/g, " ")
        );
        let parsed: Results;
        try {
          parsed = JSON.parse(text) as Results;
        } catch (parseErr) {
          // DEBUG: surface the raw parse error and a snippet of the response body
          // so developers can identify malformed JSON without needing devtools.
          const snippet = text.slice(0, 120).replace(/\n/g, " ");
          console.error(
            "[DEBUG] JSON parse failed. Error:",
            parseErr,
            "| Response snippet:",
            snippet
          );
          throw new Error(
            `Failed to parse results (${parseErr instanceof Error ? parseErr.message : String(parseErr)}). ` +
              `Response starts with: ${text.slice(0, 120)}`
          );
        }
        return parsed;
      })
      .then((data) => {
        setResults(data);
        setLoading(false);
      })
      .catch((err: unknown) => {
        // DEBUG: log the full error object for additional context in the console.
        // Remove this log once the issue is resolved.
        console.error("[DEBUG] Error loading results data. URL:", url, "| Error:", err);
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

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900">
      <header className="bg-indigo-700 text-white py-6 shadow">
        <div className="max-w-4xl mx-auto px-4">
          <h1 className="text-3xl font-bold">Diffy</h1>
          <p className="mt-1 text-indigo-200 text-sm">
            Terms of Service change tracker
          </p>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-8">
        {loading && (
          <div className="flex items-center justify-center py-16 text-indigo-600">
            <svg
              className="animate-spin h-8 w-8 mr-3"
              viewBox="0 0 24 24"
              fill="none"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8v8z"
              />
            </svg>
            <span className="text-lg font-medium">Loading results…</span>
          </div>
        )}

        {error && (
          <div className="rounded-lg bg-red-50 border border-red-200 p-6 text-red-700">
            <h2 className="text-lg font-semibold mb-1">Error loading data</h2>
            <p className="text-sm">{error}</p>
            {/* DEBUG: hint to guide developers toward the browser console for details. */}
            {/* Remove this paragraph once the root cause has been confirmed and fixed. */}
            <p className="text-xs mt-2 text-red-500">
              Check the browser console for detailed debug output (search for
              &quot;[DEBUG]&quot;).
            </p>
          </div>
        )}

        {results && (
          <>
            {results.updatedAt && (
              <p className="text-xs text-gray-500 mb-4">
                Last updated:{" "}
                {new Date(results.updatedAt).toLocaleString()}
              </p>
            )}

            {/* Search input */}
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
                    ← Back to All
                  </button>
                )}
                {categories.map((cat) => (
                  <button
                    key={cat}
                    onClick={() =>
                      setActiveCategory(activeCategory === cat ? null : cat)
                    }
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

            {visibleCompanies.length === 0 ? (
              <p className="text-gray-500">No results yet.</p>
            ) : (
              <ul className="space-y-4">
                {visibleCompanies.map((company) => (
                  <li
                    key={company.name}
                    className={`relative rounded-lg border shadow-sm cursor-pointer hover:shadow-md transition-shadow ${
                      company.changed
                        ? "border-yellow-400 bg-yellow-50"
                        : "border-gray-200 bg-white"
                    }`}
                    style={{ padding: "1.25rem" }}
                    onClick={() => setSelectedCompany(company)}
                  >
                    {/* Badge absolutely positioned at top-right */}
                    <span
                      className={`absolute top-4 right-4 rounded-full px-3 py-1 text-xs font-medium ${
                        company.changed
                          ? "bg-yellow-200 text-yellow-800"
                          : "bg-green-100 text-green-700"
                      }`}
                    >
                      {company.changed ? "Changed" : "No change"}
                    </span>

                    {/* Card content */}
                    <div style={{ minWidth: 0 }}>
                      <div className="flex items-center gap-3 mb-1 pr-24 sm:pr-28">
                        <CompanyLogo tosUrl={company.tosUrl} name={company.name} />
                        <h2 className="text-lg font-semibold">{company.name}</h2>
                      </div>
                      {company.summary && (
                        <p className="mt-2 text-sm text-gray-700">
                          {company.summary}
                        </p>
                      )}
                      {company.lastChecked && (
                        <p className="mt-1 text-xs text-gray-400">
                          Checked:{" "}
                          {new Date(company.lastChecked).toLocaleString()}
                        </p>
                      )}
                    </div>

                    {/* Folder icon – lower right corner, links to ToS */}
                    {company.tosUrl && (
                      <a
                        href={company.tosUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="absolute bottom-4 right-4 text-gray-500 hover:text-gray-900 transition-colors"
                        onClick={(e) => e.stopPropagation()}
                        aria-label="View full Terms of Service"
                        title="View full Terms of Service"
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="w-6 h-6">
                          <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z"/>
                        </svg>
                      </a>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </main>

      {/* Company summary modal */}
      {selectedCompany && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
          onClick={() => setSelectedCompany(null)}
        >
          <div
            className="bg-white rounded-xl shadow-xl max-w-lg w-full mx-4 p-6 relative"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-3 mb-4">
              <CompanyLogo tosUrl={selectedCompany.tosUrl} name={selectedCompany.name} />
              <h2 className="text-xl font-bold">{selectedCompany.name}</h2>
              <button
                className="ml-auto text-gray-400 hover:text-gray-600 text-xl leading-none"
                onClick={() => setSelectedCompany(null)}
                aria-label="Close"
              >
                ✕
              </button>
            </div>
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
              Privacy & AI Risk Flags
            </h3>
            {selectedCompany.summary ? (
              <div className="text-gray-700 text-sm leading-relaxed space-y-1">
                {selectedCompany.summary
                  .split("\n")
                  .filter((line) => line.trim())
                  .map((line, i) => (
                    <p key={i}>{line}</p>
                  ))}
              </div>
            ) : (
              <p className="text-gray-500 text-sm italic">No summary available.</p>
            )}
            {selectedCompany.tosUrl && (
              <div className="mt-6 pt-4 border-t border-gray-100 flex justify-end">
                <a
                  href={selectedCompany.tosUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-gray-500 hover:text-gray-900 transition-colors"
                  onClick={(e) => e.stopPropagation()}
                  aria-label="View full Terms of Service"
                  title="View full Terms of Service"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="w-6 h-6">
                    <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z"/>
                  </svg>
                </a>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
