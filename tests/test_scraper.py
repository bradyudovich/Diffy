"""Tests for the new features added in scraper/monitor.py:
- SHA-256 hashing
- Verdict assignment
- Structured diff summary parsing
- History tracking and schema v2 output
"""
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Stub heavy optional dependencies before importing scraper/monitor.py
# ---------------------------------------------------------------------------

def _stub_scraper_modules():
    stubs = {
        "bs4": types.ModuleType("bs4"),
        "playwright": types.ModuleType("playwright"),
        "playwright.sync_api": types.ModuleType("playwright.sync_api"),
        "playwright_stealth": types.ModuleType("playwright_stealth"),
        "requests": types.ModuleType("requests"),
    }
    stubs["bs4"].BeautifulSoup = MagicMock()
    stubs["playwright.sync_api"].sync_playwright = MagicMock()
    stubs["playwright_stealth"].Stealth = MagicMock()
    stubs["requests"].post = MagicMock()
    for name, mod in stubs.items():
        sys.modules.setdefault(name, mod)


_stub_scraper_modules()

# Import scraper/monitor.py as a separate module
_scraper_spec = importlib.util.spec_from_file_location(
    "scraper_monitor",
    Path(__file__).parent.parent / "scraper" / "monitor.py",
)
scraper_monitor = importlib.util.module_from_spec(_scraper_spec)  # type: ignore[arg-type]
_scraper_spec.loader.exec_module(scraper_monitor)  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_env(tmp_path, monkeypatch):
    """Redirect all scraper_monitor paths to a temporary directory."""
    monkeypatch.setattr(scraper_monitor, "BASE_DIR", tmp_path)
    monkeypatch.setattr(scraper_monitor, "SNAPSHOTS_DIR", tmp_path / "data" / "snapshots")
    monkeypatch.setattr(scraper_monitor, "DATA_RESULTS_PATH", tmp_path / "data" / "results.json")
    monkeypatch.setattr(scraper_monitor, "PUBLIC_RESULTS_PATH", tmp_path / "public" / "data" / "results.json")
    monkeypatch.setattr(scraper_monitor, "TOS_DIR", tmp_path / "terms_of_service")
    scraper_monitor.ensure_dirs()
    return tmp_path


# ---------------------------------------------------------------------------
# SHA-256 hashing
# ---------------------------------------------------------------------------

class TestSha256Hash:
    def test_non_empty_string_returns_64_char_hex(self):
        result = scraper_monitor.sha256_hash("hello world")
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_empty_string_returns_known_hash(self):
        # SHA-256 of empty string is well-known
        result = scraper_monitor.sha256_hash("")
        assert result == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    def test_different_inputs_produce_different_hashes(self):
        h1 = scraper_monitor.sha256_hash("Version 1 of ToS")
        h2 = scraper_monitor.sha256_hash("Version 2 of ToS")
        assert h1 != h2

    def test_identical_inputs_produce_identical_hashes(self):
        text = "This is a Terms of Service document."
        assert scraper_monitor.sha256_hash(text) == scraper_monitor.sha256_hash(text)

    def test_hash_is_deterministic_across_calls(self):
        text = "Deterministic hashing test"
        results = [scraper_monitor.sha256_hash(text) for _ in range(5)]
        assert len(set(results)) == 1


# ---------------------------------------------------------------------------
# Verdict assignment
# ---------------------------------------------------------------------------

class TestAssignVerdict:
    def test_empty_reason_returns_good(self):
        assert scraper_monitor.assign_verdict("", {}) == "Good"

    def test_privacy_reason_returns_caution(self):
        verdict = scraper_monitor.assign_verdict("change detected in hot section: privacy", {})
        assert verdict == "Caution"

    def test_arbitration_reason_returns_caution(self):
        verdict = scraper_monitor.assign_verdict("change detected in hot section: arbitration", {})
        assert verdict == "Caution"

    def test_user_data_reason_returns_caution(self):
        verdict = scraper_monitor.assign_verdict("change detected in hot section: user_data", {})
        assert verdict == "Caution"

    def test_ai_reason_returns_caution(self):
        verdict = scraper_monitor.assign_verdict("change detected in hot section: ai", {})
        assert verdict == "Caution"

    def test_termination_reason_returns_caution(self):
        verdict = scraper_monitor.assign_verdict("change detected in hot section: termination", {})
        assert verdict == "Caution"

    def test_percent_change_reason_returns_neutral(self):
        verdict = scraper_monitor.assign_verdict("document changed by 10.0%", {})
        assert verdict == "Neutral"

    def test_semantic_reason_returns_neutral(self):
        verdict = scraper_monitor.assign_verdict("semantic meaning changed", {})
        assert verdict == "Neutral"

    def test_first_version_reason_returns_neutral(self):
        verdict = scraper_monitor.assign_verdict("first version archived", {})
        assert verdict == "Neutral"

    def test_caution_content_in_diff_summary_overrides_neutral_reason(self):
        diff_summary = {
            "Privacy": "Data will be sold to third parties",
            "DataOwnership": "No significant change",
            "UserRights": "No significant change",
        }
        verdict = scraper_monitor.assign_verdict("document changed by 5.0%", diff_summary)
        assert verdict == "Caution"

    def test_restrict_keyword_in_user_rights_returns_caution(self):
        diff_summary = {
            "Privacy": "No significant change",
            "DataOwnership": "No significant change",
            "UserRights": "Users are restricted from class action lawsuits.",
        }
        verdict = scraper_monitor.assign_verdict("document changed by 5.0%", diff_summary)
        assert verdict == "Caution"

    def test_clean_diff_summary_with_size_change_returns_neutral(self):
        diff_summary = {
            "Privacy": "No significant change",
            "DataOwnership": "No significant change",
            "UserRights": "No significant change",
        }
        verdict = scraper_monitor.assign_verdict("document changed by 5.0%", diff_summary)
        assert verdict == "Neutral"


# ---------------------------------------------------------------------------
# OpenAI diff summary JSON parsing
# ---------------------------------------------------------------------------

class TestCallOpenAIDiffSummary:
    def test_returns_default_values_when_no_api_key(self, monkeypatch):
        monkeypatch.setattr(scraper_monitor, "OPENAI_API_KEY", "")
        result = scraper_monitor.call_openai_diff_summary("some diff")
        assert result["Privacy"] == "No significant changes detected"
        assert result["DataOwnership"] == "No significant changes detected"
        assert result["UserRights"] == "No significant changes detected"

    def test_parses_valid_json_response(self, monkeypatch):
        monkeypatch.setattr(scraper_monitor, "OPENAI_API_KEY", "test-key")
        valid_json = '{"Privacy": "Users data shared", "DataOwnership": "Retained", "UserRights": "Waived"}'
        monkeypatch.setattr(scraper_monitor, "_openai_post", lambda msgs, **kw: valid_json)
        result = scraper_monitor.call_openai_diff_summary("diff text")
        assert result["Privacy"] == "Users data shared"
        assert result["DataOwnership"] == "Retained"
        assert result["UserRights"] == "Waived"

    def test_strips_markdown_fences_from_response(self, monkeypatch):
        monkeypatch.setattr(scraper_monitor, "OPENAI_API_KEY", "test-key")
        fenced = '```json\n{"Privacy": "Changed", "DataOwnership": "Same", "UserRights": "Same"}\n```'
        monkeypatch.setattr(scraper_monitor, "_openai_post", lambda msgs, **kw: fenced)
        result = scraper_monitor.call_openai_diff_summary("diff text")
        assert result["Privacy"] == "Changed"

    def test_falls_back_on_invalid_json(self, monkeypatch):
        monkeypatch.setattr(scraper_monitor, "OPENAI_API_KEY", "test-key")
        monkeypatch.setattr(scraper_monitor, "_openai_post", lambda msgs, **kw: "Not valid JSON response")
        result = scraper_monitor.call_openai_diff_summary("diff text")
        # Should not raise; should fall back to raw text
        assert isinstance(result, dict)
        assert "Privacy" in result

    def test_handles_openai_exception(self, monkeypatch):
        monkeypatch.setattr(scraper_monitor, "OPENAI_API_KEY", "test-key")
        def raise_error(msgs, **kw):
            raise Exception("Network error")
        monkeypatch.setattr(scraper_monitor, "_openai_post", raise_error)
        result = scraper_monitor.call_openai_diff_summary("diff text")
        assert isinstance(result, dict)
        assert "AI analysis failed" in result.get("Privacy", "")


