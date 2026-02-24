"""
monitor.py – Phase 2 backend script for Diffy.

Scrapes each Terms-of-Service URL from config.json, maintains per-company
snapshots, calls OpenAI only when the text changes, and writes results to
both public/data/results.json and data/results.json.
"""

import difflib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.json"
SNAPSHOTS_DIR = BASE_DIR / "data" / "snapshots"
DATA_RESULTS_PATH = BASE_DIR / "data" / "results.json"
PUBLIC_RESULTS_PATH = BASE_DIR / "public" / "data" / "results.json"

# ---------------------------------------------------------------------------
# OpenAI
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
    """Fetch URL and return visible text content."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; Diffy/1.0; +https://github.com/bradyudovich/Diffy)"
        )
    }
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)


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
    diff = list(
        difflib.unified_diff(old_lines, new_lines, fromfile="previous", tofile="current", n=3)
    )
    return "".join(diff[:500])  # cap to avoid huge prompts


def call_openai(diff_text: str) -> str:
    if not OPENAI_API_KEY:
        return "AI analysis skipped: OPENAI_API_KEY not set."
    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": AI_SYSTEM_PROMPT},
            {"role": "user", "content": diff_text},
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

        try:
            new_text = fetch_text(tos_url)
        except Exception as exc:  # noqa: BLE001
            company_results.append(
                {
                    "name": name,
                    "tosUrl": tos_url,
                    "lastChecked": last_checked,
                    "changed": False,
                    "summary": f"Connection Error: {exc}",
                }
            )
            continue

        old_text = read_snapshot(name)
        write_snapshot(name, new_text)

        if old_text is None or old_text == new_text:
            company_results.append(
                {
                    "name": name,
                    "tosUrl": tos_url,
                    "lastChecked": last_checked,
                    "changed": False,
                    "summary": None,
                }
            )
            continue

        # Text changed – call OpenAI
        diff_text = build_diff(old_text, new_text)
        try:
            summary = call_openai(diff_text)
        except Exception as exc:  # noqa: BLE001
            summary = f"Connection Error: AI analysis failed – {exc}"

        company_results.append(
            {
                "name": name,
                "tosUrl": tos_url,
                "lastChecked": last_checked,
                "changed": True,
                "summary": summary,
            }
        )

    results = {"updatedAt": now, "companies": company_results}
    return results


def write_results(results: dict) -> None:
    payload = json.dumps(results, indent=2, ensure_ascii=False)
    PUBLIC_RESULTS_PATH.write_text(payload, encoding="utf-8")
    DATA_RESULTS_PATH.write_text(payload, encoding="utf-8")


# ---------------------------------------------------------------------------
# Validation / test
# ---------------------------------------------------------------------------

def validate_results(results: dict) -> None:
    """Validate that *results* matches the Phase 1 schema and print success."""
    assert isinstance(results, dict), "results must be a dict"
    assert "companies" in results, "results must have 'companies' key"
    assert isinstance(results["companies"], list), "'companies' must be a list"

    if "updatedAt" in results:
        assert isinstance(results["updatedAt"], str), "'updatedAt' must be a string"

    for company in results["companies"]:
        assert isinstance(company, dict), "each company must be a dict"
        assert isinstance(company.get("name"), str), "'name' must be a string"
        assert isinstance(company.get("tosUrl"), str), "'tosUrl' must be a string"

        if company.get("lastChecked") is not None:
            assert isinstance(company["lastChecked"], str), "'lastChecked' must be a string"
        if company.get("changed") is not None:
            assert isinstance(company["changed"], bool), "'changed' must be a bool"
        if company.get("summary") is not None:
            assert isinstance(company["summary"], str), "'summary' must be a string"

    print("✅ Validation passed: results.json matches the expected schema.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    results = monitor()
    write_results(results)
    validate_results(results)
    print(f"Done. Checked {len(results['companies'])} company/companies.")
    sys.exit(0)
