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
WATCHLIST_PATH = BASE_DIR / "watchlist.json"
CASES_PATH = BASE_DIR / "cases.json"
SNAPSHOTS_DIR = BASE_DIR / "data" / "snapshots"
DATA_RESULTS_PATH = BASE_DIR / "data" / "results.json"
# Also write to public/data so the Vite frontend picks it up during dev/build
PUBLIC_RESULTS_PATH = BASE_DIR.parent / "public" / "data" / "results.json"
TOS_DIR = BASE_DIR / "terms_of_service"

SCHEMA_VERSION = "2.2"

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

AI_POINTS_PROMPT = (
    "You are a strict legal analysis engine specializing in consumer rights. "
    "Analyze the provided Terms of Service text and return ONLY a valid JSON array — no prose, no markdown, no explanation. "
    "Each element must be an object with exactly four keys: "
    "\"text\" (a plain string, max 20 words summarising the point), "
    "\"impact\" (one of: \"positive\", \"negative\", \"neutral\"), "
    "\"case_id\" (a short kebab-case identifier matching one of the known case types such as: "
    "\"data-training\", \"arbitration-clause\", \"data-sold-third-parties\", \"no-class-action\", "
    "\"data-shared-advertising\", \"account-deletion-right\", \"content-ownership-retained\", "
    "\"broad-license-grant\", \"liability-cap\", \"transparent-data-practices\", or \"other\" if none match), "
    "\"quote\" (a verbatim excerpt, max 40 words, from the Terms of Service text that supports this point — "
    "copy exact wording from the source). "
    "Return between 5 and 8 points. Be critical and realistic: most ToS documents contain several negative clauses. "
    "Mark as \"negative\" any clause that: restricts user rights, allows data selling or sharing with third parties, "
    "enables AI training on user content without explicit opt-in, includes mandatory arbitration, waives class-action rights, "
    "retains vague rights to user data, lacks clarity, or uses excessive legal jargon that obscures user rights. "
    "Mark as \"positive\" only clear, explicit user-friendly guarantees (e.g. users retain content ownership, "
    "data is never sold, explicit right to delete account and data). "
    "Focus on: data rights, AI training usage, user content ownership, liability caps, arbitration clauses, and data sharing. "
    "Output must be a valid JSON array and nothing else."
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


def load_watchlist() -> list[str]:
    """Load high-risk keyword terms from watchlist.json."""
    if WATCHLIST_PATH.exists():
        try:
            with open(WATCHLIST_PATH, encoding="utf-8") as f:
                data = json.load(f)
            return [str(t) for t in data.get("terms", [])]
        except (json.JSONDecodeError, OSError):
            pass
    return []


def load_cases() -> list[dict]:
    """Load the standardized case definitions from cases.json."""
    if CASES_PATH.exists():
        try:
            with open(CASES_PATH, encoding="utf-8") as f:
                data = json.load(f)
            return data.get("cases", [])
        except (json.JSONDecodeError, OSError):
            pass
    return []


def _build_cases_index() -> dict[str, dict]:
    """Return a dict mapping case id → case definition."""
    return {c["id"]: c for c in load_cases()}


def scan_watchlist(text: str, watchlist: list[str] | None = None) -> list[str]:
    """Return watchlist terms found (case-insensitive) in the given text."""
    if watchlist is None:
        watchlist = load_watchlist()
    text_lower = text.lower()
    return [term for term in watchlist if term.lower() in text_lower]


_NEGATIVE_PRACTICE_TERMS: tuple[str, ...] = (
    "sell", "sold", "share", "collect", "retain", "waive", "vague",
    "unclear", "third party", "third-party", "advertising", "profil",
    "training", "ai train",
)

# Mapping from cases.json topic values to diversified-score dimension names
_TOPIC_DIMENSION: dict[str, str] = {
    "Privacy": "dataPractices",
    "DataOwnership": "dataPractices",
    "UserRights": "userRights",
}

# Default sub-score used when no relevant summary points are available
_DEFAULT_SUBSCORE: int = 70


def calculate_score_from_cases(case_ids: list[str]) -> int:
    """Compute an aggregate score (0–100) from a list of matched case ids.

    Scoring rules:
    - Start at 100.
    - For each matched case, apply its weight (Blocker = −50, Bad = −20,
      Neutral = −10, Good = +10).
    - Clamp the result to [0, 100].

    Args:
        case_ids: List of case id strings found for this entry (may contain
                  duplicates; each is only counted once).

    Returns:
        Integer score in the range [0, 100].
    """
    cases_index = _build_cases_index()
    score = 100
    seen: set[str] = set()
    for cid in case_ids:
        if cid in seen:
            continue
        seen.add(cid)
        case = cases_index.get(cid)
        if case:
            score += case.get("weight", 0)
    return max(0, min(100, score))


def calculate_trust_score(history_entry: dict) -> int:
    """Compute a trust score (0–100) for a single history entry.

    Scoring rules:
    - Start at 100.
    - Deduct 20 for a 'Caution' verdict, 10 for 'Neutral'.
    - Deduct 5 for each *unique* watchlist_hit present in the entry.
    - Apply case weights from summaryPoints case_ids (via calculate_score_from_cases).
      If no case_ids are present, fall back to: deduct 5 per negative point,
      add 2 per positive point (bonus capped at +10).
    - Deduct 5 for each diffSummary field (DataOwnership, Privacy) that
      contains language indicating negative data practices.
    - Clamp the result to a minimum of 0.
    """
    score = 100

    # Verdict-based deduction
    verdict = history_entry.get("verdict", "Good")
    if verdict == "Caution":
        score -= 20
    elif verdict == "Neutral":
        score -= 10

    # Watchlist hit deduction
    watchlist_hits = history_entry.get("watchlist_hits") or []
    unique_hits = set(watchlist_hits)
    score -= 5 * len(unique_hits)

    # AI summary points: use case weights when available, fall back to impact counts
    summary_points = history_entry.get("summaryPoints") or []
    if summary_points:
        case_ids = [
            p.get("case_id", "")
            for p in summary_points
            if isinstance(p, dict) and p.get("case_id") and p.get("case_id") != "other"
        ]
        if case_ids:
            # Replace the flat 100-base with a weighted case score delta
            case_score = calculate_score_from_cases(case_ids)
            # Apply the case score as a signed delta relative to 100
            score += (case_score - 100)
        else:
            # Legacy fallback: count positive/negative impacts
            negative_count = sum(
                1 for p in summary_points
                if isinstance(p, dict) and p.get("impact") == "negative"
            )
            positive_count = sum(
                1 for p in summary_points
                if isinstance(p, dict) and p.get("impact") == "positive"
            )
            score -= 5 * negative_count
            positive_bonus = min(2 * positive_count, 10)
            score += positive_bonus

    # Penalise negative data-ownership and privacy practices in the AI diff summary
    diff_summary = history_entry.get("diffSummary") or {}
    for key in ("DataOwnership", "Privacy"):
        val = diff_summary.get(key, "").lower()
        if any(term in val for term in _NEGATIVE_PRACTICE_TERMS):
            score -= 5

    return max(score, 0)


def get_letter_grade(score: int) -> str:
    """Map a numeric trust score (0–100) to a letter grade (A–E).

    Grade mapping (mirrors ServiceClassBadge.tsx):
      A (Very Good):  score ≥ 90
      B (Good):       score ≥ 70
      C (Fair):       score ≥ 50
      D (Bad):        score ≥ 30
      E (Very Bad):   score < 30
    """
    if score >= 90:
        return "A"
    if score >= 70:
        return "B"
    if score >= 50:
        return "C"
    if score >= 30:
        return "D"
    return "E"


def calculate_diversified_scores(company: dict) -> dict:
    """Compute multiple scoring dimensions for a company.

    Aggregates summaryPoints from all history entries (and the top-level
    ``summaryPoints`` field) to produce four sub-scores:

    - ``dataPractices`` (0–100): Quality of data handling, derived from
      cases with topic "Privacy" or "DataOwnership".
    - ``userRights`` (0–100): Strength of user rights protections, derived
      from cases with topic "UserRights".
    - ``readability`` (0–100): Clarity/user-friendliness ratio — computed
      from the balance of positive vs negative summary points.
    - ``overall`` (0–100): The company's existing top-level score.

    All sub-scores default to ``_DEFAULT_SUBSCORE`` (70) when no relevant
    summary points are available, providing a slightly cautious baseline
    rather than a misleading perfect score.

    Args:
        company: A company result dict (may include ``score``, ``history``,
                 and ``summaryPoints``).

    Returns:
        Dict with keys: ``overall``, ``dataPractices``, ``userRights``,
        ``readability``.
    """
    cases_index = _build_cases_index()

    data_case_ids: list[str] = []
    user_rights_case_ids: list[str] = []
    total_positive = 0
    total_negative = 0
    all_case_ids_seen: set[str] = set()

    # Collect all summary points from every history entry plus top-level
    all_points: list[dict] = []
    for entry in company.get("history", []):
        all_points.extend(entry.get("summaryPoints") or [])
    all_points.extend(company.get("summaryPoints") or [])

    for point in all_points:
        if not isinstance(point, dict):
            continue
        impact = point.get("impact", "neutral")
        if impact == "positive":
            total_positive += 1
        elif impact == "negative":
            total_negative += 1

        case_id = point.get("case_id", "")
        if not case_id or case_id == "other" or case_id in all_case_ids_seen:
            continue
        all_case_ids_seen.add(case_id)

        case = cases_index.get(case_id)
        if not case:
            continue
        topic = case.get("topic", "")
        if topic in ("Privacy", "DataOwnership"):
            data_case_ids.append(case_id)
        elif topic == "UserRights":
            user_rights_case_ids.append(case_id)

    data_practices = (
        calculate_score_from_cases(data_case_ids)
        if data_case_ids
        else _DEFAULT_SUBSCORE
    )
    user_rights = (
        calculate_score_from_cases(user_rights_case_ids)
        if user_rights_case_ids
        else _DEFAULT_SUBSCORE
    )

    # Readability: proportion of positive vs negative points mapped to 0–100.
    # 50% positive  → 50, all positive → 100, all negative → 0.
    total_points = total_positive + total_negative
    if total_points > 0:
        readability = max(
            0,
            min(100, round(50 + (total_positive - total_negative) / total_points * 50)),
        )
    else:
        readability = _DEFAULT_SUBSCORE

    return {
        "overall": company.get("score", 100),
        "dataPractices": data_practices,
        "userRights": user_rights,
        "readability": readability,
    }


def add_benchmark_ranks(results: dict) -> None:
    """Add ``benchmarkRank`` and ``industryAvg`` to each company's ``scores`` dict.

    Computes the mean overall score across all companies and assigns a
    qualitative rank to each company based on how far its score deviates
    from the mean:

    - ``"Top Tier"``      – ≥ 15 points above average
    - ``"Above Average"`` – 5–14 points above average
    - ``"Average"``       – within 5 points of average
    - ``"Below Average"`` – 5–14 points below average
    - ``"Bottom Tier"``   – ≥ 15 points below average

    This function mutates the companies in ``results`` in-place; it never
    replaces an existing ``scores`` sub-dict but only appends new keys.

    Args:
        results: Top-level results dict as produced by ``monitor()`` or
                 ``re_rate_existing_results()``.
    """
    companies = results.get("companies", [])
    scores = [
        c.get("score", 100)
        for c in companies
        if isinstance(c.get("score"), (int, float))
    ]
    if not scores:
        return
    avg_score = round(sum(scores) / len(scores), 1)

    for company in companies:
        company_score = company.get("score", 100)
        diff = company_score - avg_score
        if diff >= 15:
            rank = "Top Tier"
        elif diff >= 5:
            rank = "Above Average"
        elif diff >= -5:
            rank = "Average"
        elif diff >= -15:
            rank = "Below Average"
        else:
            rank = "Bottom Tier"

        existing_scores = company.get("scores")
        if not isinstance(existing_scores, dict):
            existing_scores = {"overall": company_score}
        existing_scores["benchmarkRank"] = rank
        existing_scores["industryAvg"] = avg_score
        company["scores"] = existing_scores


def calculate_score(entry: dict) -> int:
    """Compute the Diffy score (0–100) for a history entry or company summary.

    This is the public-facing scoring function used by the Scoring Engine.
    It applies a weighted deduction system:

    Verdict penalty:
      - 'Caution'  → −20 points  (high-risk change detected)
      - 'Neutral'  → −10 points  (informational / ambiguous change)
      - 'Good'     →   0 points  (no deduction)

    Watchlist penalty:
      - −5 points per *unique* high-risk term found in the change
        (e.g. 'Arbitration', 'Tracking', 'Sell', …)

    AI summary point adjustments (summaryPoints field):
      - −5 points per negative-impact point identified by AI analysis
      - +2 points per positive-impact point (bonus capped at +10)

    Negative data-practice penalty (diffSummary field):
      - −5 points if Privacy summary indicates negative data practices
      - −5 points if DataOwnership summary indicates negative data practices

    The score is clamped to [0, 100].

    Args:
        entry: A history entry dict (may contain 'verdict', 'watchlist_hits',
               'summaryPoints', and 'diffSummary').

    Returns:
        Integer score in the range [0, 100].
    """
    return calculate_trust_score(entry)


def compute_change_magnitude(old_text: str, new_text: str) -> float:
    """Return the percentage of difference between two texts (0.0–100.0).

    Uses difflib.SequenceMatcher: a similarity ratio of 0.85 means
    15.0% difference (changeMagnitude = 15.0).
    Rounded to one decimal place.
    """
    if not old_text and not new_text:
        return 0.0
    ratio = difflib.SequenceMatcher(None, old_text, new_text).ratio()
    return round((1.0 - ratio) * 100, 1)


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


def call_openai_points_summary(text: str) -> list[dict]:
    """Generate an array of summary points from ToS text or a diff.

    Each point has:
      - "text":    plain string (max 20 words) describing the point
      - "impact":  one of "positive", "negative", or "neutral"
      - "case_id": kebab-case identifier matching a case in cases.json (or "other")
      - "quote":   verbatim excerpt from the ToS text supporting this point

    Returns an empty list if the API is unavailable or parsing fails.
    """
    if not OPENAI_API_KEY:
        return []
    truncated = text[:8000]
    try:
        raw = _openai_post([
            {"role": "system", "content": AI_POINTS_PROMPT},
            {"role": "user", "content": f"Here is the Terms of Service text:\n\n{truncated}"},
        ], max_tokens=768)  # Increased from 512: each point now includes case_id + quote fields
    except Exception as exc:
        print(f"  [OpenAI points summary error] {exc}")
        return []

    # Strip markdown fences if the model wrapped the output
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned.strip())

    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, list):
            valid_impacts = {"positive", "negative", "neutral"}
            return [
                {
                    "text": str(p.get("text", "")).strip(),
                    "impact": str(p.get("impact", "neutral")).lower()
                    if str(p.get("impact", "neutral")).lower() in valid_impacts
                    else "neutral",
                    "case_id": str(p.get("case_id", "other")).strip() or "other",
                    "quote": str(p.get("quote", "")).strip(),
                }
                for p in parsed
                if isinstance(p, dict) and p.get("text")
            ]
    except json.JSONDecodeError:
        pass
    return []


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
# Current ToS insights helpers
# ---------------------------------------------------------------------------

