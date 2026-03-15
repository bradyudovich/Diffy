/**
 * TrendChart.tsx – SVG sparkline chart showing score trend over time.
 *
 * Renders a small line chart from an array of history entries, plotting
 * either trustScore values or letter-grade-derived scores for each change.
 * When showSubScores is enabled, additional lines for dataPractices, userRights,
 * and readability sub-scores are derived from each entry's diffSummary text.
 */

import type { HistoryEntry } from "../types";
import { scoreToGrade } from "./ScoreBadge";
import {
  deriveDataScore,
  deriveUserRightsScore,
  deriveReadabilityScore,
} from "../utils/scoreUtils";

interface Props {
  history: HistoryEntry[];
  /** Width of the chart in pixels. Defaults to 200. */
  width?: number;
  /** Height of the chart in pixels. Defaults to 60. */
  height?: number;
  /** Show axis labels. Defaults to false for compact use. */
  showLabels?: boolean;
  /** When true, render separate lines for each sub-score dimension. */
  showSubScores?: boolean;
}

const VERDICT_SCORES: Record<string, number> = {
  Good: 85,
  Neutral: 65,
  Caution: 40,
};

function entryScore(entry: HistoryEntry): number {
  if (entry.trustScore !== undefined) return entry.trustScore;
  return VERDICT_SCORES[entry.verdict] ?? 65;
}

/** Derive the three sub-scores for a history entry from its text content. */
function entrySubScores(entry: HistoryEntry): { dataPractices: number; userRights: number; readability: number } {
  // Combine all available text for scoring
  const text = [
    entry.changeReason,
    entry.diffSummary?.Privacy,
    entry.diffSummary?.DataOwnership,
    entry.diffSummary?.UserRights,
    ...(entry.summaryPoints?.map((p) => p.text) ?? []),
  ]
    .filter(Boolean)
    .join(" ");

  if (!text.trim()) {
    const overall = entryScore(entry);
    return { dataPractices: overall, userRights: overall, readability: overall };
  }
  return {
    dataPractices: deriveDataScore(text),
    userRights: deriveUserRightsScore(text),
    readability: deriveReadabilityScore(text),
  };
}

function scoreColor(score: number): string {
  if (score >= 70) return "#10b981"; // emerald
  if (score >= 50) return "#f59e0b"; // amber
  return "#ef4444";                  // rose
}

/** Build an SVG path string from a series of (x, y) coordinate pairs. */
function buildPath(coords: Array<{ x: number; y: number }>): string {
  if (coords.length === 0) return "";
  if (coords.length === 1) return `M ${coords[0].x} ${coords[0].y}`;
  return coords.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" ");
}

const SUB_SCORE_LINES = [
  { key: "dataPractices" as const, color: "#6366f1", label: "Data" },
  { key: "userRights"    as const, color: "#ec4899", label: "Rights" },
  { key: "readability"   as const, color: "#f59e0b", label: "Clarity" },
];