# ---------------------------------------------------------------------------
# History management
# ---------------------------------------------------------------------------

class TestGetCompanyHistory:
    def test_returns_empty_list_for_missing_company(self):
        existing = {"companies": [{"name": "OtherCo", "history": [{"timestamp": "t1"}]}]}
        result = scraper_monitor.get_company_history(existing, "NotFound")
        assert result == []

    def test_returns_history_for_existing_company(self):
        history = [{"timestamp": "2026-01-01", "verdict": "Good"}]
        existing = {"companies": [{"name": "Acme", "history": history}]}
        result = scraper_monitor.get_company_history(existing, "Acme")
        assert result == history

    def test_returns_copy_not_reference(self):
        history = [{"timestamp": "2026-01-01"}]
        existing = {"companies": [{"name": "Acme", "history": history}]}
        result = scraper_monitor.get_company_history(existing, "Acme")
        result.append({"timestamp": "extra"})
        # Original should be unchanged
        assert len(existing["companies"][0]["history"]) == 1

    def test_company_without_history_key_returns_empty(self):
        existing = {"companies": [{"name": "Acme"}]}
        result = scraper_monitor.get_company_history(existing, "Acme")
        assert result == []

    def test_empty_results_returns_empty(self):
        result = scraper_monitor.get_company_history({}, "Acme")
        assert result == []


# ---------------------------------------------------------------------------
# Schema v2 validation
# ---------------------------------------------------------------------------

class TestValidateResults:
    def _make_valid_results(self):
        return {
            "schemaVersion": "2.1",
            "updatedAt": "2026-03-08T00:00:00Z",
            "companies": [
                {
                    "name": "TestCo",
                    "category": "Tech",
                    "tosUrl": "https://test.com/tos",
                    "lastChecked": "2026-03-08T00:00:00Z",
                    "latestSummary": "Some summary",
                    "history": [
                        {
                            "previous_hash": None,
                            "current_hash": "abc123",
                            "timestamp": "2026-03-08T00:00:00Z",
                            "verdict": "Neutral",
                            "diffSummary": {
                                "Privacy": "No change",
                                "DataOwnership": "No change",
                                "UserRights": "No change",
                            },
                            "changeIsSubstantial": True,
                            "changeReason": "first version archived",
                        }
                    ],
                }
            ],
        }

    def test_valid_results_passes(self):
        scraper_monitor.validate_results(self._make_valid_results())

    def test_valid_results_passes_schema_v2(self):
        """Schema version 2.0 (legacy) should also be accepted."""
        results = self._make_valid_results()
        results["schemaVersion"] = "2.0"
        scraper_monitor.validate_results(results)

    def test_missing_companies_key_raises(self):
        with pytest.raises(AssertionError):
            scraper_monitor.validate_results({"schemaVersion": "2.1", "updatedAt": "t"})

    def test_wrong_schema_version_raises(self):
        results = self._make_valid_results()
        results["schemaVersion"] = "1.0"
        with pytest.raises(AssertionError):
            scraper_monitor.validate_results(results)

    def test_company_missing_history_raises(self):
        results = self._make_valid_results()
        del results["companies"][0]["history"]
        with pytest.raises(AssertionError):
            scraper_monitor.validate_results(results)

    def test_company_missing_latest_summary_raises(self):
        results = self._make_valid_results()
        del results["companies"][0]["latestSummary"]
        with pytest.raises(AssertionError):
            scraper_monitor.validate_results(results)

    def test_invalid_verdict_raises(self):
        results = self._make_valid_results()
        results["companies"][0]["history"][0]["verdict"] = "Unknown"
        with pytest.raises(AssertionError):
            scraper_monitor.validate_results(results)

    def test_caution_verdict_passes(self):
        results = self._make_valid_results()
        results["companies"][0]["history"][0]["verdict"] = "Caution"
        scraper_monitor.validate_results(results)

    def test_good_verdict_passes(self):
        results = self._make_valid_results()
        results["companies"][0]["history"][0]["verdict"] = "Good"
        scraper_monitor.validate_results(results)


# ---------------------------------------------------------------------------
# Monitor integration: history accumulation
# ---------------------------------------------------------------------------

class TestMonitorHistoryAccumulation:
    """Verify that monitor() appends new history entries and preserves old ones."""

    def _make_company_config(self):
        return [{"name": "TestCo", "category": "Tech", "tosUrl": "https://test.com/tos"}]

    def test_first_run_creates_history_entry(self, tmp_env, monkeypatch):
        monkeypatch.setattr(scraper_monitor, "load_config", self._make_company_config)
        monkeypatch.setattr(scraper_monitor, "fetch_text", lambda url, **kw: "ToS version 1")
        monkeypatch.setattr(scraper_monitor, "call_openai_diff_summary",
                            lambda diff: {"Privacy": "ok", "DataOwnership": "ok", "UserRights": "ok"})
        monkeypatch.setattr(scraper_monitor, "call_openai_first_summary",
                            lambda text: {"Privacy": "v1", "DataOwnership": "ok", "UserRights": "ok"})

        results = scraper_monitor.monitor()
        company = next(c for c in results["companies"] if c["name"] == "TestCo")
        assert len(company["history"]) == 1
        assert company["history"][0]["changeReason"] == "first version archived"
        assert company["history"][0]["current_hash"] == scraper_monitor.sha256_hash("ToS version 1")

    def test_second_run_unchanged_does_not_add_history(self, tmp_env, monkeypatch):
        monkeypatch.setattr(scraper_monitor, "load_config", self._make_company_config)
        monkeypatch.setattr(scraper_monitor, "fetch_text", lambda url, **kw: "ToS version 1")
        monkeypatch.setattr(scraper_monitor, "call_openai_first_summary",
                            lambda text: {"Privacy": "v1", "DataOwnership": "ok", "UserRights": "ok"})

        # First run
        r1 = scraper_monitor.monitor()
        scraper_monitor.write_results(r1)
        # Second run – same text
        r2 = scraper_monitor.monitor()
        company = next(c for c in r2["companies"] if c["name"] == "TestCo")
        # History should still be 1 entry (no new entry for unchanged text)
        assert len(company["history"]) == 1

    def test_second_run_with_change_appends_history(self, tmp_env, monkeypatch):
        calls = {"count": 0}

        def fetch_changing(url, **kw):
            calls["count"] += 1
            if calls["count"] == 1:
                return "ToS version 1 with privacy policy details about data collection."
            return "ToS version 2 with arbitration clause and waived class action rights."

        monkeypatch.setattr(scraper_monitor, "load_config", self._make_company_config)
        monkeypatch.setattr(scraper_monitor, "fetch_text", fetch_changing)
        monkeypatch.setattr(scraper_monitor, "call_openai_diff_summary",
                            lambda diff: {"Privacy": "changed", "DataOwnership": "ok", "UserRights": "ok"})
        monkeypatch.setattr(scraper_monitor, "call_openai_first_summary",
                            lambda text: {"Privacy": "v1", "DataOwnership": "ok", "UserRights": "ok"})

        # First run
        r1 = scraper_monitor.monitor()
        scraper_monitor.write_results(r1)
        # Second run with different text
        r2 = scraper_monitor.monitor()
        company = next(c for c in r2["companies"] if c["name"] == "TestCo")
        assert len(company["history"]) == 2
        # Second entry should have previous_hash set
        assert company["history"][1]["previous_hash"] is not None
        assert company["history"][1]["previous_hash"] == company["history"][0]["current_hash"]

    def test_results_have_schema_version_2(self, tmp_env, monkeypatch):
        monkeypatch.setattr(scraper_monitor, "load_config", self._make_company_config)
        monkeypatch.setattr(scraper_monitor, "fetch_text", lambda url, **kw: "ToS content")
        monkeypatch.setattr(scraper_monitor, "call_openai_first_summary",
                            lambda text: {"Privacy": "ok", "DataOwnership": "ok", "UserRights": "ok"})

        results = scraper_monitor.monitor()
        assert results.get("schemaVersion") == "2.2"

    def test_results_have_latest_summary(self, tmp_env, monkeypatch):
        monkeypatch.setattr(scraper_monitor, "load_config", self._make_company_config)
        monkeypatch.setattr(scraper_monitor, "fetch_text", lambda url, **kw: "ToS content")
        monkeypatch.setattr(scraper_monitor, "call_openai_first_summary",
                            lambda text: {"Privacy": "Privacy detail", "DataOwnership": "ok", "UserRights": "ok"})

        results = scraper_monitor.monitor()
        company = next(c for c in results["companies"] if c["name"] == "TestCo")
        assert "latestSummary" in company
        assert company["latestSummary"]  # non-empty


