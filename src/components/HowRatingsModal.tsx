/**
 * HowRatingsModal.tsx – Modal dialog explaining Diffy's scoring methodology.
 *
 * Shows the three scoring dimensions (Data Practices, User Rights, Readability),
 * grade thresholds (A–E), and important caveats about automated scoring.
 */

import { useEffect, useRef } from "react";
import { X, Info } from "lucide-react";
import { getRatingMethodology } from "../utils/scoreUtils";

interface Props {
  onClose: () => void;
}

const GRADE_COLORS: Record<string, string> = {
  emerald: "bg-emerald-100 text-emerald-800 ring-emerald-300",
  teal:    "bg-teal-100    text-teal-800    ring-teal-300",
  amber:   "bg-amber-100   text-amber-800   ring-amber-300",
  orange:  "bg-orange-100  text-orange-800  ring-orange-300",
  rose:    "bg-rose-100    text-rose-800    ring-rose-300",
};

export default function HowRatingsModal({ onClose }: Props) {
  const { dimensions, grades, notes } = getRatingMethodology();
  const dialogRef = useRef<HTMLDivElement>(null);

  // Trap focus inside the modal and handle Escape key
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

  return (
    /* Overlay */
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="ratings-modal-title"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      {/* Panel */}
      <div
        ref={dialogRef}
        tabIndex={-1}
        className="relative bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto outline-none"
      >
        {/* Header */}
        <div className="sticky top-0 bg-white border-b border-gray-100 px-6 py-4 flex items-center justify-between rounded-t-2xl z-10">
          <div className="flex items-center gap-2">
            <Info className="h-5 w-5 text-indigo-600" aria-hidden="true" />
            <h2 id="ratings-modal-title" className="text-lg font-bold text-gray-900">
              How Diffy Ratings Work
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close ratings explanation"
            className="rounded-full p-1.5 text-gray-500 hover:bg-gray-100 transition-colors
                       focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-5 space-y-6">
          {/* Intro */}
          <p className="text-sm text-gray-600 leading-relaxed">
            Diffy automatically analyses each company's Terms of Service text and assigns a score
            from 0–100 across three dimensions. The overall score is the unweighted average of
            those three scores and maps to a letter grade (A–E).
          </p>

          {/* Scoring dimensions */}
          <section aria-labelledby="dimensions-heading">
            <h3 id="dimensions-heading" className="text-sm font-semibold text-gray-800 mb-3">
              Scoring Dimensions
            </h3>
            <div className="space-y-3">
              {dimensions.map((dim) => (
                <div key={dim.name} className="rounded-xl border border-gray-200 p-4 bg-gray-50">
                  <div className="flex items-start justify-between gap-2 mb-1.5">
                    <span className="text-sm font-semibold text-gray-800">{dim.name}</span>
                    <span className="text-xs text-gray-500 bg-white border border-gray-200 px-2 py-0.5 rounded-full shrink-0">
                      weight {dim.weight}
                    </span>
                  </div>
                  <p className="text-xs text-gray-600 leading-relaxed">{dim.description}</p>
                  <div className="mt-2 flex flex-wrap gap-2 text-xs text-gray-500">
                    <span>Base score: <strong>{dim.baseScore}</strong></span>
                  {(dim.negativeAdjustment as number) !== 0 && (
                      <span className="text-rose-600">
                        Negative signal: <strong>{dim.negativeAdjustment}</strong> pts each
                      </span>
                    )}
                    {(dim.positiveAdjustment as number) !== 0 && (
                      <span className="text-emerald-600">
                        Positive signal: <strong>+{dim.positiveAdjustment}</strong> pts each
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* Grade thresholds */}
          <section aria-labelledby="grades-heading">
            <h3 id="grades-heading" className="text-sm font-semibold text-gray-800 mb-3">
              Grade Thresholds
            </h3>
            <div className="grid grid-cols-5 gap-2">
              {grades.map((g) => (
                <div
                  key={g.grade}
                  className={`flex flex-col items-center rounded-xl p-3 ring-2 ${GRADE_COLORS[g.color] ?? ""}`}
                >
                  <span className="text-2xl font-black">{g.grade}</span>
                  <span className="text-xs font-semibold mt-0.5">{g.label}</span>
                  <span className="text-xs opacity-70">{g.range}</span>
                </div>
              ))}
            </div>
          </section>

          {/* Notes */}
          <section aria-labelledby="notes-heading">
            <h3 id="notes-heading" className="text-sm font-semibold text-gray-800 mb-2">
              Important Notes
            </h3>
            <ul className="space-y-1.5">
              {notes.map((note, i) => (
                <li key={i} className="flex gap-2 text-xs text-gray-600">
                  <span className="text-indigo-400 shrink-0 mt-0.5" aria-hidden="true">•</span>
                  <span>{note}</span>
                </li>
              ))}
            </ul>
          </section>

          {/* Source */}
          <div className="rounded-lg bg-indigo-50 border border-indigo-100 px-4 py-3 text-xs text-indigo-700">
            <strong>Data sources:</strong> Diffy scrapes each company's published Terms of Service
            URL daily using an automated browser (Playwright). Summaries and risk signals are
            generated by an AI model (OpenAI GPT). Scores are recalculated on every scraper run.
          </div>
        </div>
      </div>
    </div>
  );
}