export default function TrendChart({
  history,
  width = 200,
  height = 60,
  showLabels = false,
  showSubScores = false,
}: Props) {
  if (!history || history.length === 0) {
    return (
      <div
        className="flex items-center justify-center text-gray-300 text-xs rounded-lg bg-gray-50 border border-dashed border-gray-200"
        style={{ width, height }}
      >
        No history
      </div>
    );
  }

  // Only show every meaningful change in chronological order
  const sorted = [...history].sort(
    (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
  );

  const overallScores = sorted.map(entryScore);
  const subScores = showSubScores ? sorted.map(entrySubScores) : [];

  // Compute the global min/max across all lines so they share the same axis
  const allValues = showSubScores
    ? [
        ...overallScores,
        ...subScores.map((s) => s.dataPractices),
        ...subScores.map((s) => s.userRights),
        ...subScores.map((s) => s.readability),
      ]
    : overallScores;

  const minScore = Math.max(0, Math.min(...allValues) - 10);
  const maxScore = Math.min(100, Math.max(...allValues) + 10);
  const scoreRange = maxScore - minScore || 1;

  // Reserve extra bottom space for the legend when showing sub-scores
  const legendH = showSubScores && showLabels ? 16 : 0;
  const padX = showLabels ? 30 : 8;
  const padY = showLabels ? 14 : 6;
  const innerW = width - padX * 2;
  const innerH = height - padY * 2 - legendH;
  const totalH = height + legendH;

  function toPoint(score: number, i: number, n: number) {
    const x = padX + (n === 1 ? innerW / 2 : (i / (n - 1)) * innerW);
    const y = padY + innerH - ((score - minScore) / scoreRange) * innerH;
    return { x, y };
  }

  const overallPoints = overallScores.map((s, i) => ({ ...toPoint(s, i, overallScores.length), s, entry: sorted[i] }));

  const pathD = buildPath(overallPoints);
  const areaD =
    overallPoints.length >= 2
      ? `${pathD} L ${overallPoints[overallPoints.length - 1].x.toFixed(1)} ${(padY + innerH).toFixed(1)} L ${overallPoints[0].x.toFixed(1)} ${(padY + innerH).toFixed(1)} Z`
      : "";

  const latestScore = overallScores[overallScores.length - 1];
  const lineColor = scoreColor(latestScore);

  // Build sub-score point arrays
  const subLines = showSubScores
    ? SUB_SCORE_LINES.map(({ key, color, label }) => {
        const pts = subScores.map((s, i) => toPoint(s[key], i, subScores.length));
        return { key, color, label, path: buildPath(pts), pts };
      })
    : [];

  return (
    <div className="relative" style={{ width, height: totalH }}>
      <svg
        width={width}
        height={totalH}
        viewBox={`0 0 ${width} ${totalH}`}
        className="overflow-visible"
        role="img"
        aria-label={`Score trend chart. Latest score: ${latestScore}`}
      >
        <defs>
          <linearGradient id="trend-area-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={lineColor} stopOpacity="0.2" />
            <stop offset="100%" stopColor={lineColor} stopOpacity="0" />
          </linearGradient>
        </defs>

        {/* Grid lines */}
        {showLabels && [0, 50, 100].map((v) => {
          const y = padY + innerH - ((v - minScore) / scoreRange) * innerH;
          if (y < padY - 1 || y > padY + innerH + 1) return null;
          return (
            <g key={v}>
              <line
                x1={padX}
                y1={y}
                x2={padX + innerW}
                y2={y}
                stroke="#e5e7eb"
                strokeWidth="1"
                strokeDasharray="3 3"
              />
              <text x={padX - 4} y={y + 3} textAnchor="end" fontSize="8" fill="#9ca3af">
                {v}
              </text>
            </g>
          );
        })}

        {/* Area fill (overall only) */}
        {!showSubScores && areaD && (
          <path d={areaD} fill="url(#trend-area-fill)" />
        )}

        {/* Sub-score lines (rendered beneath the overall line) */}
        {subLines.map(({ key, color, path }) => (
          <path
            key={key}
            d={path}
            fill="none"
            stroke={color}
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeDasharray="4 2"
            opacity="0.75"
          />
        ))}

        {/* Overall score line */}
        <path
          d={pathD}
          fill="none"
          stroke={lineColor}
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {/* Data points */}
        {overallPoints.map((p, i) => {
          const grade = scoreToGrade(p.s);
          return (
            <circle
              key={i}
              cx={p.x}
              cy={p.y}
              r={i === overallPoints.length - 1 ? 4 : 2.5}
              fill={scoreColor(p.s)}
              stroke="white"
              strokeWidth="1.5"
            >
              <title>
                {new Date(p.entry.timestamp).toLocaleDateString()} · {grade} ({p.s})
                {showSubScores
                  ? ` | Data: ${Math.round(subScores[i]?.dataPractices ?? 0)} · Rights: ${Math.round(subScores[i]?.userRights ?? 0)} · Clarity: ${Math.round(subScores[i]?.readability ?? 0)}`
                  : ""}
              </title>
            </circle>
          );
        })}

        {/* Date labels for first / last points */}
        {showLabels && overallPoints.length >= 2 && (
          <>
            <text
              x={overallPoints[0].x}
              y={height - legendH - 2}
              textAnchor="middle"
              fontSize="7"
              fill="#9ca3af"
            >
              {new Date(sorted[0].timestamp).toLocaleDateString(undefined, { month: "short", year: "2-digit" })}
            </text>
            <text
              x={overallPoints[overallPoints.length - 1].x}
              y={height - legendH - 2}
              textAnchor="middle"
              fontSize="7"
              fill="#9ca3af"
            >
              {new Date(sorted[sorted.length - 1].timestamp).toLocaleDateString(undefined, { month: "short", year: "2-digit" })}
            </text>
          </>
        )}

        {/* Sub-score legend */}
        {showSubScores && showLabels && (
          <g transform={`translate(${padX}, ${height + 2})`}>
            {/* Overall */}
            <line x1={0} y1={5} x2={12} y2={5} stroke={lineColor} strokeWidth="2.5" strokeLinecap="round" />
            <text x={15} y={9} fontSize="7" fill="#4b5563">Overall</text>
            {subLines.map(({ key, color, label }, idx) => {
              const ox = 50 + idx * 52;
              return (
                <g key={key}>
                  <line x1={ox} y1={5} x2={ox + 12} y2={5} stroke={color} strokeWidth="1.5" strokeDasharray="4 2" strokeLinecap="round" />
                  <text x={ox + 15} y={9} fontSize="7" fill="#4b5563">{label}</text>
                </g>
              );
            })}
          </g>
        )}
      </svg>
    </div>
  );
}