# ---------------------------------------------------------------------------
# Premium features: watchlist scanning and change magnitude
# ---------------------------------------------------------------------------

class TestScanWatchlist:
    def test_returns_matched_terms(self):
        hits = scraper_monitor.scan_watchlist(
            "This policy includes mandatory arbitration and class action waiver.",
            ["Arbitration", "Class Action", "Biometric"],
        )
        assert "Arbitration" in hits
        assert "Class Action" in hits
        assert "Biometric" not in hits

    def test_case_insensitive_match(self):
        hits = scraper_monitor.scan_watchlist(
            "Users must agree to ARBITRATION of all disputes.",
            ["Arbitration"],
        )
        assert "Arbitration" in hits

    def test_no_matches_returns_empty_list(self):
        hits = scraper_monitor.scan_watchlist(
            "All disputes resolved amicably.",
            ["Arbitration", "Class Action"],
        )
        assert hits == []

    def test_empty_text_returns_empty_list(self):
        assert scraper_monitor.scan_watchlist("", ["Arbitration"]) == []

    def test_default_watchlist_loads_from_file(self, tmp_path, monkeypatch):
        import json
        wl_path = tmp_path / "watchlist.json"
        wl_path.write_text(json.dumps({"terms": ["Arbitration", "Biometric"]}))
        monkeypatch.setattr(scraper_monitor, "WATCHLIST_PATH", wl_path)
        hits = scraper_monitor.scan_watchlist("biometric data processing")
        assert "Biometric" in hits


class TestComputeChangeMagnitude:
    def test_identical_texts_return_zero(self):
        result = scraper_monitor.compute_change_magnitude("hello world", "hello world")
        assert result == 0.0

    def test_completely_different_texts_return_high_value(self):
        result = scraper_monitor.compute_change_magnitude("aaa", "zzz")
        assert result > 0.0

    def test_empty_both_return_zero(self):
        assert scraper_monitor.compute_change_magnitude("", "") == 0.0

    def test_result_rounded_to_one_decimal(self):
        result = scraper_monitor.compute_change_magnitude(
            "The quick brown fox", "The quick brown dog"
        )
        assert isinstance(result, float)
        assert result == round(result, 1)

    def test_partial_change_between_0_and_100(self):
        old = "Terms of service: we collect your data."
        new = "Terms of service: we collect and sell your data to third parties."
        result = scraper_monitor.compute_change_magnitude(old, new)
        assert 0.0 < result <= 100.0


class TestLoadWatchlist:
    def test_loads_terms_from_file(self, tmp_path, monkeypatch):
        import json
        wl_path = tmp_path / "watchlist.json"
        wl_path.write_text(json.dumps({"terms": ["Arbitration", "Sub-processor"]}))
        monkeypatch.setattr(scraper_monitor, "WATCHLIST_PATH", wl_path)
        terms = scraper_monitor.load_watchlist()
        assert "Arbitration" in terms
        assert "Sub-processor" in terms

    def test_missing_file_returns_empty_list(self, tmp_path, monkeypatch):
        monkeypatch.setattr(scraper_monitor, "WATCHLIST_PATH", tmp_path / "missing.json")
        assert scraper_monitor.load_watchlist() == []


class TestMonitorPremiumFields:
    """Verify that monitor() includes changeMagnitude and watchlist_hits in history entries."""

    def _make_company_config(self):
        return [{"name": "TestCo", "category": "Tech", "tosUrl": "https://test.com/tos"}]

    def test_history_entry_has_change_magnitude(self, tmp_env, monkeypatch):
        monkeypatch.setattr(scraper_monitor, "load_config", self._make_company_config)
        monkeypatch.setattr(scraper_monitor, "fetch_text", lambda url, **kw: "ToS content v1")
        monkeypatch.setattr(scraper_monitor, "call_openai_first_summary",
                            lambda text: {"Privacy": "ok", "DataOwnership": "ok", "UserRights": "ok"})

        results = scraper_monitor.monitor()
        company = next(c for c in results["companies"] if c["name"] == "TestCo")
        assert len(company["history"]) == 1
        assert "changeMagnitude" in company["history"][0]
        assert isinstance(company["history"][0]["changeMagnitude"], float)

    def test_history_entry_has_watchlist_hits(self, tmp_env, monkeypatch):
        monkeypatch.setattr(scraper_monitor, "load_config", self._make_company_config)
        monkeypatch.setattr(scraper_monitor, "fetch_text",
                            lambda url, **kw: "Mandatory arbitration clause applies.")
        monkeypatch.setattr(scraper_monitor, "call_openai_first_summary",
                            lambda text: {"Privacy": "ok", "DataOwnership": "ok", "UserRights": "ok"})
        monkeypatch.setattr(scraper_monitor, "load_watchlist",
                            lambda: ["Arbitration", "Class Action"])

        results = scraper_monitor.monitor()
        company = next(c for c in results["companies"] if c["name"] == "TestCo")
        assert "watchlist_hits" in company["history"][0]
        assert isinstance(company["history"][0]["watchlist_hits"], list)
        assert "Arbitration" in company["history"][0]["watchlist_hits"]

    def test_change_magnitude_on_second_run(self, tmp_env, monkeypatch):
        calls = {"count": 0}

        def fetch_changing(url, **kw):
            calls["count"] += 1
            if calls["count"] == 1:
                return "ToS version one with lots of privacy terms."
            return "ToS version two significantly different arbitration clause."

        monkeypatch.setattr(scraper_monitor, "load_config", self._make_company_config)
        monkeypatch.setattr(scraper_monitor, "fetch_text", fetch_changing)
        monkeypatch.setattr(scraper_monitor, "call_openai_diff_summary",
                            lambda diff: {"Privacy": "changed", "DataOwnership": "ok", "UserRights": "ok"})
        monkeypatch.setattr(scraper_monitor, "call_openai_first_summary",
                            lambda text: {"Privacy": "v1", "DataOwnership": "ok", "UserRights": "ok"})

        r1 = scraper_monitor.monitor()
        scraper_monitor.write_results(r1)
        r2 = scraper_monitor.monitor()
        company = next(c for c in r2["companies"] if c["name"] == "TestCo")
        assert len(company["history"]) == 2
        second_entry = company["history"][1]
        assert "changeMagnitude" in second_entry
        assert 0.0 <= second_entry["changeMagnitude"] <= 100.0


# ---------------------------------------------------------------------------
# calculate_score (Scoring Engine)
# ---------------------------------------------------------------------------

class TestCalculateScore:
    """Verify the public calculate_score() function used by the Scoring Engine."""

    def test_good_verdict_no_hits_returns_100(self):
        entry = {"verdict": "Good", "watchlist_hits": []}
        assert scraper_monitor.calculate_score(entry) == 100

    def test_caution_verdict_deducts_20(self):
        entry = {"verdict": "Caution", "watchlist_hits": []}
        assert scraper_monitor.calculate_score(entry) == 80

    def test_neutral_verdict_deducts_10(self):
        entry = {"verdict": "Neutral", "watchlist_hits": []}
        assert scraper_monitor.calculate_score(entry) == 90

    def test_deducts_5_per_unique_watchlist_hit(self):
        entry = {"verdict": "Good", "watchlist_hits": ["Arbitration", "Tracking", "Sell"]}
        assert scraper_monitor.calculate_score(entry) == 85  # 100 - 3*5

    def test_duplicate_watchlist_hits_counted_once(self):
        entry = {"verdict": "Good", "watchlist_hits": ["Arbitration", "Arbitration"]}
        assert scraper_monitor.calculate_score(entry) == 95  # 100 - 1*5

    def test_combined_caution_and_hits(self):
        entry = {"verdict": "Caution", "watchlist_hits": ["Arbitration", "Sell", "Tracking", "Profiling"]}
        # 100 - 20 - 4*5 = 60
        assert scraper_monitor.calculate_score(entry) == 60

    def test_score_clamped_to_zero(self):
        entry = {
            "verdict": "Caution",
            "watchlist_hits": ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J",
                               "K", "L", "M", "N", "O", "P"],
        }
        assert scraper_monitor.calculate_score(entry) == 0

    def test_matches_calculate_trust_score(self):
        entry = {"verdict": "Caution", "watchlist_hits": ["Arbitration", "Tracking"]}
        assert scraper_monitor.calculate_score(entry) == scraper_monitor.calculate_trust_score(entry)

    def test_missing_watchlist_hits_defaults_to_none(self):
        entry = {"verdict": "Neutral"}
        assert scraper_monitor.calculate_score(entry) == 90