_CURRENT_FIELD_KEYS = (
    "currentOverview",
    "currentSummaryPoints",
    "currentWatchlistHits",
    "currentCaseIds",
    "currentWordCount",
)


def compute_current_fields(tos_text: str, watchlist: list[str]) -> dict:
    """Compute current-state insight fields from the latest fetched ToS text.

    These fields are always written for every company on every scraper run so
    that consumers can display up-to-date insights even when the ToS hasn't
    changed substantively enough to append a new history entry.

    Args:
        tos_text: The full text of the currently-live Terms of Service.
        watchlist: List of high-risk terms loaded from watchlist.json.

    Returns:
        A dict with the following keys:
          - currentOverview        – plain-text AI summary (≤30 words)
          - currentSummaryPoints   – list of {text, impact, case_id?, quote?}
          - currentWatchlistHits   – list of matched high-risk terms
          - currentCaseIds         – deduplicated list of case ids from points
          - currentWordCount       – integer word count of the full ToS text
    """
    current_overview = call_openai_overview(tos_text)
    current_summary_points = call_openai_points_summary(tos_text)
    current_watchlist_hits = scan_watchlist(tos_text, watchlist)

    # Derive case IDs from summary points (preserve insertion order, skip "other")
    seen_ids: set[str] = set()
    current_case_ids: list[str] = []
    for point in current_summary_points:
        cid = point.get("case_id", "")
        if cid and cid != "other" and cid not in seen_ids:
            seen_ids.add(cid)
            current_case_ids.append(cid)

    current_word_count = len(tos_text.split())

    return {
        "currentOverview": current_overview,
        "currentSummaryPoints": current_summary_points,
        "currentWatchlistHits": current_watchlist_hits,
        "currentCaseIds": current_case_ids,
        "currentWordCount": current_word_count,
    }


