# Diffy

**Diffy** is a GitHub Pages–hosted web app that tracks changes to companies' Terms of Service pages.

## Live site

The app is deployed at: **https://bradyudovich.github.io/Diffy/**

![Diffy screenshot](docs/screenshot.png)

## How it works

1. `config.json` at the repo root lists the companies and their ToS URLs to monitor.
2. The `.github/workflows/daily_scan.yml` workflow runs `monitor.py` every day at midnight UTC (and can be triggered manually). It uses a headless Chromium browser (via Playwright) to fetch each ToS page, stores snapshots in `data/snapshots/`, archives changed versions under `terms_of_service/`, generates AI summaries via the OpenAI API, and commits updated results to `data/results.json`.
3. The frontend (`src/App.tsx`) fetches `data/results.json` directly from the `main` branch via `raw.githubusercontent.com` on every page load (with a cache-busting timestamp query param), so it always reflects the latest committed data without needing a rebuild.
4. On every push to `main` (including when `data/results.json` changes), the Pages deployment workflow (`.github/workflows/deploy.yml`) rebuilds and redeploys the site automatically.

## Project structure

```
config.json              # List of companies and their ToS URLs — edit this to add/remove companies
data/
  results.json           # Latest diff results, committed by the update workflow
  snapshots/             # Raw ToS snapshots stored by the update workflow
terms_of_service/
  {company_slug}/        # One folder per company (slug replaces non-word chars with _)
    {YYYY-MM-DD}.txt     # Full ToS text archived each time a change is detected
    summary.txt          # Latest plain-English summary of the current ToS
src/
  App.tsx                # React frontend; fetches data/results.json from raw.githubusercontent.com
.github/workflows/
  deploy.yml             # GitHub Actions: build Vite app and deploy to GitHub Pages
  daily_scan.yml         # GitHub Actions: daily ToS scan, archiving, and summarization
```

## ToS version archiving

Each time `monitor.py` runs it archives the full ToS text under
`terms_of_service/{company_slug}/{YYYY-MM-DD}.txt`.  A new file is only
written when the fetched content differs from the most-recently archived
version, so the folder accumulates one file per distinct version (not one
file per day).  If two distinct versions are detected on the same calendar
day a numeric suffix (`_1`, `_2`, …) is appended to keep both.

Previous versions are **never deleted**, which enables historical diffs and
audit trails.

## ToS summarization

`monitor.py` uses the **hybrid substantive diff method** to decide when to
regenerate a ToS summary and alert users.  Raw legal text is fetched from the
company's ToS page, normalized, and compared against the most-recently archived
version.  A new AI summary is generated **only** when a *substantive* change is
detected.

### Archiving vs. alerting

Every new version of a ToS is always archived under
`terms_of_service/{company_slug}/` for audit purposes, even if the change is
not considered substantive (e.g. a pure whitespace re-flow).  However, the
`changed` field in `data/results.json` is only set to `true` and the AI
summary is only regenerated when the change is deemed significant.

### Change detection pipeline

1. **Normalize** – both texts are lowercased, whitespace is collapsed, and
   blank lines are reduced before any comparison.  This eliminates false
   positives from purely cosmetic edits.
2. **Hot-section check** – the document is split into paragraphs.  Any
   paragraph matching one of the *hot section* keywords is extracted and
   compared old-vs-new using a semantic similarity score.  If the score falls
   below `SIMILARITY_THRESHOLD` (default **0.97**), the change is flagged and
   the reason is recorded (e.g. `"change detected in hot section: arbitration"`).
3. **Percent-change check** – if total document character-length changes by
   more than `PERCENT_CHANGE_THRESHOLD` (default **2 %**), the change is
   flagged with a reason like `"document changed by 5.3%"`.
4. **Overall semantic similarity** – if no earlier check triggered, the overall
   similarity of the two normalized documents is measured.  A score below
   `SIMILARITY_THRESHOLD` flags the change with reason `"semantic meaning
   changed"`.

