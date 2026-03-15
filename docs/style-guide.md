# Diffy – UI Style Guide

This document defines the design tokens, component conventions, and accessibility rules that govern the Diffy front-end. All new UI work **must** follow these guidelines so that the application looks and behaves coherently.

---

## 1. Color Palette

Colors are defined as Tailwind CSS utility classes. Semantic intent is listed alongside each swatch.

### Brand / Primary

| Token | Tailwind class | Usage |
|-------|---------------|-------|
| Brand primary | `indigo-600` | Primary buttons, active links, focus rings |
| Brand primary dark | `indigo-800` | Hover state for primary actions |
| Brand primary light | `indigo-50` | Panel backgrounds, tinted surfaces |
| Brand accent | `purple-50` | Gradient pairs with `indigo-50` |

### Semantic (grade / status)

| Grade | Tailwind bg | Tailwind text | Score range |
|-------|------------|--------------|-------------|
| A | `bg-emerald-100` | `text-emerald-800` | ≥ 90 |
| B | `bg-teal-100` | `text-teal-800` | ≥ 70 |
| C | `bg-amber-100` | `text-amber-800` | ≥ 50 |
| D | `bg-orange-100` | `text-orange-800` | ≥ 30 |
| E | `bg-rose-100` | `text-rose-800` | < 30 |

### Impact / sentiment

| Intent | Background | Text | Border | Usage |
|--------|-----------|------|--------|-------|
| Positive | `bg-emerald-50` | `text-emerald-700` | `border-emerald-200` | Good clause, passing score |
| Negative | `bg-rose-50` | `text-rose-700` | `border-rose-200` | Bad clause, failing score |
| Neutral | `bg-sky-50` | `text-sky-700` | `border-sky-200` | Informational |
| Warning | `bg-amber-50` | `text-amber-700` | `border-amber-200` | Watchlist flags, caution |

### Neutral / surface

| Role | Tailwind class |
|------|---------------|
| Page background | `bg-gray-50` |
| Card surface | `bg-white` |
| Subtle border | `border-gray-200` |
| Muted text | `text-gray-500` |
| Body text | `text-gray-800` |
| Heading text | `text-gray-900` |

---

## 2. Typography

The app relies on the browser's system-UI font stack (`Inter, system-ui, sans-serif`) with Tailwind's default size scale.

### Scale

| Role | Tailwind classes | Notes |
|------|-----------------|-------|
| Page title | `text-2xl font-bold text-gray-900` | Company name, main headings |
| Section heading | `text-sm font-semibold text-gray-800` | Card headers, panel titles |
| Label / overline | `text-xs font-semibold text-gray-500 uppercase tracking-wide` | Section labels above content |
| Body | `text-sm text-gray-800 leading-relaxed` | Paragraph content |
| Small body | `text-xs text-gray-700 leading-snug` | List items, card details |
| Caption | `text-xs text-gray-400` | Timestamps, secondary metadata |
| Code / mono | `font-mono text-xs` | Case IDs, technical tokens |

### Rules

- Never go below `text-xs` (10 px) for readable content.
- Headings inside cards use `text-sm font-semibold`; reserve `text-base` and above for top-level page headings.
- Avoid `font-bold` on body copy – use `font-medium` or `font-semibold` instead.

---

## 3. Spacing

Spacing follows Tailwind's default 4 px base unit.

| Token | Value | Common usage |
|-------|-------|-------------|
| `gap-1` / `space-y-1` | 4 px | Tight icon+label pairs |
| `gap-2` / `space-y-2` | 8 px | Between list items |
| `gap-4` / `space-y-4` | 16 px | Between sections inside a card |
| `p-3` | 12 px | Compact card padding |
| `p-4` | 16 px | Standard card padding |
| `px-4 py-3` | 16 px / 12 px | Card header padding |
| `mb-6` | 24 px | Vertical gap between major panels |

### Rules

- Use `p-4` as the default card body padding; use `px-4 py-3` for card headers.
- Separate sibling sections inside a card with `space-y-4`.
- List items inside sections use `space-y-2`.

---

## 4. Border & Radius

| Element | Classes |
|---------|---------|
| Card | `rounded-xl border border-gray-200 shadow-sm` |
| Inner section / pill | `rounded-lg border border-gray-100` |
| Badge | `rounded-full` |
| Score bar | `rounded-full` |

---

## 5. Icon Usage

