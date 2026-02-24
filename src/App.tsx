import { useEffect, useState } from "react";

interface CompanyResult {
  name: string;
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

export default function App() {
  const [results, setResults] = useState<Results | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
            {results.companies.length === 0 ? (
              <p className="text-gray-500">No results yet.</p>
            ) : (
              <ul className="space-y-4">
                {results.companies.map((company) => (
                  <li
                    key={company.name}
                    className={`rounded-lg border p-5 shadow-sm ${
                      company.changed
                        ? "border-yellow-400 bg-yellow-50"
                        : "border-gray-200 bg-white"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <h2 className="text-lg font-semibold">
                          {company.name}
                        </h2>
                        <a
                          href={company.tosUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm text-indigo-600 hover:underline break-all"
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
                      <span
                        className={`shrink-0 rounded-full px-3 py-1 text-xs font-medium ${
                          company.changed
                            ? "bg-yellow-200 text-yellow-800"
                            : "bg-green-100 text-green-700"
                        }`}
                      >
                        {company.changed ? "Changed" : "No change"}
                      </span>
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