### Semantic similarity

spaCy (`en_core_web_md`) is used when installed.  If spaCy is unavailable the
code falls back transparently to `difflib.SequenceMatcher`, which uses the same
`SIMILARITY_THRESHOLD`.  Install spaCy for higher-quality semantic comparison:

```bash
pip install spacy
python -m spacy download en_core_web_md
```

### Configuring thresholds and hot sections

All thresholds and the list of hot-section keyword patterns live at the top of
`monitor.py` in three constants:

| Constant | Default | Description |
|---|---|---|
| `HOT_SECTION_KEYWORDS` | see source | Dict of section name → list of regex patterns |
| `SIMILARITY_THRESHOLD` | `0.97` | Similarity score below which a change is substantive |
| `PERCENT_CHANGE_THRESHOLD` | `0.02` | Fractional size change (0.02 = 2 %) to trigger a flag |

Edit these constants directly in `monitor.py` to tune sensitivity.

### Change reason in results

When a substantive change is detected, the `data/results.json` entry for that
company includes a `changeReason` field explaining why the change was flagged,
e.g.:

```json
{
  "name": "Example Corp",
  "changed": true,
  "changeReason": "change detected in hot section: arbitration",
  "summary": "..."
}
```

- **No change detected** (`archive_tos_if_changed` returns `False`): the
  existing `summary.txt` is returned as-is.  The AI is **never** called.
- **Change detected but not substantive**: the new version is archived, the
  existing summary is reused, and `changed` is `false`.
- **Substantive change detected**: the new version is archived, a fresh AI
  summary is generated, `changed` is `true`, and `changeReason` explains the
  flag.


## Editing the company list

Open `config.json` and add or remove entries:

```json
{
  "companies": [
    { "name": "Acme Inc.", "category": "Tech", "tosUrl": "https://acme.example/terms" }
  ]
}
```

The `category` field is used by the frontend to populate the category filter bar. Recognized categories with built-in icons are: `AI`, `Social`, `Productivity`, `Retail`, `Streaming`, `Services`, `Finance`, `Auto`, `Travel`, and `Tech`. Any other value falls back to a 🏢 icon.

## Company logos

Each company card displays a favicon fetched from Google's favicon API:

```
https://www.google.com/s2/favicons?sz=32&domain=<company-domain>
```

If the favicon fails to load, a 🏢 fallback icon is shown instead.

## ToS summary click-through

Clicking any company card opens a modal dialog showing a privacy- and
AI-focused summary of that company's Terms of Service. The summary is
sourced from the `summary` field in `data/results.json`.

- **When changes are detected** between versions, the summary lists what
  changed in terms of privacy, data use, and AI training, with an overall
  severity rating (High, Medium, or Low).
- **When no changes are detected** (or on the first snapshot), the summary
  lists privacy risks, AI training concerns, data collection red flags, and
  other significant user rights issues found in the current ToS.

The modal displays a 📁 folder icon in the bottom-right corner that links
to the full Terms of Service page. There is no visible URL text link in
the modal or on the company card.

## Local development

**Frontend**

```bash
npm install
npm run dev
```

The dev server runs at `http://localhost:5173/Diffy/`.

**Backend (monitor.py)**

`monitor.py` requires Python 3.11+, Playwright's Chromium browser, and an OpenAI API key:

```bash
pip install -r requirements.txt
python -m playwright install --with-deps chromium
OPENAI_API_KEY=<your-key> python monitor.py
```

## Deployment

Pushes to `main` automatically trigger the `.github/workflows/deploy.yml` workflow, which builds the Vite app and deploys the `dist/` folder to GitHub Pages.

The `.github/workflows/daily_scan.yml` workflow runs `monitor.py` on a daily schedule (midnight UTC) and can also be triggered manually from the Actions tab. It commits any updated data files back to `main`, which in turn triggers a fresh Pages deployment.
