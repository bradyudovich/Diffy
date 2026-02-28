"""
monitor.py – Phase 2 backend script for Diffy.
Uses Playwright to bypass aggressive bot detection (Cloudflare 403s).
"""

import difflib
import json
import os
import re
import sys
import time
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup
import requests
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth  # Updated import

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.json"
SNAPSHOTS_DIR = BASE_DIR / "data" / "snapshots"
DATA_RESULTS_PATH = BASE_DIR / "data" / "results.json"
PUBLIC_RESULTS_PATH = BASE_DIR / "public" / "data" / "results.json"
TOS_DIR = BASE_DIR / "terms_of_service"

# ---------------------------------------------------------------------------
# Hybrid substantive diff configuration
# ---------------------------------------------------------------------------

# Keywords/patterns identifying "hot" TOS sections that warrant careful change
# detection.  Each key maps to a list of regex patterns (case-insensitive).
# Tweak the lists here to adjust which sections are considered high-risk.
HOT_SECTION_KEYWORDS: dict[str, list[str]] = {
    "liability":     [r"\bliabilit\w*\b", r"\bindemnif\w*\b"],
    "privacy":       [r"\bprivac\w*\b", r"\bpersonal\s+data\b", r"\bdata\s+collect\w*\b"],
    "arbitration":   [r"\barbitrat\w*\b"],
    "dispute":       [r"\bdisput\w*\b", r"\bclass[\s\-]action\b"],
    "termination":   [r"\bterminat\w*\b", r"\bsuspend\w*\b"],
    "user_data":     [r"\buser\s+data\b", r"\byour\s+data\b", r"\buser\s+content\b"],
    "ai":            [r"\bartificial\s+intelligen\w*\b", r"\bmachine\s+learn\w*\b", r"\bai[\s\-]train\w*\b"],
    "governing_law": [r"\bgoverning\s+law\b", r"\bjurisdiction\b"],
}

# Similarity score below which a section change is considered substantive.
# Applies to both spaCy vector similarity (when available) and the
# SequenceMatcher fallback.  Range: 0.0 (totally different) – 1.0 (identical).
SIMILARITY_THRESHOLD: float = 0.97

# Fractional document-size change (0.02 = 2%) that triggers a flag for
# non-hot-section changes.
PERCENT_CHANGE_THRESHOLD: float = 0.02

# ---------------------------------------------------------------------------
# OpenAI API Settings
# ---------------------------------------------------------------------------
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_MODEL = "gpt-4o-mini"
AI_TOS_SUMMARY_PROMPT = (
    "You are a legal summarizer. Provide a high-level summary of the current terms for this company. "
    "Constraints: Maximum 30 words. "
    "Structure: [Category]: [Key Data/Legal Policy]. [Critical User Constraint]. "
    "Focus: Ignore minor formatting; focus on data rights, AI usage, and liability. "
    "Style: Do not use fluff like 'This policy covers...' or 'Users should know...' "
    "Return only the summary, no explanation or intro."
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ensure_dirs() -> None:
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    TOS_DIR.mkdir(parents=True, exist_ok=True)
    PUBLIC_RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)

def load_config() -> list[dict]:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("companies", [])

def snapshot_path(company_name: str) -> Path:
    safe = re.sub(r"[^\w\-]", "_", company_name)
    return SNAPSHOTS_DIR / f"{safe}.txt"

