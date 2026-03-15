/**
 * About.tsx – FAQ / About page explaining Diffy's features and data.
 */

interface FaqItem {
  question: string;
  answer: string;
}

const FAQ_ITEMS: FaqItem[] = [
  {
    question: "What is Diffy?",
    answer:
      "Diffy is an open-source tool that automatically monitors Terms of Service (ToS) documents for popular online services. When a company changes its ToS, Diffy detects the change, summarises it using AI, and flags any high-risk legal terms so you can stay informed without reading thousands of words of legalese.",
  },
  {
    question: "How current is this data?",
    answer:
      "The scanner runs every day at midnight UTC via a scheduled GitHub Actions workflow. Each company's ToS page is fetched with a real browser (Playwright) to bypass bot-detection, and any substantive change triggers a new entry in the history. The 'Last updated' timestamp at the top of the main page shows when the most recent scan completed.",
  },
  {
    question: "What do the verdict badges mean?",
    answer:
      "Each change is classified as Good, Neutral, or Caution. 'Good' means the change appears to be in the user's favour (e.g. expanded rights, improved clarity). 'Neutral' means the change is informational or ambiguous. 'Caution' means the change may restrict user rights, expand the company's data use, or introduce new legal obligations.",
  },
  {
    question: "What does the Trust Score mean?",
    answer:
      "The Trust Score (0–100) is a quick signal of how risky the most recent change appears to be. It starts at 100 and is reduced by the verdict severity (−20 for Caution, −10 for Neutral) and by the number of unique high-risk legal terms detected in the change (−5 per term). A score of 70 or above is shown in green, 40–69 in yellow, and below 40 in red.",
  },
  {
    question: "What are the high-risk terms (watchlist hits)?",
    answer:
      "The watchlist is a curated list of legal terms that often signal unfavourable clauses — for example 'Arbitration', 'Class Action', 'Tracking', or 'Sell'. When these words appear in a detected change, they are highlighted as badges so you can quickly see which legal concepts are affected. Hover over any badge to see a plain-English explanation.",
  },
  {
    question: "Does Diffy provide legal advice?",
    answer:
      "No. Diffy is an informational tool only. The AI summaries, verdicts, and trust scores are automated approximations and are not a substitute for qualified legal advice. If a ToS change may affect you significantly, consult a legal professional.",
  },
  {
    question: "How does the AI summary work?",
    answer:
      "When a substantive change is detected, the diff of the old and new text is sent to an OpenAI model. The model is asked to classify changes under three categories — Privacy, Data Ownership, and User Rights — and return a short, plain-English description for each. For the very first snapshot of a company, a full overview summary is generated instead.",
  },
  {
    question: "Which companies are monitored?",
    answer:
      "The list of monitored companies lives in scraper/config.json in the GitHub repository. It currently covers a range of AI, Social, Productivity, Retail, Streaming, Finance, and other popular services. Contributions to expand the list are welcome via pull request.",
  },
  {
    question: "How can I contribute or report an issue?",
    answer:
      "Diffy is open source on GitHub (bradyudovich/Diffy). You can open an issue to request a new company, report a bug, or suggest improvements. Pull requests are welcome — the README has setup instructions for running the scraper and frontend locally.",
  },
];

interface ScoringRule {
  condition: string;
  deduction: string;
  example: string;
}

const SCORING_RULES: ScoringRule[] = [
  {
    condition: "Caution verdict",
    deduction: "−20 points",
    example: "A change that grants the company new data-sharing rights or removes user protections.",
  },
  {
    condition: "Neutral verdict",
    deduction: "−10 points",
    example: "A change in formatting, contact details, or language with no clear user impact.",
  },
  {
    condition: "Each unique high-risk term detected",
    deduction: "−5 points each",
    example: "'Arbitration', 'Sell', 'Tracking', 'Class Action', etc. found in the changed text.",
  },
];

