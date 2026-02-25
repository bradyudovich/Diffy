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
# OpenAI API Settings
# ---------------------------------------------------------------------------
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_MODEL = "gpt-4o-mini"
AI_SYSTEM_PROMPT = (
    "You are a legal analyst. Compare these two versions of a Terms of Service. "
    "Summarize if the change affects how user data is used for AI training or if "
    "it reduces user privacy. Categorize the severity as High, Medium, or Low."
)
AI_OVERVIEW_PROMPT = (
    "You are a plain-English legal analyst. Given the following Terms of Service text, "
    "provide a concise, high-level overview (3-5 sentences) for a general audience. "
    "Explain the key obligations for the user, any notable rights the user retains, "
    "data privacy implications, and any significant risks or restrictions. "
    "Write clearly and avoid legal jargon."
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

def call_openai(diff_text: str) -> str:
    if not OPENAI_API_KEY:
        return "AI analysis skipped: OPENAI_API_KEY not set."
    
    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": AI_SYSTEM_PROMPT},
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
            {"role": "system", "content": AI_OVERVIEW_PROMPT},
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
                "summary": read_tos_summary(name) or f"Connection Error: {exc}",
            })
            continue

        old_text = read_snapshot(name)
        write_snapshot(name, new_text)

        # Archive the new version if it differs from the latest archived copy
        archived = archive_tos_if_changed(name, new_text)

        if old_text is None or old_text == new_text:
            # No snapshot change this run – generate/refresh summary only when a
            # new archive version was saved (first time or archive was absent)
            if archived or read_tos_summary(name) is None:
                try:
                    overview = call_openai_overview(new_text)
                except Exception as exc:
                    overview = f"Connection Error: AI overview failed – {exc}"
                write_tos_summary(name, overview)
            summary = read_tos_summary(name) or "Initial snapshot created. Monitoring active."
            company_results.append({
                "name": name,
                "category": category,
                "tosUrl": tos_url,
                "lastChecked": last_checked,
                "changed": False,
                "summary": summary,
            })
            continue

        # Text changed – generate a diff summary and persist it
        diff_text = build_diff(old_text, new_text)
        try:
            summary = call_openai(diff_text)
        except Exception as exc:
            summary = f"Connection Error: AI analysis failed – {exc}"

        write_tos_summary(name, summary)

        company_results.append({
            "name": name,
            "category": category,
            "tosUrl": tos_url,
            "lastChecked": last_checked,
            "changed": True,
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
