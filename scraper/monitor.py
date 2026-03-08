"""
scraper/monitor.py – Modular backend for Diffy.
Uses Playwright to bypass aggressive bot detection (Cloudflare 403s).
Outputs a versioned, verdict-tagged results.json with full history.
"""

import difflib
import hashlib
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
from playwright_stealth import Stealth

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.json"
SNAPSHOTS_DIR = BASE_DIR / "data" / "snapshots"
DATA_RESULTS_PATH = BASE_DIR / "data" / "results.json"
# Also write to public/data so the Vite frontend picks it up during dev/build
PUBLIC_RESULTS_PATH = BASE_DIR.parent / "public" / "data" / "results.json"
TOS_DIR = BASE_DIR / "terms_of_service"

# ---------------------------------------------------------------------------
# Hybrid substantive diff configuration
# ---------------------------------------------------------------------------

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

SIMILARITY_THRESHOLD: float = 0.95
PERCENT_CHANGE_THRESHOLD: float = 0.04

# ---------------------------------------------------------------------------
# Pre-cleaning: skip/ignore line patterns
# ---------------------------------------------------------------------------

SKIPPED_LINE_PATTERNS: list[re.Pattern] = [
    re.compile(r"\btrace[\s\-]?id\b", re.IGNORECASE),
    re.compile(r"\brequest[\s\-]?id\b", re.IGNORECASE),
    re.compile(r"\bsession[\s\-]?id\b", re.IGNORECASE),
    re.compile(r"\bcorrelation[\s\-]?id\b", re.IGNORECASE),
    re.compile(r"^\s*last\s+updated\s*:", re.IGNORECASE),
    re.compile(r"^\s*effective\s+date\s*:", re.IGNORECASE),
    re.compile(r"\bverifying\s+you\s+are\s+human\b", re.IGNORECASE),
    re.compile(r"\bbot[\s\-]?detection\b", re.IGNORECASE),
    re.compile(r"\bcaptcha\b", re.IGNORECASE),
    re.compile(r"\bjust\s+a\s+moment\b", re.IGNORECASE),
    re.compile(r"\bcloudflare\s+ray\s+id\b", re.IGNORECASE),
    re.compile(r"\bincident[\s\-]?id\b", re.IGNORECASE),
    re.compile(r"^\s*version\s+\d[\d\.]*\s*[\-–—]", re.IGNORECASE),
]


def pre_clean_text(text: str) -> str:
    """Remove dynamic/scaffold lines from raw ToS text before comparison."""
    cleaned_lines = [
        line for line in text.splitlines()
        if not any(pat.search(line) for pat in SKIPPED_LINE_PATTERNS)
    ]
    return "\n".join(cleaned_lines)


# ---------------------------------------------------------------------------
# Navigation preamble filtering
# ---------------------------------------------------------------------------

NAV_TITLE_ANCHORS: list[re.Pattern] = [
    re.compile(r"^\s*terms\s+of\s+(?:use|service)\b", re.IGNORECASE),
    re.compile(r"^\s*terms\s+and\s+conditions\b", re.IGNORECASE),
    re.compile(r"^\s*user\s+agreement\b", re.IGNORECASE),
    re.compile(r"^\s*acceptable\s+use\s+policy\b", re.IGNORECASE),
    re.compile(r"^\s*legal\s+terms\b", re.IGNORECASE),
]