# ---------------------------------------------------------------------------
# write_summary_index includes score, latest_verdict, favicon_url
# ---------------------------------------------------------------------------

class TestWriteSummaryIndex:
    """Verify that write_summary_index() writes score, latest_verdict, favicon_url."""

    def _make_results(self, tos_url="https://openai.com/tos", verdict="Caution", score=60):
        return {
            "schemaVersion": "2.1",
            "updatedAt": "2026-03-01T00:00:00Z",
            "companies": [
                {
                    "name": "TestCo",
                    "category": "AI",
                    "tosUrl": tos_url,
                    "lastChecked": "2026-03-01T00:00:00Z",
                    "latestSummary": "Some summary",
                    "score": score,
                    "history": [
                        {
                            "previous_hash": None,
                            "current_hash": "abc123",
                            "timestamp": "2026-03-01T00:00:00Z",
                            "verdict": verdict,
                            "diffSummary": {"Privacy": "ok", "DataOwnership": "ok", "UserRights": "ok"},
                            "changeIsSubstantial": True,
                            "changeReason": "first version archived",
                        }
                    ],
                }
            ],
        }

    def test_score_field_included(self, tmp_env, monkeypatch):
        import json
        monkeypatch.setattr(scraper_monitor, "SUMMARY_INDEX_PATH",
                            tmp_env / "summary_index.json")
        monkeypatch.setattr(scraper_monitor, "PUBLIC_SUMMARY_INDEX_PATH",
                            tmp_env / "public_summary_index.json")
        results = self._make_results(score=65)
        scraper_monitor.write_summary_index(results)
        data = json.loads((tmp_env / "summary_index.json").read_text())
        company = data["companies"][0]
        assert "score" in company
        assert company["score"] == 65

    def test_latest_verdict_field_included(self, tmp_env, monkeypatch):
        import json
        monkeypatch.setattr(scraper_monitor, "SUMMARY_INDEX_PATH",
                            tmp_env / "summary_index.json")
        monkeypatch.setattr(scraper_monitor, "PUBLIC_SUMMARY_INDEX_PATH",
                            tmp_env / "public_summary_index.json")
        results = self._make_results(verdict="Caution")
        scraper_monitor.write_summary_index(results)
        data = json.loads((tmp_env / "summary_index.json").read_text())
        company = data["companies"][0]
        assert company.get("latest_verdict") == "Caution"

    def test_favicon_url_field_included(self, tmp_env, monkeypatch):
        import json
        monkeypatch.setattr(scraper_monitor, "SUMMARY_INDEX_PATH",
                            tmp_env / "summary_index.json")
        monkeypatch.setattr(scraper_monitor, "PUBLIC_SUMMARY_INDEX_PATH",
                            tmp_env / "public_summary_index.json")
        results = self._make_results(tos_url="https://openai.com/tos")
        scraper_monitor.write_summary_index(results)
        data = json.loads((tmp_env / "summary_index.json").read_text())
        company = data["companies"][0]
        assert company.get("favicon_url") == "/favicons/openai.com.png"

    def test_no_history_gives_default_score_100(self, tmp_env, monkeypatch):
        import json
        monkeypatch.setattr(scraper_monitor, "SUMMARY_INDEX_PATH",
                            tmp_env / "summary_index.json")
        monkeypatch.setattr(scraper_monitor, "PUBLIC_SUMMARY_INDEX_PATH",
                            tmp_env / "public_summary_index.json")
        results = {
            "schemaVersion": "2.1",
            "updatedAt": "2026-03-01T00:00:00Z",
            "companies": [
                {
                    "name": "NewCo",
                    "category": "Tech",
                    "tosUrl": "https://newco.com/tos",
                    "lastChecked": "2026-03-01T00:00:00Z",
                    "latestSummary": "",
                    "history": [],
                }
            ],
        }
        scraper_monitor.write_summary_index(results)
        data = json.loads((tmp_env / "summary_index.json").read_text())
        company = data["companies"][0]
        assert company["score"] == 100
        assert company["latest_verdict"] is None


# ---------------------------------------------------------------------------
# calculate_trust_score – enhanced scoring with summaryPoints and diffSummary
# ---------------------------------------------------------------------------

class TestCalculateTrustScoreEnhanced:
    """Verify the enhanced calculate_trust_score() logic that considers
    AI summary points and diffSummary content."""

    def test_negative_summary_points_deduct_from_score(self):
        entry = {
            "verdict": "Good",
            "watchlist_hits": [],
            "summaryPoints": [
                {"text": "Data sold to third parties", "impact": "negative"},
                {"text": "Mandatory arbitration applies", "impact": "negative"},
            ],
        }
        # 100 - 0 (Good) - 0 (no hits) - 2*5 (2 negative points) = 90
        assert scraper_monitor.calculate_trust_score(entry) == 90

    def test_positive_summary_points_add_to_score(self):
        entry = {
            "verdict": "Neutral",
            "watchlist_hits": [],
            "summaryPoints": [
                {"text": "Users retain full content ownership", "impact": "positive"},
                {"text": "Data is never sold", "impact": "positive"},
            ],
        }
        # 100 - 10 (Neutral) + 2*2 (2 positive points) = 94
        assert scraper_monitor.calculate_trust_score(entry) == 94

    def test_positive_bonus_capped_at_10(self):
        entry = {
            "verdict": "Good",
            "watchlist_hits": [],
            "summaryPoints": [
                {"text": "p1", "impact": "positive"},
                {"text": "p2", "impact": "positive"},
                {"text": "p3", "impact": "positive"},
                {"text": "p4", "impact": "positive"},
                {"text": "p5", "impact": "positive"},
                {"text": "p6", "impact": "positive"},
                {"text": "p7", "impact": "positive"},
                {"text": "p8", "impact": "positive"},
            ],
        }
        # 100 - 0 + min(8*2, 10) = 100 + 10 = 110 → clamped to... no, not clamped from above
        # But bonus is capped at 10, so 100 + 10 = 110.
        # There is no upper clamp, only lower clamp at 0.
        assert scraper_monitor.calculate_trust_score(entry) == 110

    def test_diff_summary_negative_data_ownership_deducts_score(self):
        entry = {
            "verdict": "Neutral",
            "watchlist_hits": [],
            "summaryPoints": [],
            "diffSummary": {
                "Privacy": "No significant changes detected",
                "DataOwnership": "Company may sell user data to third parties",
                "UserRights": "No significant changes detected",
            },
        }
        # 100 - 10 (Neutral) - 0 (no hits) - 0 (no summary points) - 5 (DataOwnership sell) = 85
        assert scraper_monitor.calculate_trust_score(entry) == 85

    def test_diff_summary_negative_privacy_deducts_score(self):
        entry = {
            "verdict": "Good",
            "watchlist_hits": [],
            "summaryPoints": [],
            "diffSummary": {
                "Privacy": "Data collected and shared with advertising partners",
                "DataOwnership": "No significant changes detected",
                "UserRights": "No significant changes detected",
            },
        }
        # 100 - 0 (Good) - 0 (no hits) - 0 (no points) - 5 (Privacy collect/advertising/share) = 95
        assert scraper_monitor.calculate_trust_score(entry) == 95

    def test_combined_all_deductions(self):
        entry = {
            "verdict": "Caution",
            "watchlist_hits": ["Arbitration", "Tracking"],
            "summaryPoints": [
                {"text": "Mandatory arbitration clause", "impact": "negative"},
                {"text": "User data sold to advertisers", "impact": "negative"},
                {"text": "Users retain ownership", "impact": "positive"},
            ],
            "diffSummary": {
                "Privacy": "Data collected and retained for advertising",
                "DataOwnership": "Company may share data with third parties",
                "UserRights": "No significant changes detected",
            },
        }
        # 100 - 20 (Caution) - 2*5 (2 watchlist hits) - 2*5 (2 neg points) + 2 (1 pos point)
        # - 5 (Privacy collect/retained/advertising) - 5 (DataOwnership share/third party)
        # = 100 - 20 - 10 - 10 + 2 - 5 - 5 = 52
        assert scraper_monitor.calculate_trust_score(entry) == 52

    def test_neutral_points_have_no_score_impact(self):
        entry = {
            "verdict": "Good",
            "watchlist_hits": [],
            "summaryPoints": [
                {"text": "Service governed by California law", "impact": "neutral"},
                {"text": "Updates notified by email", "impact": "neutral"},
            ],
        }
        # 100 - 0 - 0 - 0 (no neg/pos points) = 100
        assert scraper_monitor.calculate_trust_score(entry) == 100

    def test_empty_summary_points_list_no_change(self):
        entry = {
            "verdict": "Good",
            "watchlist_hits": [],
            "summaryPoints": [],
        }
        assert scraper_monitor.calculate_trust_score(entry) == 100

    def test_missing_summary_points_key_no_change(self):
        entry = {"verdict": "Good", "watchlist_hits": []}
        assert scraper_monitor.calculate_trust_score(entry) == 100

    def test_score_never_drops_below_zero(self):
        entry = {
            "verdict": "Caution",
            "watchlist_hits": ["A", "B", "C", "D", "E"],
            "summaryPoints": [
                {"text": f"negative point {i}", "impact": "negative"}
                for i in range(10)
            ],
            "diffSummary": {
                "Privacy": "Data sold and shared with advertising third-party",
                "DataOwnership": "Company retains and sells all user data",
                "UserRights": "No significant changes detected",
            },
        }
        assert scraper_monitor.calculate_trust_score(entry) >= 0