def get_company_current_fields(existing_results: dict, company_name: str) -> dict:
    """Return the stored current* fields for a company from previously-saved results.

    Used to carry forward cached insight fields when the ToS text hasn't changed
    so that every company entry always contains the current* block without
    incurring redundant OpenAI API calls.

    Args:
        existing_results: The dict loaded from the on-disk results.json.
        company_name:     The company ``name`` to look up.

    Returns:
        A (possibly empty) dict containing whichever current* keys were stored.
    """
    for c in existing_results.get("companies", []):
        if c.get("name") == company_name:
            return {k: c[k] for k in _CURRENT_FIELD_KEYS if k in c}
    return {}


# ---------------------------------------------------------------------------
# Main monitoring loop
# ---------------------------------------------------------------------------

def monitor() -> dict:
    ensure_dirs()
    companies_config = load_config()
    now = datetime.now(timezone.utc).isoformat()
    existing_results = load_existing_results()
    company_results: list[dict] = []
    watchlist = load_watchlist()

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
            company_score = calculate_score(history[-1]) if history else 100
            # Preserve previously-computed current* fields so the schema block
            # is always present even when the network request fails.
            current_fields = get_company_current_fields(existing_results, name)
            company_entry: dict = {
                "name": name,
                "category": category,
                "tosUrl": tos_url,
                "lastChecked": last_checked,
                "latestSummary": latest_summary,
                "score": company_score,
                "scores": calculate_diversified_scores({"score": company_score, "history": history}),
                "history": history,
                **current_fields,
            }
            company_results.append(company_entry)
            continue

        current_hash = sha256_hash(new_text)
        old_text = read_snapshot(name)
        previous_hash = sha256_hash(old_text) if old_text is not None else None
        write_snapshot(name, new_text)

        archived = archive_tos_if_changed(name, new_text)

        if not archived:
            # Content unchanged – no new history entry needed.
            # Re-use cached current* fields; compute fresh if not yet stored.
            latest_summary = read_tos_summary(name) or "Initial snapshot created. Monitoring active."
            company_score = calculate_score(history[-1]) if history else 100
            current_fields = get_company_current_fields(existing_results, name)
            if not current_fields:
                current_fields = compute_current_fields(new_text, watchlist)
            company_entry = {
                "name": name,
                "category": category,
                "tosUrl": tos_url,
                "lastChecked": last_checked,
                "latestSummary": latest_summary,
                "score": company_score,
                "scores": calculate_diversified_scores({"score": company_score, "history": history}),
                "history": history,
                **current_fields,
            }
            company_results.append(company_entry)
            continue

        # Raw text changed – determine substantive change
        if old_text is not None:
            is_significant, change_reason = detect_substantive_change(old_text, new_text)
        else:
            is_significant = True
            change_reason = "first version archived"

        # Text changed (even non-substantively) – always refresh current* fields
        # so they stay in sync with the live ToS.
        current_fields = compute_current_fields(new_text, watchlist)

        if not is_significant:
            # Non-substantive change (whitespace / cosmetic) – archive written,
            # but we do NOT add a history entry or regenerate the diff summary.
            latest_summary = read_tos_summary(name) or "Initial snapshot created. Monitoring active."
            company_score = calculate_score(history[-1]) if history else 100
            company_entry = {
                "name": name,
                "category": category,
                "tosUrl": tos_url,
                "lastChecked": last_checked,
                "latestSummary": latest_summary,
                "score": company_score,
                "scores": calculate_diversified_scores({"score": company_score, "history": history}),
                "history": history,
                **current_fields,
            }
            company_results.append(company_entry)
            continue

        # Substantive change – generate structured diff summary
        if old_text is not None and old_text != new_text:
            diff_text = build_diff(old_text, new_text)
            diff_summary = call_openai_diff_summary(diff_text)
        else:
            diff_text = ""
            diff_summary = call_openai_first_summary(new_text)

        verdict = assign_verdict(change_reason, diff_summary)

        # Flatten diff_summary to a plain-text string for latestSummary
        latest_summary = " | ".join(
            f"[{k}]: {v}" for k, v in diff_summary.items()
            if v and v != "No significant change"
        ) or "No significant change detected."

        write_tos_summary(name, latest_summary)

        # Compute change magnitude (percentage difference between versions)
        change_magnitude = compute_change_magnitude(old_text or "", new_text)

        # Scan for high-risk watchlist terms in the diff (or full text for first version)
        scan_target = diff_text if diff_text else new_text
        watchlist_hits = scan_watchlist(scan_target, watchlist)

        trust_score = calculate_trust_score({
            "verdict": verdict,
            "watchlist_hits": watchlist_hits,
        })
        letter_grade = get_letter_grade(trust_score)

        # Generate point-based summary for the card UI (diff-focused)
        summary_points = call_openai_points_summary(scan_target)

        # Append new history entry (chronological; oldest first)
        new_entry: dict = {
            "previous_hash": previous_hash,
            "current_hash": current_hash,
            "timestamp": last_checked,
            "verdict": verdict,
            "diffSummary": diff_summary,
            "changeIsSubstantial": True,
            "changeReason": change_reason,
            "changeMagnitude": change_magnitude,
            "watchlist_hits": watchlist_hits,
            "trustScore": trust_score,
            "letterGrade": letter_grade,
            "summaryPoints": summary_points,
        }
        history.append(new_entry)

        company_score = calculate_score(history[-1]) if history else 100
        company_entry = {
            "name": name,
            "category": category,
            "tosUrl": tos_url,
            "lastChecked": last_checked,
            "latestSummary": latest_summary,
            "summaryPoints": summary_points,
            "score": company_score,
            "scores": calculate_diversified_scores({
                "score": company_score,
                "history": history,
                "summaryPoints": summary_points,
            }),
            "history": history,
            **current_fields,
        }
        company_results.append(company_entry)

    results = {
        "schemaVersion": SCHEMA_VERSION,
        "updatedAt": now,
        "companies": company_results,
    }
    add_benchmark_ranks(results)
    return results


