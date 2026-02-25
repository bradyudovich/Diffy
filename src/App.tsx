import { useEffect, useState } from "react";

interface CompanyResult {
  name: string;
  category?: string;
  tosUrl: string;
  lastChecked?: string;
  changed?: boolean;
  summary?: string;
}

interface Results {
  updatedAt?: string;
  companies: CompanyResult[];
}

const RESULTS_URL =
  "https://raw.githubusercontent.com/bradyudovich/Diffy/main/data/results.json";

const HUNTER_LOGO_BASE = "https://hunter.io/api/logo?domain=";

function getLogoUrl(tosUrl: string): string {
  try {
    const { hostname } = new URL(tosUrl);
    // Strip leading "www." so hunter.io returns the root-domain logo
    const domain = hostname.replace(/^www\./, "");
    return `${HUNTER_LOGO_BASE}${domain}`;
  } catch {
    return "";
  }
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

  useEffect(() => {
    const url = `${RESULTS_URL}?t=${Date.now()}`;
    fetch(url)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json() as Promise<Results>;
      })
      .then((data) => {
        setResults(data);
        setLoading(false);
      })
      .catch((err: unknown) => {
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
                    className={`relative rounded-lg border shadow-sm ${
                      company.changed
                        ? "border-yellow-400 bg-yellow-50"
                        : "border-gray-200 bg-white"
                    }`}
                    style={{ padding: "1.25rem" }}
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

                    {/* Card content – right padding ensures text doesn't overlap badge */}
                    <div className="pr-28" style={{ minWidth: 0 }}>
                      <div className="flex items-center gap-3 mb-1">
                        {getLogoUrl(company.tosUrl) && (
                          <img
                            src={getLogoUrl(company.tosUrl)}
                            alt={`${company.name} logo`}
                            className="h-6 w-6 object-contain flex-shrink-0"
                            onError={(e) => {
                              (e.currentTarget as HTMLImageElement).style.display = "none";
                            }}
                          />
                        )}
                        <h2 className="text-lg font-semibold">{company.name}</h2>
                      </div>
                      {company.category && (
                        <span className="inline-block text-xs text-indigo-600 font-medium mb-1">
                          {CATEGORY_ICONS[company.category] ?? "🏢"}{" "}
                          {company.category}
                        </span>
                      )}
                      <a
                        href={company.tosUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="block text-sm text-indigo-600 hover:underline break-all"
                      >
                        {company.tosUrl}
                      </a>
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
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </main>
    </div>
  );
}
