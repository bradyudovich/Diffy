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
        className="mb-6 text-sm text-indigo-600 hover:text-indigo-800 flex items-center gap-1"
      >
        ← Back
      </button>

      <h2 className="text-2xl font-bold text-gray-900 mb-1">About Diffy</h2>
      <p className="text-sm text-gray-500 mb-8">
        Frequently asked questions about how Diffy works and what its data means.
      </p>

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
