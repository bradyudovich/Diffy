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
        assert results.get("schemaVersion") == "2.1"

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