def strip_navigation_preamble(text: str) -> str:
    """Remove leading navigation/UI content from fetched ToS text."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        for pattern in NAV_TITLE_ANCHORS:
            if pattern.search(line):
                return "\n".join(lines[i:])
    return text


# ---------------------------------------------------------------------------
# Appendix / footer filtering
# ---------------------------------------------------------------------------

APPENDIX_TRIGGER_PATTERNS: list[str] = [
    r"open[\s\-]source",
    r"acknowledg",
    r"third[\s\-]party\s+librar",
    r"third[\s\-]party\s+software",
    r"licens",
    r"librar(?:ies|y)",
    r"copyright",
    r"attribution",
]

APPENDIX_SEARCH_START_FRACTION: float = 0.60
MIN_LINES_FOR_APPENDIX_DETECTION: int = 5

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

AI_DIFF_SUMMARY_PROMPT = (
    "You are a strict legal analysis engine. "
    "Analyze the provided Terms of Service diff and return ONLY a valid JSON object — no prose, no markdown, no explanation. "
    "The JSON must have exactly these three keys: \"Privacy\", \"DataOwnership\", \"UserRights\". "
    "Each value must be a concise plain string (max 30 words) summarizing only the changes in that category. "
    "If a category has no relevant changes, the value must be exactly: \"No significant changes detected\". "
    "Output must be valid JSON and nothing else."
)

# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------

def sha256_hash(text: str) -> str:
    """Return the SHA-256 hex digest of the given text (UTF-8 encoded)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Verdict assignment
# ---------------------------------------------------------------------------

_CAUTION_KEYWORDS = frozenset([
    "privacy", "user_data", "arbitration", "dispute", "termination", "ai",
])

_CAUTION_CONTENT_WORDS = [
    "restrict", "limit", "prohibit", "sell", "sold", "share", "waive",
    "class action", "mandatory", "collected", "retain",
]


def assign_verdict(change_reason: str, diff_summary: dict) -> str:
    """Assign Good / Neutral / Caution based on change reason and diff content.

    - "Good"    – no substantive change (should not normally appear in history)
    - "Neutral" – substantive but low-risk change
    - "Caution" – change involves a high-risk section (privacy, arbitration, etc.)
    """
    if not change_reason:
        return "Good"

    reason_lower = change_reason.lower()
    for kw in _CAUTION_KEYWORDS:
        if kw in reason_lower:
            return "Caution"

    for key in ("Privacy", "DataOwnership", "UserRights"):
        val = diff_summary.get(key, "").lower()
        if any(w in val for w in _CAUTION_CONTENT_WORDS):
            return "Caution"

    return "Neutral"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ensure_dirs() -> None:
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    TOS_DIR.mkdir(parents=True, exist_ok=True)
    PUBLIC_RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)


def load_config() -> list[dict]:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("companies", [])


def snapshot_path(company_name: str) -> Path:
    safe = re.sub(r"[^\w\-]", "_", company_name)
    return SNAPSHOTS_DIR / f"{safe}.txt"


def fetch_text(url: str, max_retries: int = 3) -> str:
    """Fetch URL using a headless browser with stealth patterns."""
    last_exc: Exception = Exception(f"All {max_retries} attempts to fetch {url} failed.")

    for attempt in range(1, max_retries + 1):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--disable-http2"])
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            stealth = Stealth()
            stealth.apply_stealth_sync(page)

            try:
                time.sleep(random.uniform(1, 3))
                page.goto(url, wait_until="domcontentloaded", timeout=90000)
                html_content = page.content()
                soup = BeautifulSoup(html_content, "html.parser")
                for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside"]):
                    tag.decompose()
                return soup.get_text(separator="\n", strip=True)

            except Exception as e:
                last_exc = e
                print(f"  [attempt {attempt}/{max_retries}] Failed to fetch {url}: {e}")
                if attempt < max_retries:
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
    return re.sub(r"[^\w\-]", "_", company_name)


def tos_archive_dir(company_name: str) -> Path:
    return TOS_DIR / company_slug(company_name)


def get_latest_archived_tos(company_name: str) -> str | None:
    archive_dir = tos_archive_dir(company_name)
    if not archive_dir.exists():
        return None
    dated_files = sorted(f for f in archive_dir.glob("*.txt") if f.name != "summary.txt")
    if not dated_files:
        return None
    return dated_files[-1].read_text(encoding="utf-8")


