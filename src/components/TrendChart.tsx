/**
 * TrendChart.tsx – SVG sparkline chart showing score trend over time.
 *
 * Renders a small line chart from an array of history entries, plotting
 * either trustScore values or letter-grade-derived scores for each change.
 */

import type { HistoryEntry } from "../types";
import { scoreToGrade } from "./ScoreBadge";

interface Props {
  history: HistoryEntry[];
  /** Width of the chart in pixels. Defaults to 200. */
  width?: number;
  /** Height of the chart in pixels. Defaults to 60. */
  height?: number;
  /** Show axis labels. Defaults to false for compact use. */
  showLabels?: boolean;
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

function scoreColor(score: number): string {
  if (score >= 70) return "#10b981"; // emerald
  if (score >= 50) return "#f59e0b"; // amber
  return "#ef4444";                  // rose
}

export default function TrendChart({
  history,
  width = 200,
  height = 60,
  showLabels = false,
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

  const scores = sorted.map(entryScore);
  const minScore = Math.max(0, Math.min(...scores) - 10);
  const maxScore = Math.min(100, Math.max(...scores) + 10);
  const scoreRange = maxScore - minScore || 1;

  const padX = showLabels ? 30 : 8;
  const padY = showLabels ? 14 : 6;
  const innerW = width - padX * 2;
  const innerH = height - padY * 2;

  const points = scores.map((s, i) => {
    const x = padX + (scores.length === 1 ? innerW / 2 : (i / (scores.length - 1)) * innerW);
    const y = padY + innerH - ((s - minScore) / scoreRange) * innerH;
    return { x, y, s, entry: sorted[i] };
  });

  const pathD =
    points.length === 1
      ? `M ${points[0].x} ${points[0].y}`
      : points.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" ");

  const areaD =
    points.length >= 2
      ? `${pathD} L ${points[points.length - 1].x.toFixed(1)} ${(padY + innerH).toFixed(1)} L ${points[0].x.toFixed(1)} ${(padY + innerH).toFixed(1)} Z`
      : "";

  const latestScore = scores[scores.length - 1];
  const lineColor = scoreColor(latestScore);

  return (
    <div className="relative" style={{ width, height }}>
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
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

        {/* Area fill */}
        {areaD && (
          <path d={areaD} fill="url(#trend-area-fill)" />
        )}

        {/* Line */}
        <path
          d={pathD}
          fill="none"
          stroke={lineColor}
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {/* Data points */}
        {points.map((p, i) => {
          const grade = scoreToGrade(p.s);
          return (
            <circle
              key={i}
              cx={p.x}
              cy={p.y}
              r={i === points.length - 1 ? 4 : 2.5}
              fill={scoreColor(p.s)}
              stroke="white"
              strokeWidth="1.5"
            >
              <title>
                {new Date(p.entry.timestamp).toLocaleDateString()} · {grade} ({p.s})
              </title>
            </circle>
          );
        })}

        {/* Date labels for first / last points */}
        {showLabels && points.length >= 2 && (
          <>
            <text
              x={points[0].x}
              y={height - 2}
              textAnchor="middle"
              fontSize="7"
              fill="#9ca3af"
            >
              {new Date(sorted[0].timestamp).toLocaleDateString(undefined, { month: "short", year: "2-digit" })}
            </text>
            <text
              x={points[points.length - 1].x}
              y={height - 2}
              textAnchor="middle"
              fontSize="7"
              fill="#9ca3af"
            >
              {new Date(sorted[sorted.length - 1].timestamp).toLocaleDateString(undefined, { month: "short", year: "2-digit" })}
            </text>
          </>
        )}
      </svg>
    </div>
  );
}