# ---------------------------------------------------------------------------
# re_rate_existing_results
# ---------------------------------------------------------------------------

class TestReRateExistingResults:
    """Verify re_rate_existing_results() recalculates scores across all companies."""

    def _make_results_json(self, tmp_env):
        import json
        results = {
            "schemaVersion": "2.1",
            "updatedAt": "2026-01-01T00:00:00Z",
            "companies": [
                {
                    "name": "AlphaCo",
                    "category": "Tech",
                    "tosUrl": "https://alphaco.com/tos",
                    "lastChecked": "2026-01-01T00:00:00Z",
                    "latestSummary": "Overview",
                    "score": 100,
                    "history": [
                        {
                            "previous_hash": None,
                            "current_hash": "hash1",
                            "timestamp": "2026-01-01T00:00:00Z",
                            "verdict": "Neutral",
                            "diffSummary": {
                                "Privacy": "Data collected and sold",
                                "DataOwnership": "No significant changes detected",
                                "UserRights": "No significant changes detected",
                            },
                            "changeIsSubstantial": True,
                            "changeReason": "first version archived",
                            "watchlist_hits": ["Arbitration"],
                            "summaryPoints": [
                                {"text": "Data sold to advertisers", "impact": "negative"},
                            ],
                        }
                    ],
                }
            ],
        }
        payload = json.dumps(results, indent=2)
        (tmp_env / "data").mkdir(parents=True, exist_ok=True)
        (tmp_env / "data" / "results.json").write_text(payload)
        return results

    def test_re_rate_updates_trust_score_in_history(self, tmp_env, monkeypatch):
        import json
        self._make_results_json(tmp_env)
        monkeypatch.setattr(scraper_monitor, "DATA_RESULTS_PATH",
                            tmp_env / "data" / "results.json")
        monkeypatch.setattr(scraper_monitor, "PUBLIC_RESULTS_PATH",
                            tmp_env / "public" / "data" / "results.json")
        monkeypatch.setattr(scraper_monitor, "SUMMARY_INDEX_PATH",
                            tmp_env / "summary_index.json")
        monkeypatch.setattr(scraper_monitor, "PUBLIC_SUMMARY_INDEX_PATH",
                            tmp_env / "public_summary_index.json")

        updated = scraper_monitor.re_rate_existing_results()
        entry = updated["companies"][0]["history"][0]
        assert "trustScore" in entry
        assert "letterGrade" in entry
        # Neutral(-10) + Arbitration hit(-5) + 1 neg summaryPoint(-5) + Privacy sell/collected(-5) = 75
        assert entry["trustScore"] == 75
        assert entry["letterGrade"] == "B"  # 75 >= 70 → grade B

    def test_re_rate_updates_company_score(self, tmp_env, monkeypatch):
        self._make_results_json(tmp_env)
        monkeypatch.setattr(scraper_monitor, "DATA_RESULTS_PATH",
                            tmp_env / "data" / "results.json")
        monkeypatch.setattr(scraper_monitor, "PUBLIC_RESULTS_PATH",
                            tmp_env / "public" / "data" / "results.json")
        monkeypatch.setattr(scraper_monitor, "SUMMARY_INDEX_PATH",
                            tmp_env / "summary_index.json")
        monkeypatch.setattr(scraper_monitor, "PUBLIC_SUMMARY_INDEX_PATH",
                            tmp_env / "public_summary_index.json")

        updated = scraper_monitor.re_rate_existing_results()
        company = updated["companies"][0]
        # company score reflects latest history entry's score
        assert company["score"] == 75

    def test_re_rate_returns_empty_when_no_results(self, tmp_env, monkeypatch):
        monkeypatch.setattr(scraper_monitor, "DATA_RESULTS_PATH",
                            tmp_env / "nonexistent.json")
        monkeypatch.setattr(scraper_monitor, "PUBLIC_RESULTS_PATH",
                            tmp_env / "nonexistent2.json")
        result = scraper_monitor.re_rate_existing_results()
        assert result == {}

    def test_re_rate_writes_results_to_disk(self, tmp_env, monkeypatch):
        import json
        self._make_results_json(tmp_env)
        monkeypatch.setattr(scraper_monitor, "DATA_RESULTS_PATH",
                            tmp_env / "data" / "results.json")
        monkeypatch.setattr(scraper_monitor, "PUBLIC_RESULTS_PATH",
                            tmp_env / "public" / "data" / "results.json")
        monkeypatch.setattr(scraper_monitor, "SUMMARY_INDEX_PATH",
                            tmp_env / "summary_index.json")
        monkeypatch.setattr(scraper_monitor, "PUBLIC_SUMMARY_INDEX_PATH",
                            tmp_env / "public_summary_index.json")

        scraper_monitor.re_rate_existing_results()

        saved = json.loads((tmp_env / "data" / "results.json").read_text())
        entry = saved["companies"][0]["history"][0]
        assert entry["trustScore"] == 75
        assert entry["letterGrade"] == "B"  # 75 >= 70 → grade B


# ---------------------------------------------------------------------------
# calculate_diversified_scores
# ---------------------------------------------------------------------------

