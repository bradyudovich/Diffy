/**
 * Button.tsx – Reusable button primitive.
 *
 * Variants:
 *   primary  – filled indigo, white text (default call-to-action)
 *   secondary – outlined indigo, indigo text
 *   ghost    – transparent background, gray text
 *
 * All variants include explicit focus-visible rings for keyboard accessibility.
 */

import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "secondary" | "ghost";
type Size = "sm" | "md" | "lg";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** Visual style variant. Defaults to "primary". */
  variant?: Variant;
  /** Size variant. Defaults to "md". */
  size?: Size;
  children: ReactNode;
}

const VARIANT_CLASSES: Record<Variant, string> = {
  primary:
    "bg-indigo-600 text-white border border-transparent hover:bg-indigo-700 active:bg-indigo-800 disabled:bg-indigo-300",
  secondary:
    "bg-transparent text-indigo-700 border border-indigo-300 hover:bg-indigo-50 active:bg-indigo-100 disabled:text-indigo-300 disabled:border-indigo-200",
  ghost:
    "bg-transparent text-gray-600 border border-transparent hover:bg-gray-100 active:bg-gray-200 disabled:text-gray-300",
};

const SIZE_CLASSES: Record<Size, string> = {
  sm: "px-3 py-1 text-xs gap-1",
  md: "px-4 py-2 text-sm gap-1.5",
  lg: "px-5 py-2.5 text-base gap-2",
};

/** WCAG-compliant focus ring applied on keyboard navigation only. */
const FOCUS_CLASSES =
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2";

export default function Button({
  variant = "primary",
  size = "md",
  className = "",
  children,
  disabled,
  ...rest
}: Props) {
  return (
    <button
      type="button"
      disabled={disabled}
      aria-disabled={disabled}
      className={[
        "inline-flex items-center justify-center rounded-lg font-semibold transition-colors duration-150",
        "disabled:cursor-not-allowed",
        VARIANT_CLASSES[variant],
        SIZE_CLASSES[size],
        FOCUS_CLASSES,
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      {...rest}
    >
      {children}
    </button>
  );
}