def fetch_text(url: str, max_retries: int = 3) -> str:
    """Fetch URL using a headless browser with updated stealth patterns.

    Workarounds applied to handle slow/flaky external pages in CI:
    - ``wait_until="domcontentloaded"`` is used instead of ``"networkidle"``
      because ``networkidle`` waits for *all* network activity to stop, which
      frequently times out on external sites that keep long-polling connections
      open (e.g. analytics scripts).
    - The timeout is raised to 90 000 ms to give slow-loading pages more room.
    - Up to ``max_retries`` attempts are made with exponential back-off so
      transient network blips don't cause a hard failure.
    """
    last_exc: Exception = Exception(f"All {max_retries} attempts to fetch {url} failed.")

    for attempt in range(1, max_retries + 1):
        with sync_playwright() as p:
            # Launch Chromium with HTTP/2 disabled to avoid
            # ERR_HTTP2_PROTOCOL_ERROR on sites like Adobe, Ford, and
            # United Airlines that have aggressive HTTP/2 configurations.
            browser = p.chromium.launch(headless=True, args=["--disable-http2"])

            # Set a realistic user agent
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )

            page = context.new_page()

            # NEW VERSION: Use the Stealth class to apply evasion patterns
            stealth = Stealth()
            stealth.apply_stealth_sync(page)

            try:
                # Human-like delay before navigation
                time.sleep(random.uniform(1, 3))

                # Use "domcontentloaded" instead of "networkidle" to avoid
                # timeouts caused by persistent background network requests on
                # external sites.  Timeout increased to 90 s for slow pages.
                page.goto(url, wait_until="domcontentloaded", timeout=90000)

                # Get rendered HTML
                html_content = page.content()
                soup = BeautifulSoup(html_content, "html.parser")

                # Remove scripts, styles, and common UI elements to keep legal text clean
                for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside"]):
                    tag.decompose()

                return soup.get_text(separator="\n", strip=True)

            except Exception as e:
                last_exc = e
                print(
                    f"  [attempt {attempt}/{max_retries}] Failed to fetch {url}: {e}"
                )
                if attempt < max_retries:
                    # Exponential back-off: 5 s, 10 s, 20 s, …
                    backoff = 5 * (2 ** (attempt - 1))
                    print(f"  Retrying in {backoff}s…")
                    time.sleep(backoff)
            finally:
                browser.close()

    raise Exception(f"Playwright failed to fetch {url}: {last_exc}")

def read_snapshot(company_name: str) -> str | None:
    path = snapshot_path(company_name)
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None

def write_snapshot(company_name: str, text: str) -> None:
    snapshot_path(company_name).write_text(text, encoding="utf-8")

def company_slug(company_name: str) -> str:
    """Return a filesystem-safe slug for a company name."""
    return re.sub(r"[^\w\-]", "_", company_name)

def tos_archive_dir(company_name: str) -> Path:
    """Return the archive directory for a company."""
    return TOS_DIR / company_slug(company_name)

def get_latest_archived_tos(company_name: str) -> str | None:
    """Return the text of the most recently archived ToS, or None if no archive exists."""
    archive_dir = tos_archive_dir(company_name)
    if not archive_dir.exists():
        return None
    dated_files = sorted(f for f in archive_dir.glob("*.txt") if f.name != "summary.txt")
    if not dated_files:
        return None
    return dated_files[-1].read_text(encoding="utf-8")

def archive_tos_if_changed(company_name: str, new_text: str) -> bool:
    """Save new_text as a dated archive file if it differs from the latest archived version.

    Returns True if a new archive file was written, False if the content is unchanged.
    """
    archive_dir = tos_archive_dir(company_name)
    archive_dir.mkdir(parents=True, exist_ok=True)
    if get_latest_archived_tos(company_name) == new_text:
        return False
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    archive_path = archive_dir / f"{date_str}.txt"
    # Avoid overwriting a same-day file with a numeric suffix
    suffix = 1
    while archive_path.exists():
        archive_path = archive_dir / f"{date_str}_{suffix}.txt"
        suffix += 1
    archive_path.write_text(new_text, encoding="utf-8")
    return True

def read_tos_summary(company_name: str) -> str | None:
    """Return the persisted summary for a company, or None if it doesn't exist."""
    summary_file = tos_archive_dir(company_name) / "summary.txt"
    if summary_file.exists():
        return summary_file.read_text(encoding="utf-8")
    return None

def write_tos_summary(company_name: str, summary: str) -> None:
    """Persist the summary text for a company."""
    archive_dir = tos_archive_dir(company_name)
    archive_dir.mkdir(parents=True, exist_ok=True)
    (archive_dir / "summary.txt").write_text(summary, encoding="utf-8")

def build_diff(old_text: str, new_text: str) -> str:
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)
    diff = list(difflib.unified_diff(old_lines, new_lines, fromfile="previous", tofile="current", n=3))
    return "".join(diff[:1000])  # Increased limit for better AI context

# ---------------------------------------------------------------------------
# Hybrid substantive diff helpers
# ---------------------------------------------------------------------------

def normalize_text(text: str) -> str:
    """Normalize TOS text to reduce noise from formatting, whitespace, and case.

    Lowercases the text, collapses runs of whitespace within lines, strips
    leading/trailing whitespace per line, and collapses excessive blank lines.
    This allows meaningful content comparisons that ignore purely cosmetic edits.
    """
    text = text.lower()
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Collapse runs of spaces/tabs within a line to a single space
    text = re.sub(r"[ \t]+", " ", text)
    # Strip each line and drop blank lines caused by stripping
    text = "\n".join(line.strip() for line in text.splitlines())
    # Collapse three or more consecutive blank lines to two
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def fallback_similarity(a: str, b: str) -> float:
    """Return a similarity score (0–1) using difflib.SequenceMatcher.

    This is the lightweight fallback used when spaCy is not installed.
    """
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