class TestCalculateDiversifiedScores:
    """Verify calculate_diversified_scores() returns correct sub-scores."""

    def test_empty_company_returns_defaults(self):
        company = {"score": 100, "history": [], "summaryPoints": []}
        scores = scraper_monitor.calculate_diversified_scores(company)
        assert scores["overall"] == 100
        assert scores["dataPractices"] == scraper_monitor._DEFAULT_SUBSCORE
        assert scores["userRights"] == scraper_monitor._DEFAULT_SUBSCORE
        assert scores["readability"] == scraper_monitor._DEFAULT_SUBSCORE

    def test_overall_mirrors_company_score(self):
        company = {"score": 65, "history": []}
        scores = scraper_monitor.calculate_diversified_scores(company)
        assert scores["overall"] == 65

    def test_missing_score_defaults_to_100(self):
        company = {"history": []}
        scores = scraper_monitor.calculate_diversified_scores(company)
        assert scores["overall"] == 100

    def test_negative_data_case_lowers_data_practices(self):
        company = {
            "score": 80,
            "history": [
                {
                    "summaryPoints": [
                        {"text": "Data sold to third parties", "impact": "negative",
                         "case_id": "data-sold-third-parties"},
                    ]
                }
            ],
        }
        scores = scraper_monitor.calculate_diversified_scores(company)
        # data-sold-third-parties is Blocker (-50) → 100 - 50 = 50
        assert scores["dataPractices"] == 50
        # userRights has no cases → default
        assert scores["userRights"] == scraper_monitor._DEFAULT_SUBSCORE

    def test_negative_user_rights_case_lowers_user_rights(self):
        company = {
            "score": 80,
            "history": [
                {
                    "summaryPoints": [
                        {"text": "Mandatory arbitration", "impact": "negative",
                         "case_id": "arbitration-clause"},
                    ]
                }
            ],
        }
        scores = scraper_monitor.calculate_diversified_scores(company)
        # arbitration-clause is Blocker (-50) → 100 - 50 = 50
        assert scores["userRights"] == 50
        # dataPractices has no cases → default
        assert scores["dataPractices"] == scraper_monitor._DEFAULT_SUBSCORE

    def test_positive_case_raises_sub_score_above_default(self):
        company = {
            "score": 90,
            "history": [
                {
                    "summaryPoints": [
                        {"text": "Users retain content ownership", "impact": "positive",
                         "case_id": "content-ownership-retained"},
                    ]
                }
            ],
        }
        scores = scraper_monitor.calculate_diversified_scores(company)
        # content-ownership-retained is Good (+10) → 100 + 10 = 110 → clamped to 100
        assert scores["dataPractices"] == 100

    def test_readability_all_positive_returns_100(self):
        company = {
            "score": 90,
            "history": [
                {
                    "summaryPoints": [
                        {"text": "p1", "impact": "positive", "case_id": "other"},
                        {"text": "p2", "impact": "positive", "case_id": "other"},
                        {"text": "p3", "impact": "positive", "case_id": "other"},
                    ]
                }
            ],
        }
        scores = scraper_monitor.calculate_diversified_scores(company)
        assert scores["readability"] == 100

    def test_readability_all_negative_returns_0(self):
        company = {
            "score": 40,
            "history": [
                {
                    "summaryPoints": [
                        {"text": "n1", "impact": "negative", "case_id": "other"},
                        {"text": "n2", "impact": "negative", "case_id": "other"},
                    ]
                }
            ],
        }
        scores = scraper_monitor.calculate_diversified_scores(company)
        assert scores["readability"] == 0

    def test_readability_mixed_points_gives_midrange(self):
        company = {
            "score": 70,
            "history": [
                {
                    "summaryPoints": [
                        {"text": "p1", "impact": "positive", "case_id": "other"},
                        {"text": "n1", "impact": "negative", "case_id": "other"},
                    ]
                }
            ],
        }
        scores = scraper_monitor.calculate_diversified_scores(company)
        # 1 positive, 1 negative: 50 + (1-1)/2 * 50 = 50
        assert scores["readability"] == 50

    def test_case_ids_deduplicated_across_history_entries(self):
        company = {
            "score": 50,
            "history": [
                {
                    "summaryPoints": [
                        {"text": "Sold", "impact": "negative",
                         "case_id": "data-sold-third-parties"},
                    ]
                },
                {
                    "summaryPoints": [
                        {"text": "Sold again", "impact": "negative",
                         "case_id": "data-sold-third-parties"},  # duplicate
                    ]
                },
            ],
        }
        scores = scraper_monitor.calculate_diversified_scores(company)
        # Even with duplicate, weight applied once: 100 - 50 = 50
        assert scores["dataPractices"] == 50

    def test_top_level_summary_points_included(self):
        company = {
            "score": 80,
            "history": [],
            "summaryPoints": [
                {"text": "No class action", "impact": "negative",
                 "case_id": "no-class-action"},
            ],
        }
        scores = scraper_monitor.calculate_diversified_scores(company)
        # no-class-action is Bad (-20) → 100 - 20 = 80
        assert scores["userRights"] == 80

    def test_neutral_points_not_counted_as_positive_or_negative(self):
        company = {
            "score": 80,
            "history": [
                {
                    "summaryPoints": [
                        {"text": "Governed by California law", "impact": "neutral",
                         "case_id": "other"},
                    ]
                }
            ],
        }
        scores = scraper_monitor.calculate_diversified_scores(company)
        # No positive or negative points → readability defaults to _DEFAULT_SUBSCORE
        assert scores["readability"] == scraper_monitor._DEFAULT_SUBSCORE

    def test_new_case_unilateral_changes_applies_to_user_rights(self):
        company = {
            "score": 70,
            "history": [
                {
                    "summaryPoints": [
                        {"text": "Terms can change without notice", "impact": "negative",
                         "case_id": "unilateral-changes"},
                    ]
                }
            ],
        }
        scores = scraper_monitor.calculate_diversified_scores(company)
        # unilateral-changes is Bad (-20) → 100 - 20 = 80
        assert scores["userRights"] == 80

    def test_new_case_data_retention_limit_applies_to_data_practices(self):
        company = {
            "score": 90,
            "history": [
                {
                    "summaryPoints": [
                        {"text": "Data deleted after 12 months", "impact": "positive",
                         "case_id": "data-retention-limit"},
                    ]
                }
            ],
        }
        scores = scraper_monitor.calculate_diversified_scores(company)
        # data-retention-limit is Good (+10) → 100 + 10 = 110 → clamped to 100
        assert scores["dataPractices"] == 100

    def test_returns_dict_with_required_keys(self):
        company = {"score": 80, "history": []}
        scores = scraper_monitor.calculate_diversified_scores(company)
        for key in ("overall", "dataPractices", "userRights", "readability"):
            assert key in scores, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# add_benchmark_ranks
# ---------------------------------------------------------------------------

class TestAddBenchmarkRanks:
    """Verify add_benchmark_ranks() correctly computes ranks and industry average."""

    def _make_results(self, scores_list):
        return {
            "companies": [
                {"name": f"Co{i}", "score": s}
                for i, s in enumerate(scores_list)
            ]
        }

    def test_top_tier_company(self):
        results = self._make_results([100, 70, 70, 70, 70])
        scraper_monitor.add_benchmark_ranks(results)
        # avg ≈ 76; 100 - 76 = 24 ≥ 15 → Top Tier
        assert results["companies"][0]["scores"]["benchmarkRank"] == "Top Tier"

    def test_bottom_tier_company(self):
        results = self._make_results([30, 60, 60, 60, 60])
        scraper_monitor.add_benchmark_ranks(results)
        # avg = 54; 30 - 54 = -24 ≤ -15 → Bottom Tier
        assert results["companies"][0]["scores"]["benchmarkRank"] == "Bottom Tier"

    def test_above_average_company(self):
        results = self._make_results([80, 70, 70, 70, 70])
        scraper_monitor.add_benchmark_ranks(results)
        # avg = 72; 80 - 72 = 8, between 5 and 14 → Above Average
        assert results["companies"][0]["scores"]["benchmarkRank"] == "Above Average"

    def test_below_average_company(self):
        results = self._make_results([60, 70, 70, 70, 70])
        scraper_monitor.add_benchmark_ranks(results)
        # avg = 68; 60 - 68 = -8, between -5 and -14 → Below Average
        assert results["companies"][0]["scores"]["benchmarkRank"] == "Below Average"

    def test_average_company(self):
        results = self._make_results([70, 70, 70, 70, 70])
        scraper_monitor.add_benchmark_ranks(results)
        # avg = 70; 70 - 70 = 0, within ±5 → Average
        assert results["companies"][0]["scores"]["benchmarkRank"] == "Average"

    def test_industry_avg_set_on_all_companies(self):
        results = self._make_results([80, 60])
        scraper_monitor.add_benchmark_ranks(results)
        # avg = 70
        for company in results["companies"]:
            assert company["scores"]["industryAvg"] == 70.0

    def test_empty_companies_does_not_raise(self):
        results = {"companies": []}
        scraper_monitor.add_benchmark_ranks(results)  # should not raise

    def test_existing_scores_dict_preserved(self):
        results = {
            "companies": [
                {"name": "Co", "score": 80,
                 "scores": {"overall": 80, "dataPractices": 75}},
            ]
        }
        scraper_monitor.add_benchmark_ranks(results)
        # Existing keys should still be present
        assert results["companies"][0]["scores"]["dataPractices"] == 75
        assert "benchmarkRank" in results["companies"][0]["scores"]

    def test_company_without_scores_dict_gets_one_created(self):
        results = {"companies": [{"name": "Co", "score": 70}]}
        scraper_monitor.add_benchmark_ranks(results)
        assert isinstance(results["companies"][0].get("scores"), dict)
        assert "benchmarkRank" in results["companies"][0]["scores"]


# ---------------------------------------------------------------------------
# monitor() includes scores field
# ---------------------------------------------------------------------------