def re_rate_existing_results() -> dict:
    """Reload results.json and recalculate all trust scores using the current logic.

    This function applies the latest ``calculate_trust_score`` logic to every
    history entry in the stored results, updates each company's top-level
    ``score`` field, and writes the results back to disk.  It is safe to call
    repeatedly (idempotent) and should be run whenever the scoring logic is
    updated so that previously-stored entries reflect the new rating system.

    Returns:
        The updated results dict (same structure as ``monitor()`` output).
        Returns an empty dict if no existing results are found.
    """
    existing = load_existing_results()
    if not existing:
        print("No existing results found to re-rate.")
        return {}

    updated_count = 0
    for company in existing.get("companies", []):
        history = company.get("history", [])
        for entry in history:
            entry["trustScore"] = calculate_trust_score(entry)
            entry["letterGrade"] = get_letter_grade(entry["trustScore"])
            updated_count += 1
        if history:
            company["score"] = calculate_score(history[-1])
        company["scores"] = calculate_diversified_scores(company)

    add_benchmark_ranks(existing)
    existing["updatedAt"] = datetime.now(timezone.utc).isoformat()
    write_results(existing)
    write_summary_index(existing)
    print(
        f"Re-rated {len(existing.get('companies', []))} companies "
        f"({updated_count} history entries updated)."
    )
    return existing


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

    Each company entry includes:
      - score         – Diffy score (0–100) derived from the latest history entry
      - latest_verdict – verdict string of the latest history entry
      - favicon_url   – relative URL to the cached favicon image
    """
    summary_companies = []
    for company in results.get("companies", []):
        history = company.get("history", [])
        latest_entry = history[-1] if history else None

        # Derive per-company aggregate fields
        score: int = company.get("score", calculate_score(latest_entry) if latest_entry else 100)
        latest_verdict: Optional[str] = (
            latest_entry.get("verdict") if isinstance(latest_entry, dict) else None
        )

        # Build favicon URL from the tosUrl domain (mirrors fetch_and_store_favicons)
        tos_url = company.get("tosUrl", "")
        favicon_url: Optional[str] = None
        if tos_url:
            try:
                from urllib.parse import urlparse
                hostname = urlparse(tos_url).hostname or ""
                domain = hostname.replace("www.", "", 1)
                if domain:
                    favicon_url = f"/favicons/{domain}.png"
            except Exception:
                pass

        summary_companies.append({
            "name": company.get("name"),
            "category": company.get("category"),
            "tosUrl": tos_url,
            "lastChecked": company.get("lastChecked"),
            "latestSummary": company.get("latestSummary"),
            "summaryPoints": company.get("summaryPoints"),
            "score": score,
            "scores": company.get("scores"),
            "latest_verdict": latest_verdict,
            "favicon_url": favicon_url,
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
    assert results.get("schemaVersion") in ("2.0", "2.1", "2.2"), \
        f"schemaVersion must be '2.0', '2.1', or '2.2', got: {results.get('schemaVersion')!r}"
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
    if "--re-rate" in sys.argv:
        re_rate_existing_results()
        sys.exit(0)
    final_results = monitor()
    write_results(final_results)
    write_summary_index(final_results)
    validate_results(final_results)
    fetch_and_store_favicons(load_config())
    print(f"Done. Checked {len(final_results['companies'])} companies.")
    sys.exit(0)
