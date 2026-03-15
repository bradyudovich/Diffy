/**
 * FeedbackForm.tsx – Modal for submitting user feedback about TOS accuracy.
 *
 * Allows users to flag inaccurate data, report missing TOS, or suggest
 * improvements.  Submissions open a pre-filled GitHub issue so contributions
 * stay transparent and auditable.
 */

import { useState, useEffect, useRef } from "react";
import { X, MessageSquare, Send } from "lucide-react";

interface Props {
  /** Pre-fill the company name if feedback is for a specific company. */
  companyName?: string;
  onClose: () => void;
}

type FeedbackType = "inaccurate-data" | "missing-tos" | "suggestion" | "other";

const FEEDBACK_LABELS: Record<FeedbackType, string> = {
  "inaccurate-data": "Inaccurate data or rating",
  "missing-tos":     "Missing TOS / URL",
  "suggestion":      "Feature suggestion",
  "other":           "Other",
};

export default function FeedbackForm({ companyName, onClose }: Props) {
  const [feedbackType, setFeedbackType] = useState<FeedbackType>("inaccurate-data");
  const [company, setCompany] = useState(companyName ?? "");
  const [message, setMessage] = useState("");
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const previouslyFocused = document.activeElement as HTMLElement | null;
    dialogRef.current?.focus();

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      previouslyFocused?.focus();
    };
  }, [onClose]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    // Build a GitHub issue URL with pre-filled body
    const title = encodeURIComponent(
      `[Feedback] ${FEEDBACK_LABELS[feedbackType]}${company ? ` – ${company}` : ""}`
    );
    const body = encodeURIComponent(
      [
        `**Feedback type:** ${FEEDBACK_LABELS[feedbackType]}`,
        company ? `**Company:** ${company}` : "",
        `**Message:**\n${message}`,
        "",
        "---",
        "_Submitted via the Diffy feedback form._",
      ]
        .filter(Boolean)
        .join("\n")
    );
    const label = encodeURIComponent(feedbackType);
    const url = `https://github.com/bradyudovich/Diffy/issues/new?title=${title}&body=${body}&labels=${label}`;
    window.open(url, "_blank", "noopener,noreferrer");
    onClose();
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="feedback-modal-title"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        ref={dialogRef}
        tabIndex={-1}
        className="relative bg-white rounded-2xl shadow-2xl max-w-lg w-full outline-none"
      >
        {/* Header */}
        <div className="border-b border-gray-100 px-6 py-4 flex items-center justify-between rounded-t-2xl">
          <div className="flex items-center gap-2">
            <MessageSquare className="h-5 w-5 text-indigo-600" aria-hidden="true" />
            <h2 id="feedback-modal-title" className="text-lg font-bold text-gray-900">
              Send Feedback
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close feedback form"
            className="rounded-full p-1.5 text-gray-500 hover:bg-gray-100 transition-colors
                       focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
          <p className="text-sm text-gray-600">
            Found an inaccuracy, missing TOS, or have a suggestion? Fill in the
            form below. Clicking "Submit" will open a pre-filled GitHub issue —
            no account required to view, but a free GitHub account is needed to post.
          </p>

          {/* Feedback type */}
          <div>
            <label
              htmlFor="feedback-type"
              className="block text-xs font-semibold text-gray-700 mb-1"
            >
              Feedback type
            </label>
            <select
              id="feedback-type"
              value={feedbackType}
              onChange={(e) => setFeedbackType(e.target.value as FeedbackType)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm
                         focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
              {(Object.keys(FEEDBACK_LABELS) as FeedbackType[]).map((type) => (
                <option key={type} value={type}>
                  {FEEDBACK_LABELS[type]}
                </option>
              ))}
            </select>
          </div>

          {/* Company name */}
          <div>
            <label
              htmlFor="feedback-company"
              className="block text-xs font-semibold text-gray-700 mb-1"
            >
              Company name <span className="text-gray-400 font-normal">(optional)</span>
            </label>
            <input
              id="feedback-company"
              type="text"
              value={company}
              onChange={(e) => setCompany(e.target.value)}
              placeholder="e.g. OpenAI, Google, Apple"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm
                         focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>

          {/* Message */}
          <div>
            <label
              htmlFor="feedback-message"
              className="block text-xs font-semibold text-gray-700 mb-1"
            >
              Message <span className="text-rose-500">*</span>
            </label>
            <textarea
              id="feedback-message"
              required
              rows={4}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Describe the issue or suggestion…"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm resize-y
                         focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-3 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg text-sm text-gray-600 border border-gray-300
                         hover:bg-gray-50 transition-colors
                         focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm
                         font-semibold bg-indigo-600 text-white hover:bg-indigo-700 transition-colors
                         focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500
                         focus-visible:ring-offset-1"
            >
              <Send className="h-3.5 w-3.5" aria-hidden="true" />
              Submit via GitHub
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