class TestMonitorIncludesScores:
    """Verify monitor() includes the scores field in company output."""

    def _make_company_config(self):
        return [{"name": "ScoreCo", "category": "Tech", "tosUrl": "https://scoreco.com/tos"}]

    def test_company_result_has_scores_field(self, tmp_env, monkeypatch):
        monkeypatch.setattr(scraper_monitor, "load_config", self._make_company_config)
        monkeypatch.setattr(scraper_monitor, "fetch_text", lambda url, **kw: "ToS content v1")
        monkeypatch.setattr(scraper_monitor, "call_openai_first_summary",
                            lambda text: {"Privacy": "ok", "DataOwnership": "ok", "UserRights": "ok"})

        results = scraper_monitor.monitor()
        company = next(c for c in results["companies"] if c["name"] == "ScoreCo")
        assert "scores" in company
        scores = company["scores"]
        for key in ("overall", "dataPractices", "userRights", "readability"):
            assert key in scores, f"scores missing key: {key}"

    def test_scores_overall_matches_company_score(self, tmp_env, monkeypatch):
        monkeypatch.setattr(scraper_monitor, "load_config", self._make_company_config)
        monkeypatch.setattr(scraper_monitor, "fetch_text", lambda url, **kw: "ToS content v1")
        monkeypatch.setattr(scraper_monitor, "call_openai_first_summary",
                            lambda text: {"Privacy": "ok", "DataOwnership": "ok", "UserRights": "ok"})

        results = scraper_monitor.monitor()
        company = next(c for c in results["companies"] if c["name"] == "ScoreCo")
        assert company["scores"]["overall"] == company["score"]

    def test_benchmark_rank_present_after_monitor(self, tmp_env, monkeypatch):
        monkeypatch.setattr(scraper_monitor, "load_config", self._make_company_config)
        monkeypatch.setattr(scraper_monitor, "fetch_text", lambda url, **kw: "ToS content v1")
        monkeypatch.setattr(scraper_monitor, "call_openai_first_summary",
                            lambda text: {"Privacy": "ok", "DataOwnership": "ok", "UserRights": "ok"})

        results = scraper_monitor.monitor()
        company = next(c for c in results["companies"] if c["name"] == "ScoreCo")
        assert "benchmarkRank" in company["scores"]
        assert "industryAvg" in company["scores"]


# ---------------------------------------------------------------------------
# validate_results accepts schema 2.2
# ---------------------------------------------------------------------------

class TestValidateResultsSchema22:
    """Verify validate_results() accepts schema version 2.2."""

    def _make_valid_results(self, schema="2.2"):
        return {
            "schemaVersion": schema,
            "updatedAt": "2026-03-08T00:00:00Z",
            "companies": [
                {
                    "name": "TestCo",
                    "category": "Tech",
                    "tosUrl": "https://test.com/tos",
                    "lastChecked": "2026-03-08T00:00:00Z",
                    "latestSummary": "Some summary",
                    "history": [
                        {
                            "previous_hash": None,
                            "current_hash": "abc123",
                            "timestamp": "2026-03-08T00:00:00Z",
                            "verdict": "Neutral",
                            "diffSummary": {
                                "Privacy": "No change",
                                "DataOwnership": "No change",
                                "UserRights": "No change",
                            },
                            "changeIsSubstantial": True,
                            "changeReason": "first version archived",
                        }
                    ],
                }
            ],
        }

    def test_schema_22_passes_validation(self):
        scraper_monitor.validate_results(self._make_valid_results("2.2"))

    def test_schema_21_still_passes(self):
        scraper_monitor.validate_results(self._make_valid_results("2.1"))

    def test_schema_20_still_passes(self):
        scraper_monitor.validate_results(self._make_valid_results("2.0"))

    def test_schema_23_raises(self):
        with pytest.raises(AssertionError):
            scraper_monitor.validate_results(self._make_valid_results("2.3"))


# ---------------------------------------------------------------------------
# load_cases – new cases present in cases.json
# ---------------------------------------------------------------------------

class TestNewCases:
    """Verify the two new cases added to cases.json are loadable and correct."""

    def test_unilateral_changes_case_present(self):
        cases = scraper_monitor.load_cases()
        ids = [c["id"] for c in cases]
        assert "unilateral-changes" in ids

    def test_unilateral_changes_weight(self):
        cases = scraper_monitor.load_cases()
        case = next(c for c in cases if c["id"] == "unilateral-changes")
        assert case["weight"] == -20
        assert case["topic"] == "UserRights"

    def test_data_retention_limit_case_present(self):
        cases = scraper_monitor.load_cases()
        ids = [c["id"] for c in cases]
        assert "data-retention-limit" in ids

    def test_data_retention_limit_weight(self):
        cases = scraper_monitor.load_cases()
        case = next(c for c in cases if c["id"] == "data-retention-limit")
        assert case["weight"] == 10
        assert case["topic"] == "Privacy"

    def test_total_case_count_is_12(self):
        cases = scraper_monitor.load_cases()
        assert len(cases) == 12


# ---------------------------------------------------------------------------
# compute_current_fields / get_company_current_fields
# ---------------------------------------------------------------------------

class TestComputeCurrentFields:
    """Tests for compute_current_fields() helper."""

    def test_returns_all_required_keys(self, monkeypatch):
        monkeypatch.setattr(scraper_monitor, "call_openai_overview", lambda t: "Overview text.")
        monkeypatch.setattr(scraper_monitor, "call_openai_points_summary", lambda t: [
            {"text": "Point one", "impact": "negative", "case_id": "data-training", "quote": "q1"},
        ])
        result = scraper_monitor.compute_current_fields("sample tos text", ["Arbitration"])
        for key in ("currentOverview", "currentSummaryPoints", "currentWatchlistHits",
                    "currentCaseIds", "currentWordCount"):
            assert key in result, f"Missing key: {key}"

    def test_current_overview_uses_openai(self, monkeypatch):
        monkeypatch.setattr(scraper_monitor, "call_openai_overview", lambda t: "My overview.")
        monkeypatch.setattr(scraper_monitor, "call_openai_points_summary", lambda t: [])
        result = scraper_monitor.compute_current_fields("text", [])
        assert result["currentOverview"] == "My overview."

    def test_current_summary_points_from_openai(self, monkeypatch):
        points = [{"text": "Sells data", "impact": "negative", "case_id": "data-sold", "quote": ""}]
        monkeypatch.setattr(scraper_monitor, "call_openai_overview", lambda t: "")
        monkeypatch.setattr(scraper_monitor, "call_openai_points_summary", lambda t: points)
        result = scraper_monitor.compute_current_fields("text", [])
        assert result["currentSummaryPoints"] == points

    def test_watchlist_hits_scans_full_text(self, monkeypatch):
        monkeypatch.setattr(scraper_monitor, "call_openai_overview", lambda t: "")
        monkeypatch.setattr(scraper_monitor, "call_openai_points_summary", lambda t: [])
        result = scraper_monitor.compute_current_fields(
            "We may use arbitration to resolve disputes.", ["Arbitration", "Class Action"]
        )
        assert "Arbitration" in result["currentWatchlistHits"]
        assert "Class Action" not in result["currentWatchlistHits"]

    def test_case_ids_derived_from_points(self, monkeypatch):
        points = [
            {"text": "A", "impact": "negative", "case_id": "data-training", "quote": ""},
            {"text": "B", "impact": "negative", "case_id": "arbitration-clause", "quote": ""},
            {"text": "C", "impact": "positive", "case_id": "other", "quote": ""},
            {"text": "D", "impact": "negative", "case_id": "data-training", "quote": ""},  # duplicate
        ]
        monkeypatch.setattr(scraper_monitor, "call_openai_overview", lambda t: "")
        monkeypatch.setattr(scraper_monitor, "call_openai_points_summary", lambda t: points)
        result = scraper_monitor.compute_current_fields("text", [])
        # "other" is excluded; duplicates deduplicated; order preserved
        assert result["currentCaseIds"] == ["data-training", "arbitration-clause"]

    def test_word_count_matches_split(self, monkeypatch):
        monkeypatch.setattr(scraper_monitor, "call_openai_overview", lambda t: "")
        monkeypatch.setattr(scraper_monitor, "call_openai_points_summary", lambda t: [])
        text = "one two three four five"
        result = scraper_monitor.compute_current_fields(text, [])
        assert result["currentWordCount"] == 5

    def test_word_count_empty_text(self, monkeypatch):
        monkeypatch.setattr(scraper_monitor, "call_openai_overview", lambda t: "")
        monkeypatch.setattr(scraper_monitor, "call_openai_points_summary", lambda t: [])
        result = scraper_monitor.compute_current_fields("", [])
        assert result["currentWordCount"] == 0


