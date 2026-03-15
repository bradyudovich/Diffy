/**
 * Card.tsx – Reusable card container primitive.
 *
 * Provides a consistent border, radius, and shadow surface.  An optional
 * Card.Header sub-component renders the indigo gradient header band used
 * across report-card panels (score breakdown, current ToS report card, etc.).
 *
 * Usage:
 *   <Card>
 *     <Card.Header icon="📊" title="Score Breakdown" subtitle="Industry comparison" />
 *     <Card.Body>…</Card.Body>
 *   </Card>
 */

import type { ReactNode } from "react";

// ---------------------------------------------------------------------------
// Card.Header
// ---------------------------------------------------------------------------

interface CardHeaderProps {
  /** Decorative emoji/icon shown before the title. Wrapped in aria-hidden. */
  icon?: string;
  /** Required heading text. */
  title: string;
  /** Optional subtitle / description rendered below the title. */
  subtitle?: string;
}

function CardHeader({ icon, title, subtitle }: CardHeaderProps) {
  return (
    <div className="px-4 py-3 border-b border-indigo-100 bg-gradient-to-r from-indigo-50 to-purple-50">
      <h3 className="text-sm font-semibold text-indigo-900 flex items-center gap-1.5">
        {icon && <span aria-hidden="true">{icon}</span>}
        {title}
      </h3>
      {subtitle && (
        <p className="text-xs text-indigo-600 mt-0.5">{subtitle}</p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Card.Body
// ---------------------------------------------------------------------------

interface CardBodyProps {
  children: ReactNode;
  className?: string;
}

function CardBody({ children, className = "" }: CardBodyProps) {
  return (
    <div
      className={["p-4 space-y-4", className].filter(Boolean).join(" ")}
    >
      {children}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Card root
// ---------------------------------------------------------------------------

interface CardProps {
  children: ReactNode;
  className?: string;
  /** data-testid forwarded to the root div for testing. */
  testId?: string;
}

function Card({ children, className = "", testId }: CardProps) {
  return (
    <div
      className={[
        "rounded-xl border border-indigo-200 bg-gradient-to-br from-white to-indigo-50 shadow-sm overflow-hidden",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      data-testid={testId}
    >
      {children}
    </div>
  );
}

Card.Header = CardHeader;
Card.Body = CardBody;

export default Card;
