# Diffy

**Diffy** is a GitHub Pages–hosted web app that tracks changes to companies'
Terms of Service pages. It uses AI to summarize each change and categorizes
them by Privacy, Data Ownership, and User Rights impact, with a **Caution /
Neutral / Good** verdict system.

## Live site

**https://bradyudovich.github.io/Diffy/**

## Project structure

```
scraper/                        # Python backend (ToS fetching & summarization)
  monitor.py                    # Main scraper — run by CI or manually
  config.json                   # Company list (edit to add/remove companies)
  requirements.txt              # Python dependencies
  data/
    results.json                # Schema v2 output (history, hashes, verdicts)
    snapshots/                  # Raw per-company ToS snapshots
  terms_of_service/
    {company_slug}/
      {YYYY-MM-DD}.txt          # Archived ToS versions (one per distinct change)
      summary.txt               # Latest plain-text summary (backward compat)

src/                            # React + TypeScript frontend (Vite)
  App.tsx                       # Root component — card grid + detail view
  types.ts                      # Shared TypeScript interfaces (v2 schema)
  components/
    ServiceCardGrid.tsx         # Overview grid: all companies + verdict badge
    ChangeTimeline.tsx          # Per-company change history timeline
    DiffViewer.tsx              # AI-labeled breakdown for a selected change

public/
  data/results.json             # Copy of scraper output served to the frontend

.github/workflows/
  daily_scan.yml                # CI: daily ToS scan (runs scraper/monitor.py)
  deploy.yml                    # CI: build Vite app → GitHub Pages
```

## How it works

1. **`scraper/config.json`** lists companies and their ToS URLs.
2. **`daily_scan.yml`** runs `scraper/monitor.py` every day at midnight UTC.
   The scraper uses Playwright (headless Chromium) to fetch each page,
   detects substantive changes, calls OpenAI to generate a structured summary,
   and commits the new `data/results.json`.
3. **`src/App.tsx`** fetches `data/results.json` from `raw.githubusercontent.com`
   on every page load (cache-busted), so it always shows the latest data
   without a full rebuild.
4. **`deploy.yml`** rebuilds and redeploys the site on every push to `main`.

## Data schema (v2)

```json
{
  "schemaVersion": "2.0",
  "updatedAt": "2026-03-08T03:01:44Z",
  "companies": [
    {
      "name": "OpenAI",
      "category": "AI",
      "tosUrl": "https://openai.com/policies/terms-of-use",
      "lastChecked": "2026-03-08T03:01:44Z",
      "latestSummary": "[Privacy]: Data may be used for model training.",
      "history": [
        {
          "previous_hash": null,
          "current_hash": "e3b0c44298fc1c149afb...",
          "timestamp": "2026-03-08T03:01:44Z",
          "verdict": "Caution",
          "diffSummary": {
            "Privacy": "Data may be used for model training without opt-out.",
            "DataOwnership": "Users retain rights to inputs; outputs owned by OpenAI.",
            "UserRights": "Arbitration clause added; class actions waived."
          },
          "changeIsSubstantial": true,
          "changeReason": "change detected in hot section: privacy"
        }
      ]
    }
  ]
}
```

### Verdict values

| Verdict   | Meaning |
|-----------|---------|
| `Good`    | No substantive change |
| `Neutral` | Substantive change with low risk |
| `Caution` | Change in a high-risk section (privacy, arbitration, AI training, termination, …) |

### `latestSummary`

A backward-compatible plain-text flattening of the most recent `diffSummary`,
matching the `summary` field format used in schema v1.

## Running the scraper locally

```bash
pip install -r scraper/requirements.txt
python -m playwright install --with-deps chromium
OPENAI_API_KEY=sk-... python scraper/monitor.py
```

## Running the frontend locally

```bash
npm install
npm run dev
```

## Adding companies

Edit `scraper/config.json`:

```json
{
  "companies": [
    { "name": "Example Corp", "category": "Tech", "tosUrl": "https://example.com/terms" }
  ]
}
```

## Frontend components

| Component | Purpose |
|-----------|---------|
| `ServiceCardGrid` | Responsive grid of all tracked companies; shows name, category, latest verdict badge, and change count |
| `ChangeTimeline` | Vertical timeline of all recorded changes for a selected company; click an entry to view its diff |
| `DiffViewer` | Detail card for a selected change: SHA-256 hashes, verdict, and AI-labeled breakdown by Privacy / Data Ownership / User Rights |

See [`scraper/README.md`](scraper/README.md) for full backend documentation.