# Module-level cache for the spaCy NLP model.
# None = not yet attempted; False = unavailable; model object = loaded.
_spacy_nlp: Optional[object] = None


def _get_spacy_nlp() -> Optional[object]:
    """Lazily load and cache a spaCy model.  Returns None if unavailable."""
    global _spacy_nlp
    if _spacy_nlp is None:
        try:
            import spacy  # type: ignore
            _spacy_nlp = spacy.load("en_core_web_md")
        except Exception:
            _spacy_nlp = False
    return _spacy_nlp if _spacy_nlp is not False else None


def semantic_similarity(a: str, b: str) -> float:
    """Return a semantic similarity score (0–1).

    Uses spaCy vector similarity when available; falls back to
    ``fallback_similarity`` (SequenceMatcher) otherwise.
    """
    nlp = _get_spacy_nlp()
    if nlp is not None:
        try:
            # Truncate to avoid excessive memory use on very long texts
            doc_a = nlp(a[:25000])  # type: ignore[call-arg]
            doc_b = nlp(b[:25000])  # type: ignore[call-arg]
            return doc_a.similarity(doc_b)
        except Exception:
            pass
    return fallback_similarity(a, b)


def extract_hot_section_text(text: str) -> dict[str, str]:
    """Return a mapping of hot-section names to their relevant paragraphs.

    Splits *text* into paragraphs and assigns each paragraph to every
    hot-section whose keyword patterns it matches.
    """
    paragraphs = [p for p in re.split(r"\n{2,}", text) if p.strip()]
    sections: dict[str, list[str]] = {k: [] for k in HOT_SECTION_KEYWORDS}
    for para in paragraphs:
        for section_name, patterns in HOT_SECTION_KEYWORDS.items():
            for pattern in patterns:
                if re.search(pattern, para, re.IGNORECASE):
                    sections[section_name].append(para)
                    break
    return {k: "\n\n".join(v) for k, v in sections.items()}


def detect_substantive_change(old_text: str, new_text: str) -> tuple[bool, str]:
    """Determine whether a TOS change is substantive and return the reason.

    Returns ``(is_significant, reason)`` where *reason* is a human-readable
    explanation suitable for displaying to the user, e.g.
    ``"change detected in hot section: arbitration"``.

    Algorithm:
    1. Normalize both texts; if identical after normalization → not significant.
    2. Check each hot section: flag if similarity < ``SIMILARITY_THRESHOLD``.
    3. Flag if total document size change exceeds ``PERCENT_CHANGE_THRESHOLD``.
    4. Flag if overall semantic similarity < ``SIMILARITY_THRESHOLD``.
    """
    old_norm = normalize_text(old_text)
    new_norm = normalize_text(new_text)

    if old_norm == new_norm:
        return False, ""

    # --- Hot-section check ---
    old_sections = extract_hot_section_text(old_norm)
    new_sections = extract_hot_section_text(new_norm)
    for section_name in HOT_SECTION_KEYWORDS:
        old_sec = old_sections.get(section_name, "")
        new_sec = new_sections.get(section_name, "")
        if old_sec or new_sec:
            sim = semantic_similarity(old_sec, new_sec)
            if sim < SIMILARITY_THRESHOLD:
                return True, f"change detected in hot section: {section_name}"

    # --- Percent-change check (catches large non-hot edits) ---
    old_len = len(old_norm)
    if old_len > 0:
        # pct is a fraction (e.g. 0.05 = 5%); format with :.1% multiplies by 100
        pct = abs(len(new_norm) - old_len) / old_len
        if pct > PERCENT_CHANGE_THRESHOLD:
            return True, f"document changed by {pct:.1%}"

    # --- Overall semantic similarity check ---
    sim = semantic_similarity(old_norm, new_norm)
    if sim < SIMILARITY_THRESHOLD:
        return True, "semantic meaning changed"

    return False, ""

