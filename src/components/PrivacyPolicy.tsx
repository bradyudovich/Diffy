/**
 * PrivacyPolicy.tsx – Diffy's privacy policy page.
 *
 * Discloses what data Diffy collects (if any), how it is used,
 * and links to the open-source scraper so users can audit the code.
 */

import { SectionHeader } from "./ui";

interface Props {
  onBack: () => void;
}

interface PolicySection {
  heading: string;
  content: string[];
}

const POLICY_SECTIONS: PolicySection[] = [
  {
    heading: "What data does Diffy collect about you?",
    content: [
      "Diffy does not collect, store, or process any personally identifiable information (PII) from visitors to this website.",
      "The site is a static React application served from GitHub Pages. There is no backend server, no user accounts, no login, and no analytics SDK embedded in the page.",
      "Your browser fetches company data (results.json) directly from the public GitHub repository. No request is routed through a Diffy-controlled server.",
    ],
  },
  {
    heading: "Cookies and local storage",
    content: [
      "Diffy does not set any cookies.",
      "No data is written to your browser's localStorage or sessionStorage.",
    ],
  },
  {
    heading: "Third-party requests",
    content: [
      "The page loads company favicons from public CDNs. Your browser may make requests directly to those CDNs as a side-effect of rendering company cards.",
      "Clicking external links (e.g. a company's Terms of Service URL or GitHub) will take you to a third-party site subject to their own privacy policy.",
      "The feedback form opens a pre-filled GitHub issue in a new tab. GitHub's own privacy policy applies if you choose to submit that issue.",
    ],
  },
  {
    heading: "How does the scraper work?",
    content: [
      "The automated scraper (monitor.py) runs on GitHub Actions — a cloud service provided by GitHub. It fetches each company's Terms of Service page using a headless browser (Playwright), generates AI summaries via the OpenAI API, and commits the resulting JSON files to this repository.",
      "The scraper does not collect any information about Diffy website visitors. It only processes publicly available Terms of Service documents.",
      "You can audit the full scraper source code in the open-source repository at github.com/bradyudovich/Diffy.",
    ],
  },
  {
    heading: "AI-generated summaries",
    content: [
      "ToS text is sent to the OpenAI API to generate plain-English summaries. This is governed by OpenAI's own usage policies and privacy policy.",
      "Diffy does not send any user data to OpenAI — only the publicly available ToS text is transmitted.",
    ],
  },
  {
    heading: "Changes to this policy",
    content: [
      "If this privacy policy changes, the updated version will be committed to the public GitHub repository along with a dated commit message. You can review the full history of changes at any time.",
    ],
  },
  {
    heading: "Contact",
    content: [
      "Questions or concerns? Open an issue at github.com/bradyudovich/Diffy or use the feedback button on this site.",
    ],
  },
];

export default function PrivacyPolicy({ onBack }: Props) {
  return (
    <div className="animate-fade-in max-w-2xl mx-auto">
      {/* Back button */}
      <button
        type="button"
        onClick={onBack}
        className="mb-4 text-sm text-indigo-600 hover:text-indigo-800 flex items-center gap-1 transition-colors
                   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-1 rounded"
      >
        ← Back
      </button>

      <SectionHeader
        icon="🔒"
        label="Privacy Policy"
      />
      <p className="text-xs text-gray-500 mb-4">
        Last updated:{" "}
        {new Date().toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" })}
      </p>

      <div className="mt-2 rounded-xl bg-indigo-50 border border-indigo-100 px-4 py-3 text-sm text-indigo-700 mb-6">
        <strong>TL;DR:</strong> Diffy collects no personal data about you. The site is a
        static page with no backend. The open-source scraper only processes publicly
        available Terms of Service documents.
      </div>

      <div className="space-y-6">
        {POLICY_SECTIONS.map((section) => (
          <section key={section.heading} aria-labelledby={`pp-${section.heading.replace(/\s+/g, "-")}`}>
            <h3
              id={`pp-${section.heading.replace(/\s+/g, "-")}`}
              className="text-sm font-semibold text-gray-800 mb-2"
            >
              {section.heading}
            </h3>
            <div className="space-y-2">
              {section.content.map((para, i) => (
                <p key={i} className="text-sm text-gray-600 leading-relaxed">
                  {para}
                </p>
              ))}
            </div>
          </section>
        ))}
      </div>

      <div className="mt-8 border-t border-gray-200 pt-4 text-xs text-gray-400 text-center">
        This privacy policy is open-source.{" "}
        <a
          href="https://github.com/bradyudovich/Diffy"
          target="_blank"
          rel="noopener noreferrer"
          className="underline hover:text-indigo-600 transition-colors"
        >
          View on GitHub
        </a>
      </div>
    </div>
  );
}