def archive_tos_if_changed(company_name: str, new_text: str) -> bool:
    """Save new_text as a dated archive file if it differs from the latest archived version."""
    archive_dir = tos_archive_dir(company_name)
    archive_dir.mkdir(parents=True, exist_ok=True)
    if get_latest_archived_tos(company_name) == new_text:
        return False
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    existing_today = sorted(
        f for f in archive_dir.glob("*.txt")
        if f.name != "summary.txt" and f.stem.startswith(date_str)
    )
    if not existing_today:
        archive_path = archive_dir / f"{date_str}.txt"
    else:
        suffix = len(existing_today)
        archive_path = archive_dir / f"{date_str}_{suffix}.txt"
        while archive_path.exists():
            suffix += 1
            archive_path = archive_dir / f"{date_str}_{suffix}.txt"
    archive_path.write_text(new_text, encoding="utf-8")
    return True


def prune_old_tos_archives(company_name: str) -> int:
    """Delete all but the most-recent dated snapshot for a company."""
    archive_dir = tos_archive_dir(company_name)
    if not archive_dir.exists():
        return 0
    dated_files = sorted(f for f in archive_dir.glob("*.txt") if f.name != "summary.txt")
    if len(dated_files) <= 1:
        return 0
    to_delete = dated_files[:-1]
    for f in to_delete:
        f.unlink()
    return len(to_delete)


def read_tos_summary(company_name: str) -> str | None:
    summary_file = tos_archive_dir(company_name) / "summary.txt"
    if summary_file.exists():
        return summary_file.read_text(encoding="utf-8")
    return None


def write_tos_summary(company_name: str, summary: str) -> None:
    archive_dir = tos_archive_dir(company_name)
    archive_dir.mkdir(parents=True, exist_ok=True)
    (archive_dir / "summary.txt").write_text(summary, encoding="utf-8")


def build_diff(old_text: str, new_text: str) -> str:
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)
    diff = list(difflib.unified_diff(old_lines, new_lines, fromfile="previous", tofile="current", n=3))
    return "".join(diff[:1000])


# ---------------------------------------------------------------------------
# Hybrid substantive diff helpers
# ---------------------------------------------------------------------------

def normalize_text(text: str) -> str:
    text = text.lower()
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_core_content(text: str) -> str:
    """Return the main ToS content, excluding any trailing appendix/footer region."""
    if not text:
        return text
    lines = text.splitlines()
    total = len(lines)
    if total < MIN_LINES_FOR_APPENDIX_DETECTION:
        return text
    search_start = max(1, int(total * APPENDIX_SEARCH_START_FRACTION))
    for i in range(search_start, total):
        for pattern in APPENDIX_TRIGGER_PATTERNS:
            if re.search(pattern, lines[i], re.IGNORECASE):
                core = "\n".join(lines[:i]).rstrip()
                return core if core else text
    return text


