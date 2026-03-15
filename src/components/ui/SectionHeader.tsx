/**
 * SectionHeader.tsx – Reusable overline section-label primitive.
 *
 * Renders the recurring "🔍 OVERVIEW" / "📌 KEY CLAUSES" label pattern used
 * inside report-card panels.  The icon is wrapped in aria-hidden to keep it
 * purely decorative.
 *
 * Usage:
 *   <SectionHeader icon="🔍" label="Overview" />
 *   <SectionHeader icon="📌" label="Key Clauses" />
 */

interface Props {
  /** Decorative emoji/icon. Wrapped in aria-hidden="true". */
  icon?: string;
  /** Section label text (rendered uppercase via CSS). */
  label: string;
  className?: string;
}

export default function SectionHeader({ icon, label, className = "" }: Props) {
  return (
    <p
      className={[
        "text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5 flex items-center gap-1",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {icon && <span aria-hidden="true">{icon}</span>}
      {label}
    </p>
  );
}