class TestGetCompanyCurrentFields:
    """Tests for get_company_current_fields() helper."""

    def test_returns_stored_fields_for_known_company(self):
        existing = {
            "companies": [
                {
                    "name": "Acme",
                    "currentOverview": "Overview",
                    "currentSummaryPoints": [],
                    "currentWatchlistHits": ["Arbitration"],
                    "currentCaseIds": ["data-training"],
                    "currentWordCount": 500,
                }
            ]
        }
        result = scraper_monitor.get_company_current_fields(existing, "Acme")
        assert result["currentOverview"] == "Overview"
        assert result["currentWatchlistHits"] == ["Arbitration"]
        assert result["currentCaseIds"] == ["data-training"]
        assert result["currentWordCount"] == 500

    def test_returns_empty_dict_for_unknown_company(self):
        existing = {"companies": [{"name": "Other", "currentOverview": "X"}]}
        result = scraper_monitor.get_company_current_fields(existing, "Acme")
        assert result == {}

    def test_returns_only_current_field_keys(self):
        existing = {
            "companies": [
                {
                    "name": "Acme",
                    "currentOverview": "Overview",
                    "score": 80,
                    "latestSummary": "old summary",
                }
            ]
        }
        result = scraper_monitor.get_company_current_fields(existing, "Acme")
        assert "score" not in result
        assert "latestSummary" not in result
        assert "currentOverview" in result

    def test_partial_fields_returned_when_some_missing(self):
        existing = {
            "companies": [
                {"name": "Acme", "currentOverview": "Overview"}
            ]
        }
        result = scraper_monitor.get_company_current_fields(existing, "Acme")
        assert result == {"currentOverview": "Overview"}

    def test_returns_empty_dict_when_no_companies_key(self):
        result = scraper_monitor.get_company_current_fields({}, "Acme")
        assert result == {}


class TestMonitorCurrentFields:
    """Integration-style tests verifying monitor() writes current* fields."""

    def test_current_fields_present_on_first_run(self, tmp_env, monkeypatch):
        """First run: text archived as first version → current* fields computed."""
        monkeypatch.setattr(scraper_monitor, "fetch_text", lambda url: "hello world terms of service")
        monkeypatch.setattr(scraper_monitor, "strip_navigation_preamble", lambda t: t)
        monkeypatch.setattr(scraper_monitor, "call_openai_overview", lambda t: "First overview.")
        monkeypatch.setattr(scraper_monitor, "call_openai_points_summary", lambda t: [
            {"text": "Data sold", "impact": "negative", "case_id": "data-training", "quote": "q"},
        ])
        monkeypatch.setattr(scraper_monitor, "call_openai_diff_summary", lambda t: {
            "Privacy": "OK", "DataOwnership": "OK", "UserRights": "OK"
        })
        monkeypatch.setattr(scraper_monitor, "load_config", lambda: [
            {"name": "TestCo", "tosUrl": "https://example.com/tos", "category": "Test"}
        ])

        results = scraper_monitor.monitor()
        company = results["companies"][0]
        assert "currentOverview" in company
        assert "currentSummaryPoints" in company
        assert "currentWatchlistHits" in company
        assert "currentCaseIds" in company
        assert "currentWordCount" in company

    def test_current_fields_present_when_text_unchanged(self, tmp_env, monkeypatch):
        """Second run with identical text: cached current* fields carried forward."""
        tos_text = "hello world terms of service"

        # Pre-populate both the snapshot and the ToS archive so monitor() sees
        # no change and takes the "not archived" (content unchanged) branch.
        scraper_monitor.ensure_dirs()
        scraper_monitor.write_snapshot("TestCo", tos_text)
        scraper_monitor.archive_tos_if_changed("TestCo", tos_text)

        # Pre-populate existing results with current* fields
        existing = {
            "schemaVersion": "2.2",
            "updatedAt": "2026-01-01T00:00:00+00:00",
            "companies": [
                {
                    "name": "TestCo",
                    "category": "Test",
                    "tosUrl": "https://example.com/tos",
                    "lastChecked": "2026-01-01T00:00:00+00:00",
                    "history": [],
                    "currentOverview": "Cached overview.",
                    "currentSummaryPoints": [],
                    "currentWatchlistHits": [],
                    "currentCaseIds": [],
                    "currentWordCount": 5,
                }
            ],
        }
        scraper_monitor.write_results(existing)

        monkeypatch.setattr(scraper_monitor, "fetch_text", lambda url: tos_text)
        monkeypatch.setattr(scraper_monitor, "strip_navigation_preamble", lambda t: t)
        monkeypatch.setattr(scraper_monitor, "load_config", lambda: [
            {"name": "TestCo", "tosUrl": "https://example.com/tos", "category": "Test"}
        ])
        # AI should NOT be called when text is unchanged and fields exist
        monkeypatch.setattr(scraper_monitor, "call_openai_overview",
                            lambda t: (_ for _ in ()).throw(AssertionError("Should not call OpenAI")))

        results = scraper_monitor.monitor()
        company = results["companies"][0]
        assert company["currentOverview"] == "Cached overview."
        assert "currentSummaryPoints" in company
        assert "currentWordCount" in company

    def test_current_fields_recomputed_on_text_change(self, tmp_env, monkeypatch):
        """When the ToS text changes, current* fields are recomputed fresh."""
        old_text = "old terms of service version one"
        new_text = "new terms of service version two"

        scraper_monitor.ensure_dirs()
        scraper_monitor.write_snapshot("TestCo", old_text)

        existing = {
            "schemaVersion": "2.2",
            "updatedAt": "2026-01-01T00:00:00+00:00",
            "companies": [
                {
                    "name": "TestCo",
                    "category": "Test",
                    "tosUrl": "https://example.com/tos",
                    "lastChecked": "2026-01-01T00:00:00+00:00",
                    "history": [],
                    "currentOverview": "Old overview.",
                    "currentSummaryPoints": [],
                    "currentWatchlistHits": [],
                    "currentCaseIds": [],
                    "currentWordCount": 6,
                }
            ],
        }
        scraper_monitor.write_results(existing)

        monkeypatch.setattr(scraper_monitor, "fetch_text", lambda url: new_text)
        monkeypatch.setattr(scraper_monitor, "strip_navigation_preamble", lambda t: t)
        monkeypatch.setattr(scraper_monitor, "call_openai_overview", lambda t: "New overview.")
        monkeypatch.setattr(scraper_monitor, "call_openai_points_summary", lambda t: [])
        monkeypatch.setattr(scraper_monitor, "call_openai_diff_summary", lambda t: {
            "Privacy": "Changed", "DataOwnership": "OK", "UserRights": "OK"
        })
        monkeypatch.setattr(scraper_monitor, "load_config", lambda: [
            {"name": "TestCo", "tosUrl": "https://example.com/tos", "category": "Test"}
        ])

        results = scraper_monitor.monitor()
        company = results["companies"][0]
        assert company["currentOverview"] == "New overview."
        assert company["currentWordCount"] == len(new_text.split())

    def test_current_fields_preserved_on_fetch_error(self, tmp_env, monkeypatch):
        """When fetching fails, existing current* fields are preserved."""
        existing = {
            "schemaVersion": "2.2",
            "updatedAt": "2026-01-01T00:00:00+00:00",
            "companies": [
                {
                    "name": "TestCo",
                    "category": "Test",
                    "tosUrl": "https://example.com/tos",
                    "lastChecked": "2026-01-01T00:00:00+00:00",
                    "history": [],
                    "currentOverview": "Preserved overview.",
                    "currentSummaryPoints": [],
                    "currentWatchlistHits": ["Arbitration"],
                    "currentCaseIds": [],
                    "currentWordCount": 100,
                }
            ],
        }
        scraper_monitor.write_results(existing)

        monkeypatch.setattr(scraper_monitor, "fetch_text",
                            lambda url: (_ for _ in ()).throw(ConnectionError("timeout")))
        monkeypatch.setattr(scraper_monitor, "load_config", lambda: [
            {"name": "TestCo", "tosUrl": "https://example.com/tos", "category": "Test"}
        ])

        results = scraper_monitor.monitor()
        company = results["companies"][0]
        assert company["currentOverview"] == "Preserved overview."
        assert company["currentWatchlistHits"] == ["Arbitration"]
        assert company["currentWordCount"] == 100
