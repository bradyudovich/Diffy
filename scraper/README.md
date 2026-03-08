# scraper/

This directory contains the Diffy backend: the Python scraper that monitors
Terms of Service pages, detects substantive changes, and outputs the versioned
`data/results.json` consumed by the frontend.

## Structure

```
scraper/
├── monitor.py          # Main scraper script (run by CI or manually)
├── config.json         # List of companies and their ToS URLs
├── requirements.txt    # Python dependencies
├── data/
│   ├── results.json    # Primary output (schema v2, versioned history)
│   └── snapshots/      # Temporary raw ToS snapshots (per-company .txt)
└── terms_of_service/
    └── {company_slug}/
        ├── {YYYY-MM-DD}.txt    # Archived ToS versions (one per distinct change)
        └── summary.txt         # Latest plain-text summary (backward compat)
```

## Running the scraper

```bash
# From the repo root:
pip install -r scraper/requirements.txt
python -m playwright install --with-deps chromium
OPENAI_API_KEY=sk-... python scraper/monitor.py
```

## Output schema (v2)

`data/results.json` follows schema version 2.0:

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
      "latestSummary": "[Privacy]: Users retain ownership...",
      "history": [
        {
          "previous_hash": null,
          "current_hash": "sha256hexstring",
          "timestamp": "2026-03-08T03:01:44Z",
          "verdict": "Caution",
          "diffSummary": {
            "Privacy": "Data may be used for model training without explicit opt-out.",
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
| `Good`    | No substantive change detected |
| `Neutral` | Substantive change with low risk (e.g. formatting, minor rewording) |
| `Caution` | Change in a high-risk section: privacy, arbitration, data ownership, AI training, termination |

Verdict is assigned automatically based on the `changeReason` and `diffSummary`
content; future automation may use a classifier model instead.

### SHA-256 hashing

`previous_hash` and `current_hash` are SHA-256 digests of the raw fetched ToS
text (UTF-8 encoded), computed before navigation preamble stripping.  A `null`
`previous_hash` indicates the first recorded version.

### `latestSummary`

The `latestSummary` field is a backward-compatible plain-text representation of
the most recent `diffSummary`, formatted as:

```
[Privacy]: <text> | [DataOwnership]: <text> | [UserRights]: <text>
```

It mirrors the `summary` field from schema v1 so that any tooling that reads
the old schema continues to work without modification.

## Configuration

Edit `config.json` to add or remove monitored companies:

```json
{
  "companies": [
    {
      "name": "Example Corp",
      "category": "Tech",
      "tosUrl": "https://example.com/terms"
    }
  ]
}
```

## Change detection algorithm

1. Fetch ToS page via headless Chromium (Playwright + Stealth)
2. Strip navigation preamble and appendix/footer regions
3. Pre-clean dynamic lines (Trace IDs, timestamps, bot-detection banners)
4. Normalize text (lowercase, collapse whitespace)
5. Compare against most-recently archived version:
   - Hot-section keyword check (privacy, arbitration, user_data, AI, …)
   - Document size % change check (> 4% threshold)
   - Overall semantic similarity check (SequenceMatcher or spaCy)
6. If substantive: call OpenAI GPT-4o-mini for a structured `diffSummary`
7. Assign a `verdict` and append a new entry to `history[]`
8. Write output to `scraper/data/results.json` **and** `public/data/results.json`