def fallback_similarity(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


_spacy_nlp: Optional[object] = None


def _get_spacy_nlp() -> Optional[object]:
    global _spacy_nlp
    if _spacy_nlp is None:
        try:
            import spacy  # type: ignore
            _spacy_nlp = spacy.load("en_core_web_md")
        except Exception:
            _spacy_nlp = False
    return _spacy_nlp if _spacy_nlp is not False else None


def semantic_similarity(a: str, b: str) -> float:
    nlp = _get_spacy_nlp()
    if nlp is not None:
        try:
            doc_a = nlp(a[:25000])  # type: ignore[call-arg]
            doc_b = nlp(b[:25000])  # type: ignore[call-arg]
            return doc_a.similarity(doc_b)
        except Exception:
            pass
    return fallback_similarity(a, b)


def extract_hot_section_text(text: str) -> dict[str, str]:
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
    old_norm = normalize_text(extract_core_content(pre_clean_text(old_text)))
    new_norm = normalize_text(extract_core_content(pre_clean_text(new_text)))

    if old_norm == new_norm:
        return False, ""

    old_sections = extract_hot_section_text(old_norm)
    new_sections = extract_hot_section_text(new_norm)
    for section_name in HOT_SECTION_KEYWORDS:
        old_sec = old_sections.get(section_name, "")
        new_sec = new_sections.get(section_name, "")
        if old_sec or new_sec:
            sim = semantic_similarity(old_sec, new_sec)
            if sim < SIMILARITY_THRESHOLD:
                return True, f"change detected in hot section: {section_name}"

    old_len = len(old_norm)
    if old_len > 0:
        pct = abs(len(new_norm) - old_len) / old_len
        if pct > PERCENT_CHANGE_THRESHOLD:
            return True, f"document changed by {pct:.1%}"

    sim = semantic_similarity(old_norm, new_norm)
    if sim < SIMILARITY_THRESHOLD:
        return True, "semantic meaning changed"

    return False, ""


# ---------------------------------------------------------------------------
# OpenAI helpers
# ---------------------------------------------------------------------------

def _openai_post(messages: list[dict], max_tokens: int = 512) -> str:
    """POST to OpenAI and return the assistant message content."""
    if not OPENAI_API_KEY:
        return ""
    payload = {
        "model": OPENAI_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
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
    """Generate a plain-text overview summary of the full ToS."""
    if not OPENAI_API_KEY:
        return "AI analysis skipped: OPENAI_API_KEY not set."
    truncated = tos_text[:8000]  # ~2 000 GPT-4o-mini tokens; keeps costs low and avoids context limits
    try:
        return _openai_post([
            {"role": "system", "content": AI_TOS_SUMMARY_PROMPT},
            {"role": "user", "content": f"Here is the Terms of Service text:\n\n{truncated}"},
        ])
    except Exception as exc:
        return f"Connection Error: AI overview failed – {exc}"


def call_openai_diff_summary(diff_text: str) -> dict:
    """Generate a structured diff summary broken down by Privacy/DataOwnership/UserRights.

    Returns a dict with keys: Privacy, DataOwnership, UserRights.
    Falls back to plain strings if OpenAI is unavailable or JSON parsing fails.
    """
    empty = {"Privacy": "No significant changes detected", "DataOwnership": "No significant changes detected", "UserRights": "No significant changes detected"}
    if not OPENAI_API_KEY:
        return empty

    try:
        raw = _openai_post([
            {"role": "system", "content": AI_DIFF_SUMMARY_PROMPT},
            {"role": "user", "content": f"Here is the diff of the TOS changes:\n\n{diff_text}"},
        ], max_tokens=256)
    except Exception as exc:
        print(f"  [OpenAI diff summary error] {exc}")
        return {k: f"AI analysis failed: {exc}" for k in empty}

    # Strip markdown fences if model wrapped output anyway
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned.strip())

    try:
        parsed = json.loads(cleaned)
        return {
            "Privacy": str(parsed.get("Privacy", empty["Privacy"])),
            "DataOwnership": str(parsed.get("DataOwnership", empty["DataOwnership"])),
            "UserRights": str(parsed.get("UserRights", empty["UserRights"])),
        }
    except json.JSONDecodeError:
        # If the model didn't return valid JSON, use the raw text for all keys
        return {k: raw[:120] for k in empty}


def call_openai_first_summary(tos_text: str) -> dict:
    """Generate a structured summary for the first version of a ToS."""
    overview = call_openai_overview(tos_text)
    return {
        "Privacy": overview,
        "DataOwnership": "No significant change",
        "UserRights": "No significant change",
    }


# ---------------------------------------------------------------------------
# History management
# ---------------------------------------------------------------------------

def load_existing_results() -> dict:
    """Load the existing results.json (if any) so we can append to history."""
    for path in (DATA_RESULTS_PATH, PUBLIC_RESULTS_PATH):
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
    return {}


def get_company_history(existing_results: dict, company_name: str) -> list[dict]:
    """Return the existing history list for a company from the loaded results."""
    for c in existing_results.get("companies", []):
        if c.get("name") == company_name:
            return list(c.get("history", []))
    return []


# ---------------------------------------------------------------------------
# Main monitoring loop
# ---------------------------------------------------------------------------

def monitor() -> dict:
    ensure_dirs()
    companies_config = load_config()
    now = datetime.now(timezone.utc).isoformat()
    existing_results = load_existing_results()
    company_results: list[dict] = []

    for company in companies_config:
        name: str = company.get("name", "")
        tos_url: str = company.get("tosUrl", "")
        category: str = company.get("category", "")
        last_checked = datetime.now(timezone.utc).isoformat()

        print(f"Scanning {name}...")

        # Load existing history for this company so we can append to it
        history: list[dict] = get_company_history(existing_results, name)

        try:
            new_text = strip_navigation_preamble(fetch_text(tos_url))
        except Exception as exc:
            print(f"Error fetching {name}: {exc}")
            latest_summary = read_tos_summary(name) or f"Connection Error: {exc}"
            company_results.append({
                "name": name,
                "category": category,
                "tosUrl": tos_url,
                "lastChecked": last_checked,
                "latestSummary": latest_summary,
                "history": history,
            })
            continue

        current_hash = sha256_hash(new_text)
        old_text = read_snapshot(name)
        previous_hash = sha256_hash(old_text) if old_text is not None else None
        write_snapshot(name, new_text)

        archived = archive_tos_if_changed(name, new_text)

        if not archived:
            # Content unchanged – no new history entry needed
            latest_summary = read_tos_summary(name) or "Initial snapshot created. Monitoring active."
            company_results.append({
                "name": name,
                "category": category,
                "tosUrl": tos_url,
                "lastChecked": last_checked,
                "latestSummary": latest_summary,
                "history": history,
            })
            continue

        # Raw text changed – determine substantive change
        if old_text is not None:
            is_significant, change_reason = detect_substantive_change(old_text, new_text)
        else:
            is_significant = True
            change_reason = "first version archived"

        if not is_significant:
            # Non-substantive change (whitespace / cosmetic) – archive written,
            # but we do NOT add a history entry or regenerate the summary.
            latest_summary = read_tos_summary(name) or "Initial snapshot created. Monitoring active."
            company_results.append({
                "name": name,
                "category": category,
                "tosUrl": tos_url,
                "lastChecked": last_checked,
                "latestSummary": latest_summary,
                "history": history,
            })
            continue

        # Substantive change – generate structured diff summary
        if old_text is not None and old_text != new_text:
            diff_text = build_diff(old_text, new_text)
            diff_summary = call_openai_diff_summary(diff_text)
        else:
            diff_summary = call_openai_first_summary(new_text)

        verdict = assign_verdict(change_reason, diff_summary)

        # Flatten diff_summary to a plain-text string for latestSummary
        latest_summary = " | ".join(
            f"[{k}]: {v}" for k, v in diff_summary.items()
            if v and v != "No significant change"
        ) or "No significant change detected."

        write_tos_summary(name, latest_summary)

        # Append new history entry (chronological; oldest first)
        new_entry: dict = {
            "previous_hash": previous_hash,
            "current_hash": current_hash,
            "timestamp": last_checked,
            "verdict": verdict,
            "diffSummary": diff_summary,
            "changeIsSubstantial": True,
            "changeReason": change_reason,
        }
        history.append(new_entry)

        company_results.append({
            "name": name,
            "category": category,
            "tosUrl": tos_url,
            "lastChecked": last_checked,
            "latestSummary": latest_summary,
            "history": history,
        })

    results = {
        "schemaVersion": "2.0",
        "updatedAt": now,
        "companies": company_results,
    }
    return results


def write_results(results: dict) -> None:
    payload = json.dumps(results, indent=2, ensure_ascii=False)
    try:
        json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"write_results: serialised payload is not valid JSON – aborting write. "
            f"JSONDecodeError: {exc}"
        ) from exc
    DATA_RESULTS_PATH.write_text(payload, encoding="utf-8")
    PUBLIC_RESULTS_PATH.write_text(payload, encoding="utf-8")