def call_openai(diff_text: str) -> str:
    if not OPENAI_API_KEY:
        return "AI analysis skipped: OPENAI_API_KEY not set."
    
    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": AI_TOS_SUMMARY_PROMPT},
            {"role": "user", "content": f"Here is the diff of the TOS changes:\n\n{diff_text}"},
        ],
        "max_tokens": 512,
        "temperature": 0.3,
    }
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    resp = requests.post(OPENAI_URL, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()

def call_openai_overview(tos_text: str) -> str:
    if not OPENAI_API_KEY:
        return "AI analysis skipped: OPENAI_API_KEY not set."

    # Truncate to avoid exceeding token limits while preserving key content
    truncated = tos_text[:8000]
    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": AI_TOS_SUMMARY_PROMPT},
            {"role": "user", "content": f"Here is the Terms of Service text:\n\n{truncated}"},
        ],
        "max_tokens": 512,
        "temperature": 0.3,
    }
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    resp = requests.post(OPENAI_URL, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()

# ---------------------------------------------------------------------------
# Main monitoring loop
# ---------------------------------------------------------------------------

def monitor() -> dict:
    ensure_dirs()
    companies_config = load_config()
    now = datetime.now(timezone.utc).isoformat()
    company_results: list[dict] = []

    for company in companies_config:
        name: str = company.get("name", "")
        tos_url: str = company.get("tosUrl", "")
        category: str = company.get("category", "")
        last_checked = datetime.now(timezone.utc).isoformat()

        print(f"Scanning {name}...")

        try:
            new_text = fetch_text(tos_url)
        except Exception as exc:
            print(f"Error fetching {name}: {exc}")
            company_results.append({
                "name": name,
                "category": category,
                "tosUrl": tos_url,
                "lastChecked": last_checked,
                "changed": False,
                "changeReason": "",
                "summary": read_tos_summary(name) or f"Connection Error: {exc}",
            })
            continue

        old_text = read_snapshot(name)
        write_snapshot(name, new_text)

        # Content-diff method: compare the newly fetched ToS against the most
        # recently archived version.  `archived=True` means the raw text has
        # changed; `archived=False` means it is byte-for-byte identical.
        # Every new version is always archived; significance is determined
        # separately by detect_substantive_change below.
        archived = archive_tos_if_changed(name, new_text)

        if not archived:
            # ToS content is unchanged – reuse the persisted summary without
            # calling the AI API.  This is the core of the content-diff method.
            summary = read_tos_summary(name) or "Initial snapshot created. Monitoring active."
            company_results.append({
                "name": name,
                "category": category,
                "tosUrl": tos_url,
                "lastChecked": last_checked,
                "changed": False,
                "changeReason": "",
                "summary": summary,
            })
            continue

        # Raw text changed – determine whether the change is *substantive*
        # using the hybrid diff logic (hot sections, percent change, semantics).
        if old_text is not None:
            is_significant, change_reason = detect_substantive_change(old_text, new_text)
        else:
            # First version ever archived – always treat as significant.
            is_significant = True
            change_reason = "first version archived"

        if not is_significant:
            # Change is noise (formatting/whitespace/trivial wording) – archive
            # was already written above; skip AI and keep the existing summary
            # so the user is not alerted unnecessarily.
            summary = read_tos_summary(name) or "Initial snapshot created. Monitoring active."
            company_results.append({
                "name": name,
                "category": category,
                "tosUrl": tos_url,
                "lastChecked": last_checked,
                "changed": False,
                "changeReason": "",
                "summary": summary,
            })
            continue

        # Substantive change – generate a new AI summary and persist it.
        if old_text is not None and old_text != new_text:
            # Incremental change: generate a diff-focused summary.
            diff_text = build_diff(old_text, new_text)
            try:
                summary = call_openai(diff_text)
            except Exception as exc:
                summary = f"Connection Error: AI analysis failed – {exc}"
        else:
            # First version or snapshot missing: generate a full overview summary.
            try:
                summary = call_openai_overview(new_text)
            except Exception as exc:
                summary = f"Connection Error: AI overview failed – {exc}"

        write_tos_summary(name, summary)

        company_results.append({
            "name": name,
            "category": category,
            "tosUrl": tos_url,
            "lastChecked": last_checked,
            "changed": True,
            "changeReason": change_reason,
            "summary": summary,
        })

    results = {"updatedAt": now, "companies": company_results}
    return results

def write_results(results: dict) -> None:
    payload = json.dumps(results, indent=2, ensure_ascii=False)
    PUBLIC_RESULTS_PATH.write_text(payload, encoding="utf-8")
    DATA_RESULTS_PATH.write_text(payload, encoding="utf-8")

def validate_results(results: dict) -> None:
    assert isinstance(results, dict)
    assert "companies" in results
    print("✅ Validation passed: results.json structure is correct.")

if __name__ == "__main__":
    final_results = monitor()
    write_results(final_results)
    validate_results(final_results)
    print(f"Done. Checked {len(final_results['companies'])} companies.")
    sys.exit(0)