function ScoringTable() {
  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-gray-50 text-left">
            <th className="px-4 py-2 font-semibold text-gray-700 border-b border-gray-200">Condition</th>
            <th className="px-4 py-2 font-semibold text-gray-700 border-b border-gray-200">Deduction</th>
            <th className="px-4 py-2 font-semibold text-gray-700 border-b border-gray-200">Example</th>
          </tr>
        </thead>
        <tbody>
          {SCORING_RULES.map((rule) => (
            <tr key={rule.condition} className="border-b border-gray-100 last:border-b-0">
              <td className="px-4 py-2 font-medium text-gray-800">{rule.condition}</td>
              <td className="px-4 py-2 font-bold text-red-600">{rule.deduction}</td>
              <td className="px-4 py-2 text-gray-600">{rule.example}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function FaqRow({ item }: { item: FaqItem }) {
  return (
    <div className="border-b border-gray-200 py-5 last:border-b-0">
      <h3 className="text-sm font-semibold text-gray-800 mb-1">{item.question}</h3>
      <p className="text-sm text-gray-600 leading-relaxed">{item.answer}</p>
    </div>
  );
}

interface Props {
  onBack: () => void;
}

export default function About({ onBack }: Props) {
  return (
    <div className="max-w-2xl mx-auto">
      <button
        onClick={onBack}
        className="mb-6 text-sm text-indigo-600 hover:text-indigo-800 flex items-center gap-1
                   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500
                   focus-visible:ring-offset-1 rounded transition-colors"
      >
        ← Back
      </button>

      <h2 className="text-2xl font-bold text-gray-900 mb-1">About Diffy</h2>
      <p className="text-sm text-gray-500 mb-8">
        Frequently asked questions about how Diffy works and what its data means.
      </p>

      {/* How we score section */}
      <section className="mb-8 bg-indigo-50 rounded-xl border border-indigo-100 px-6 py-5">
        <h2 className="text-lg font-bold text-indigo-900 mb-1 flex items-center gap-2">
          <span aria-hidden="true">📊</span> How we score
        </h2>
        <p className="text-sm text-indigo-800 mb-4 leading-relaxed">
          Every company starts with a perfect score of <strong>100</strong>. Points are deducted each
          time a substantive Terms of Service change is detected, based on its severity and the
          high-risk legal terms it introduces. The score always reflects the <em>most recent</em>{" "}
          change, so a company can recover if a later update reverses a harmful clause.
        </p>

        <ScoringTable />

        <div className="mt-4 space-y-2">
          <p className="text-xs font-semibold text-indigo-700 uppercase tracking-wide">Score bands</p>
          <div className="flex flex-wrap gap-2">
            <span className="rounded-full bg-green-100 border border-green-300 px-3 py-1 text-xs font-medium text-green-800">
              🟢 70–100 · Good
            </span>
            <span className="rounded-full bg-yellow-100 border border-yellow-300 px-3 py-1 text-xs font-medium text-yellow-800">
              🟡 40–69 · Fair
            </span>
            <span className="rounded-full bg-red-100 border border-red-300 px-3 py-1 text-xs font-medium text-red-800">
              🔴 0–39 · Poor
            </span>
          </div>
        </div>

        <div className="mt-5 rounded-lg bg-white/70 border border-indigo-100 px-4 py-3">
          <p className="text-xs font-semibold text-indigo-700 mb-2">Real-world examples</p>
          <ul className="space-y-1 text-xs text-indigo-900 leading-relaxed">
            <li>
              <strong>OpenAI</strong> — a Caution change (−20) that mentions &quot;Arbitration&quot;,
              &quot;Sell&quot;, and &quot;Tracking&quot; (3 terms × −5 = −15) leaves a score of{" "}
              <strong className="text-yellow-700">65 (Fair)</strong>.
            </li>
            <li>
              <strong>A privacy-focused tool</strong> — no Caution changes and only one watchlist
              term (−5) gives a score of <strong className="text-green-700">95 (Good)</strong>.
            </li>
          </ul>
        </div>

        <p className="mt-4 text-xs text-indigo-600">
          The scoring system is fully open-source. You can inspect the{" "}
          <code className="bg-indigo-100 px-1 py-0.5 rounded text-indigo-800">calculate_score()</code>{" "}
          function in{" "}
          <a
            href="https://github.com/bradyudovich/Diffy/blob/main/scraper/monitor.py"
            target="_blank"
            rel="noopener noreferrer"
            className="underline hover:text-indigo-900"
          >
            scraper/monitor.py
          </a>{" "}
          on GitHub.
        </p>
      </section>

      <div className="bg-white rounded-xl border border-gray-200 shadow-sm px-6">
        {FAQ_ITEMS.map((item) => (
          <FaqRow key={item.question} item={item} />
        ))}
      </div>

      <p className="text-xs text-gray-400 mt-6 text-center">
        Diffy is open source —{" "}
        <a
          href="https://github.com/bradyudovich/Diffy"
          target="_blank"
          rel="noopener noreferrer"
          aria-label="View Diffy on GitHub (opens in new tab)"
          className="text-indigo-500 hover:underline"
        >
          view on GitHub
        </a>
      </p>
    </div>
  );
}