# ---------------------------------------------------------------------------
# Summary index – lightweight snapshot for fast initial page loads
# ---------------------------------------------------------------------------

SUMMARY_INDEX_PATH = BASE_DIR / "data" / "summary_index.json"
PUBLIC_SUMMARY_INDEX_PATH = BASE_DIR.parent / "public" / "data" / "summary_index.json"


def write_summary_index(results: dict) -> None:
    """Write a trimmed summary_index.json containing only the latest history
    entry per company. The frontend can load this for a fast initial render;
    full history stays in results.json and is fetched on demand.
    """
    summary_companies = []
    for company in results.get("companies", []):
        history = company.get("history", [])
        latest_entry = history[-1] if history else None
        summary_companies.append({
            "name": company.get("name"),
            "category": company.get("category"),
            "tosUrl": company.get("tosUrl"),
            "lastChecked": company.get("lastChecked"),
            "latestSummary": company.get("latestSummary"),
            "history": [latest_entry] if latest_entry else [],
        })

    index = {
        "schemaVersion": results.get("schemaVersion", "2.0"),
        "updatedAt": results.get("updatedAt"),
        "companies": summary_companies,
    }
    payload = json.dumps(index, indent=2, ensure_ascii=False)
    SUMMARY_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_INDEX_PATH.write_text(payload, encoding="utf-8")
    PUBLIC_SUMMARY_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC_SUMMARY_INDEX_PATH.write_text(payload, encoding="utf-8")
    print(f"Summary index written ({len(summary_companies)} companies).")


