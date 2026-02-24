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

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ensure_dirs() -> None:
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    PUBLIC_RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)

def load_config() -> list[dict]:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("companies", [])

def snapshot_path(company_name: str) -> Path:
    safe = re.sub(r"[^\w\-]", "_", company_name)
    return SNAPSHOTS_DIR / f"{safe}.txt"

def fetch_text(url: str) -> str:
    """Fetch URL using a headless browser with updated stealth patterns."""
    with sync_playwright() as p:
        # Launch Chromium
        browser = p.chromium.launch(headless=True)
        
        # Set a realistic user agent
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        
        page = context.new_page()
        
        # NEW VERSION: Use the Stealth class to apply evasion patterns
        stealth = Stealth()
        stealth.apply_stealth_sync(page)
        
        try:
            # Human-like delay
            time.sleep(random.uniform(1, 3))
            
            # Go to URL and wait for the page to finish loading
            page.goto(url, wait_until="networkidle", timeout=60000)
            
            # Get rendered HTML
            html_content = page.content()
            soup = BeautifulSoup(html_content, "html.parser")
            
            # Remove scripts, styles, and common UI elements to keep legal text clean
            for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside"]):
                tag.decompose()
                
            return soup.get_text(separator="\n", strip=True)
            
        except Exception as e:
            raise Exception(f"Playwright failed to fetch {url}: {e}")
        finally:
            browser.close()

def read_snapshot(company_name: str) -> str | None:
    path = snapshot_path(company_name)
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None

def write_snapshot(company_name: str, text: str) -> None:
    snapshot_path(company_name).write_text(text, encoding="utf-8")

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
        last_checked = datetime.now(timezone.utc).isoformat()

        print(f"Scanning {name}...")

        try:
            new_text = fetch_text(tos_url)
        except Exception as exc:
            print(f"Error fetching {name}: {exc}")
            company_results.append({
                "name": name,
                "tosUrl": tos_url,
                "lastChecked": last_checked,
                "changed": False,
                "summary": f"Connection Error: {exc}",
            })
            continue

        old_text = read_snapshot(name)
        write_snapshot(name, new_text)

        if old_text is None or old_text == new_text:
            company_results.append({
                "name": name,
                "tosUrl": tos_url,
                "lastChecked": last_checked,
                "changed": False,
                "summary": None if old_text else "Initial snapshot created. Monitoring active.",
            })
            continue

        # Text changed – call OpenAI
        diff_text = build_diff(old_text, new_text)
        try:
            summary = call_openai(diff_text)
        except Exception as exc:
            summary = f"Connection Error: AI analysis failed – {exc}"

        company_results.append({
            "name": name,
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
