import { useMemo } from "react";
import { diffLines } from "diff";
import { List } from "react-window";
import type { Change } from "diff";
import type { RowComponentProps } from "react-window";

interface Props {
  oldText: string;
  newText: string;
}

interface DiffRow {
  type: "removed" | "added" | "unchanged";
  value: string;
}

function buildRows(changes: Change[]): DiffRow[] {
  const rows: DiffRow[] = [];
  for (const change of changes) {
    const lines = change.value.split("\n");
    // The last element from split is always an empty string when the chunk
    // ends with a newline – skip it to avoid phantom blank rows.
    const last = lines[lines.length - 1] === "" ? lines.slice(0, -1) : lines;
    for (const line of last) {
      if (change.added) {
        rows.push({ type: "added", value: line });
      } else if (change.removed) {
        rows.push({ type: "removed", value: line });
      } else {
        rows.push({ type: "unchanged", value: line });
      }
    }
  }
  return rows;
}

const ROW_HEIGHT = 22; // px
const MAX_VISIBLE_ROWS = 30;

const ROW_BG: Record<DiffRow["type"], string> = {
  removed:   "bg-red-50 text-red-800",
  added:     "bg-green-50 text-green-700",
  unchanged: "text-gray-600",
};

const ROW_INDICATOR: Record<DiffRow["type"], string> = {
  removed:   "−",
  added:     "+",
  unchanged: " ",
};

// Custom row data type (no forbidden keys: index, style, ariaAttributes).
interface RowData {
  rows: DiffRow[];
}

// Use react-window's RowComponentProps utility to get correctly-typed props.
type DiffRowProps = RowComponentProps<RowData>;

function DiffRowComponent({ index, style, rows }: DiffRowProps) {
  const row = rows[index];
  if (!row) return null;
  return (
    <div
      style={style}
      className={`flex items-center gap-2 px-2 whitespace-pre font-mono text-xs ${ROW_BG[row.type]}`}
    >
      <span className="w-4 shrink-0 text-center select-none opacity-60">
        {ROW_INDICATOR[row.type]}
      </span>
      <span className="truncate">{row.value}</span>
    </div>
  );
}

export default function RawDiffView({ oldText, newText }: Props) {
  const rows = useMemo(() => {
    if (!oldText && !newText) return [];
    const changes = diffLines(oldText, newText);
    return buildRows(changes);
  }, [oldText, newText]);

  if (rows.length === 0) {
    return (
      <p className="text-sm text-gray-400 italic px-2 py-4">
        No raw text available to diff.
      </p>
    );
  }

  const listHeight = Math.min(rows.length, MAX_VISIBLE_ROWS) * ROW_HEIGHT;

  return (
    <div className="rounded-lg border border-gray-200 overflow-hidden">
      {/* Legend */}
      <div className="flex gap-4 px-3 py-1.5 bg-gray-50 border-b border-gray-200 text-xs">
        <span className="flex items-center gap-1 text-red-600">
          <span className="font-bold">−</span> Removed
        </span>
        <span className="flex items-center gap-1 text-green-700">
          <span className="font-bold">+</span> Added
        </span>
        <span className="ml-auto text-gray-400">{rows.length} lines</span>
      </div>

      <List<RowData>
        rowComponent={DiffRowComponent}
        rowCount={rows.length}
        rowHeight={ROW_HEIGHT}
        rowProps={{ rows }}
        style={{ height: listHeight, width: "100%", overflowX: "auto" }}
      />
    </div>
  );
}
