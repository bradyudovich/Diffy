/**
 * ScoreBreakdownPanel.tsx – Multi-dimensional score breakdown display.
 *
 * Shows three score dimensions (Data Practices, User Rights, Readability) as
 * labelled progress bars with colour coding.  Accepts either a structured
 * `DiversifiedScores` object from the backend or raw numbers derived from
 * legacy summary text.
 */

import type { DiversifiedScores } from "../types";
import { Card } from "./ui";

interface Props {
  /** Backend-computed multi-dimensional scores (preferred). */
  scores?: DiversifiedScores;
  /** Fallback values derived from legacy summary text. */
  derived?: {
    dataPractices: number;
    userRights: number;
    readability: number;
    overall: number;
  };
  /** Show a compact single-row variant for the card grid. */
  compact?: boolean;
}

interface Dimension {
  label: string;
  key: "dataPractices" | "userRights" | "readability";
  icon: string;
  description: string;
}

const DIMENSIONS: Dimension[] = [
  {
    label: "Data Practices",
    key: "dataPractices",
    icon: "🔒",
    description: "How responsibly the company handles your personal data",
  },
  {
    label: "User Rights",
    key: "userRights",
    icon: "⚖️",
    description: "How well the TOS protects your legal rights",
  },
  {
    label: "Readability",
    key: "readability",
    icon: "📖",
    description: "How clearly the terms are written",
  },
];

function barColor(score: number): { bar: string; text: string } {
  if (score >= 70) return { bar: "bg-emerald-500", text: "text-emerald-700" };
  if (score >= 50) return { bar: "bg-amber-400",   text: "text-amber-700" };
  if (score >= 30) return { bar: "bg-orange-400",  text: "text-orange-700" };
  return { bar: "bg-rose-500", text: "text-rose-700" };
}

function ScoreBar({
  label,
  icon,
  description,
  score,
  compact,
}: {
  label: string;
  icon: string;
  description: string;
  score: number;
  compact?: boolean;
}) {
  const clamped = Math.max(0, Math.min(100, Math.round(score)));
  const { bar, text } = barColor(clamped);

  if (compact) {
    return (
      <div className="flex items-center gap-1.5" title={`${label}: ${clamped}/100 – ${description}`}>
        <span className="text-[10px] text-gray-500 w-16 shrink-0 truncate">{icon} {label}</span>
        <div className="flex-1 h-1.5 rounded-full bg-gray-100 overflow-hidden">
          <div className={`h-full rounded-full ${bar} transition-all duration-500`} style={{ width: `${clamped}%` }} />
        </div>
        <span className={`text-[10px] font-semibold w-6 text-right ${text}`}>{clamped}</span>
      </div>
    );
  }

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-gray-700 flex items-center gap-1">
          <span aria-hidden="true">{icon}</span>
          {label}
        </span>
        <span className={`text-xs font-bold ${text}`}>{clamped}</span>
      </div>
      <div
        className="h-2 rounded-full bg-gray-100 overflow-hidden"
        role="progressbar"
        aria-valuenow={clamped}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`${label}: ${clamped} out of 100`}
        title={description}
      >
        <div
          className={`h-full rounded-full ${bar} transition-all duration-500`}
          style={{ width: `${clamped}%` }}
        />
      </div>
    </div>
  );
}

export default function ScoreBreakdownPanel({ scores, derived, compact = false }: Props) {
  // Use backend scores when available, fall back to derived values
  const values = {
    dataPractices: scores?.dataPractices ?? derived?.dataPractices ?? 0,
    userRights:    scores?.userRights    ?? derived?.userRights    ?? 0,
    readability:   scores?.readability   ?? derived?.readability   ?? 0,
  };

  const benchmarkRank = scores?.benchmarkRank;
  const industryAvg   = scores?.industryAvg;

  if (compact) {
    return (
      <div className="space-y-0.5 mt-2">
        {DIMENSIONS.map((dim) => (
          <ScoreBar
            key={dim.key}
            label={dim.label}
            icon={dim.icon}
            description={dim.description}
            score={values[dim.key]}
            compact
          />
        ))}
      </div>
    );
  }

  return (
    <Card>
      <Card.Header
        icon="📊"
        title="Score Breakdown"
        subtitle={
          benchmarkRank
            ? `Industry rank: ${benchmarkRank}${industryAvg !== undefined ? ` (avg ${Math.round(industryAvg)})` : ""}`
            : undefined
        }
      />

      <div className="px-4 py-3 space-y-3">
        {DIMENSIONS.map((dim) => (
          <ScoreBar
            key={dim.key}
            label={dim.label}
            icon={dim.icon}
            description={dim.description}
            score={values[dim.key]}
          />
        ))}
      </div>

      {!scores && (
        <p className="px-4 pb-3 text-[10px] text-gray-400 italic">
          * Scores estimated from TOS summary text. Run the scraper to get precise backend-computed values.
        </p>
      )}
    </Card>
  );
}