Icons come from **[Lucide React](https://lucide.dev/)** (`lucide-react` package).  
Emoji are used sparingly for decorative section labels only (not interactive controls).

### Standard icon sizes

| Context | Size class |
|---------|-----------|
| Inline with `text-xs` | `h-3 w-3` |
| Inline with `text-sm` | `h-3.5 w-3.5` |
| Button / nav item | `h-4 w-4` |
| Large standalone | `h-5 w-5` |

### Rules

- All decorative icons must carry `aria-hidden="true"`.
- Icons that convey meaning (e.g., status icons) must have a text alternative via `aria-label` on the parent or a visually-hidden `<span>`.
- Prefer Lucide icons over emoji for interactive elements.
- Emoji decorative labels use `<span aria-hidden="true">` before the visible text.

### Semantic icon mapping

| Icon (Lucide) | Meaning |
|--------------|---------|
| `CheckCircle` | Positive / passing |
| `XCircle` | Negative / failing |
| `Info` | Neutral / informational |
| `AlertTriangle` | Warning / watchlist |
| `ChevronDown` / `ChevronUp` | Expand / collapse |
| `ExternalLink` | Opens in new tab |

---

## 6. Focus States & Accessibility

### Focus rings

All interactive elements **must** show a visible focus ring on keyboard navigation using Tailwind's `focus-visible` utilities:

```
focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2
```

- Use `focus-visible` (not `focus`) to avoid showing the ring on mouse click.
- Ring color must be `indigo-500` (brand color).
- Ring offset `2` ensures the ring is not obscured by the element's own background.

### Buttons

- Always set an explicit `type` attribute (`type="button"` or `type="submit"`).
- Disabled buttons must include `aria-disabled="true"` and `disabled` attribute.
- Provide an `aria-label` when button text is icon-only.

### Color contrast

All text must meet **WCAG AA** contrast ratios:

| Context | Minimum ratio |
|---------|--------------|
| Normal text (< 18 px) | 4.5 : 1 |
| Large text (≥ 18 px or 14 px bold) | 3 : 1 |

Verified combinations:
- `text-gray-800` on `bg-white` → 14.7 : 1 ✔
- `text-gray-700` on `bg-gray-50` → 10.7 : 1 ✔
- `text-indigo-900` on `bg-indigo-50` → 8.6 : 1 ✔
- `text-emerald-800` on `bg-emerald-100` → 5.9 : 1 ✔
- `text-amber-800` on `bg-amber-100` → 5.0 : 1 ✔
- `text-rose-800` on `bg-rose-100` → 5.8 : 1 ✔
- `text-white` on `bg-indigo-600` → 5.9 : 1 ✔

### ARIA

- Sections use `<section aria-label="…">` to describe their purpose.
- Use `role="progressbar"` with `aria-valuenow`, `aria-valuemin`, `aria-valuemax` on score bars.
- Modal / overlay content must trap focus and support `Escape` to dismiss.
- Avoid `tabindex` values other than `0` and `-1`.

---

## 7. Reusable Primitives

All primitives live in `src/components/ui/` and are exported from `src/components/ui/index.ts`.

### `Button`

```tsx
import { Button } from "./components/ui";

<Button variant="primary" size="md" onClick={…}>Save</Button>
<Button variant="secondary">Cancel</Button>
<Button variant="ghost" size="sm">Learn more</Button>
```

**Props:** `variant` (`primary` | `secondary` | `ghost`), `size` (`sm` | `md` | `lg`), all native `<button>` props.

### `Card`

```tsx
import { Card } from "./components/ui";

<Card>
  <Card.Header icon="📊" title="Score Breakdown" subtitle="Industry comparison" />
  <Card.Body>…</Card.Body>
</Card>
```

### `Badge`

```tsx
import { Badge } from "./components/ui";

<Badge intent="positive">Positive</Badge>
<Badge intent="negative">Negative</Badge>
<Badge intent="neutral">Neutral</Badge>
<Badge intent="warning">Watchlist</Badge>
<Badge intent="grade" grade="A">A</Badge>
```

### `SectionHeader`

```tsx
import { SectionHeader } from "./components/ui";

<SectionHeader icon="🔍" label="Overview" />
<SectionHeader icon="📌" label="Key Clauses" />
```

---

## 8. Component Conventions

- One component per file, default export.
- Local sub-components (used only within one file) are defined in the same file above the main export.
- Props interfaces are defined with `interface Props { … }` directly above the component.
- Use `data-testid` attributes on the root element of each report-card component for testability.
- Use `aria-label` on `<section>` elements to describe their purpose in screen readers.