# ---------------------------------------------------------------------------
# Favicon fetching
# ---------------------------------------------------------------------------

FAVICONS_DIR = BASE_DIR.parent / "public" / "favicons"


def fetch_and_store_favicons(companies_config: list[dict]) -> None:
    """Fetch company favicons from Google S2 and cache them locally under
    public/favicons/{domain}.png so the frontend can serve them without
    an external request.
    """
    FAVICONS_DIR.mkdir(parents=True, exist_ok=True)
    for company in companies_config:
        tos_url = company.get("tosUrl", "")
        try:
            from urllib.parse import urlparse
            hostname = urlparse(tos_url).hostname or ""
            domain = hostname.replace("www.", "", 1)
            if not domain:
                continue
            dest = FAVICONS_DIR / f"{domain}.png"
            if dest.exists():
                continue  # already cached
            favicon_url = f"https://www.google.com/s2/favicons?sz=32&domain={domain}"
            resp = requests.get(favicon_url, timeout=10)
            if resp.status_code == 200:
                dest.write_bytes(resp.content)
                print(f"  Saved favicon for {domain}")
        except Exception as exc:
            print(f"  [favicon] Could not fetch for {company.get('name')}: {exc}")


def validate_results(results: dict) -> None:
    assert isinstance(results, dict), "results must be a dict"
    assert "companies" in results, "results must have 'companies' key"
    assert results.get("schemaVersion") == "2.0", "schemaVersion must be '2.0'"
    for company in results["companies"]:
        assert "name" in company, f"company missing 'name': {company}"
        assert "history" in company, f"company '{company.get('name')}' missing 'history'"
        assert "latestSummary" in company, f"company '{company.get('name')}' missing 'latestSummary'"
        for entry in company["history"]:
            assert "current_hash" in entry, f"history entry missing 'current_hash'"
            assert "timestamp" in entry, f"history entry missing 'timestamp'"
            assert "verdict" in entry, f"history entry missing 'verdict'"
            assert entry["verdict"] in ("Good", "Neutral", "Caution"), \
                f"verdict must be Good/Neutral/Caution, got: {entry['verdict']}"
            assert "diffSummary" in entry, f"history entry missing 'diffSummary'"
    try:
        round_tripped = json.loads(json.dumps(results, ensure_ascii=False))
        assert isinstance(round_tripped, dict)
    except (json.JSONDecodeError, AssertionError) as exc:
        raise ValueError(f"validate_results: JSON round-trip check failed – {exc}") from exc
    print("✅ Validation passed: results.json structure is correct.")


if __name__ == "__main__":
    final_results = monitor()
    write_results(final_results)
    write_summary_index(final_results)
    validate_results(final_results)
    fetch_and_store_favicons(load_config())
    print(f"Done. Checked {len(final_results['companies'])} companies.")
    sys.exit(0)
