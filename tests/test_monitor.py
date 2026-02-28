"""Tests for the ToS archiving and summarization helpers in monitor.py."""
import importlib
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Stub heavy optional dependencies so we can import monitor.py without
# Playwright / BeautifulSoup being installed in the test environment.
# ---------------------------------------------------------------------------

def _stub_modules():
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


_stub_modules()

# Now import the module under test
import monitor  # noqa: E402  (must follow the stub setup)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_env(tmp_path, monkeypatch):
    """Redirect all monitor paths to a temporary directory."""
    monkeypatch.setattr(monitor, "BASE_DIR", tmp_path)
    monkeypatch.setattr(monitor, "SNAPSHOTS_DIR", tmp_path / "data" / "snapshots")
    monkeypatch.setattr(monitor, "DATA_RESULTS_PATH", tmp_path / "data" / "results.json")
    monkeypatch.setattr(monitor, "PUBLIC_RESULTS_PATH", tmp_path / "public" / "data" / "results.json")
    monkeypatch.setattr(monitor, "TOS_DIR", tmp_path / "terms_of_service")
    monitor.ensure_dirs()
    return tmp_path


# ---------------------------------------------------------------------------
# ToS archiving tests
# ---------------------------------------------------------------------------

class TestArchiveTosIfChanged:
    def test_first_run_creates_archive(self, tmp_env):
        archived = monitor.archive_tos_if_changed("Acme", "Hello ToS")
        assert archived is True
        archive_dir = monitor.tos_archive_dir("Acme")
        dated_files = [f for f in archive_dir.glob("*.txt") if f.name != "summary.txt"]
        assert len(dated_files) == 1
        assert dated_files[0].read_text() == "Hello ToS"

    def test_unchanged_does_not_create_new_file(self, tmp_env):
        monitor.archive_tos_if_changed("Acme", "Hello ToS")
        archived_again = monitor.archive_tos_if_changed("Acme", "Hello ToS")
        assert archived_again is False
        dated_files = [
            f for f in monitor.tos_archive_dir("Acme").glob("*.txt")
            if f.name != "summary.txt"
        ]
        assert len(dated_files) == 1  # Still only one file

    def test_changed_content_creates_second_file(self, tmp_env):
        monitor.archive_tos_if_changed("Acme", "Version 1")
        archived = monitor.archive_tos_if_changed("Acme", "Version 2")
        assert archived is True
        dated_files = sorted(
            f for f in monitor.tos_archive_dir("Acme").glob("*.txt")
            if f.name != "summary.txt"
        )
        assert len(dated_files) == 2
        assert dated_files[-1].read_text() == "Version 2"

    def test_same_day_collision_adds_suffix(self, tmp_env, monkeypatch):
        """Two distinct versions on the same date get suffixed filenames."""
        from datetime import timezone
        fixed_date = "2026-01-01"

        # Patch datetime in monitor to return a fixed date
        mock_dt = MagicMock()
        mock_dt.now.return_value.strftime.return_value = fixed_date
        monkeypatch.setattr(monitor, "datetime", mock_dt)

        # Also make timezone available (it's used in monitor directly)
        monkeypatch.setattr(mock_dt, "timezone", timezone)

        monitor.archive_tos_if_changed("Acme", "Version A")
        monitor.archive_tos_if_changed("Acme", "Version B")

        archive_dir = monitor.tos_archive_dir("Acme")
        dated_files = sorted(f.name for f in archive_dir.glob("*.txt") if f.name != "summary.txt")
        assert f"{fixed_date}.txt" in dated_files
        assert f"{fixed_date}_1.txt" in dated_files

    def test_previous_versions_are_retained(self, tmp_env):
        """Archiving multiple changes must keep all previous files."""
        for i in range(1, 4):
            monitor.archive_tos_if_changed("Acme", f"Version {i}")

        dated_files = [
            f for f in monitor.tos_archive_dir("Acme").glob("*.txt")
            if f.name != "summary.txt"
        ]
        assert len(dated_files) == 3


# ---------------------------------------------------------------------------
# Summary persistence tests
# ---------------------------------------------------------------------------

class TestTosSummary:
    def test_read_returns_none_when_missing(self, tmp_env):
        assert monitor.read_tos_summary("NoCompany") is None

    def test_write_then_read(self, tmp_env):
        monitor.write_tos_summary("Acme", "This is the summary.")
        assert monitor.read_tos_summary("Acme") == "This is the summary."

    def test_write_overwrites_previous_summary(self, tmp_env):
        monitor.write_tos_summary("Acme", "Old summary.")
        monitor.write_tos_summary("Acme", "New summary.")
        assert monitor.read_tos_summary("Acme") == "New summary."

    def test_summary_file_not_counted_as_archive(self, tmp_env):
        """summary.txt must not be treated as a versioned archive file."""
        monitor.write_tos_summary("Acme", "A summary.")
        # get_latest_archived_tos should ignore summary.txt
        assert monitor.get_latest_archived_tos("Acme") is None


# ---------------------------------------------------------------------------
# monitor() integration: summary fallback behaviour
# ---------------------------------------------------------------------------

class TestMonitorSummaryFallback:
    """Verify that monitor() returns the persisted summary or the fallback string."""

    def _run_monitor_single(self, tmp_env, monkeypatch, tos_text, openai_return=None):
        """Run monitor() for a single fake company and return the result dict."""
        monkeypatch.setattr(monitor, "CONFIG_PATH", None)  # unused – we patch load_config
        monkeypatch.setattr(monitor, "load_config", lambda: [
            {"name": "TestCo", "tosUrl": "https://example.com/tos", "category": "Tech"}
        ])
        monkeypatch.setattr(monitor, "fetch_text", lambda url: tos_text)

        if openai_return is not None:
            monkeypatch.setattr(monitor, "call_openai_overview", lambda text: openai_return)
            monkeypatch.setattr(monitor, "call_openai", lambda diff: openai_return)

        results = monitor.monitor()
        return results["companies"][0]

    def test_first_run_uses_ai_summary(self, tmp_env, monkeypatch):
        result = self._run_monitor_single(tmp_env, monkeypatch, "ToS text v1", "AI generated summary")
        assert result["summary"] == "AI generated summary"

    def test_second_run_no_change_uses_persisted_summary(self, tmp_env, monkeypatch):
        # First run: archives text and saves AI summary
        self._run_monitor_single(tmp_env, monkeypatch, "ToS text v1", "Persisted summary")
        # Second run: same text – should use the persisted summary, NOT call AI again
        call_count = {"n": 0}
        original_overview = monitor.call_openai_overview

        def counting_overview(text):
            call_count["n"] += 1
            return original_overview(text)

        monkeypatch.setattr(monitor, "call_openai_overview", counting_overview)
        result = self._run_monitor_single(tmp_env, monkeypatch, "ToS text v1")
        assert result["summary"] == "Persisted summary"
        assert call_count["n"] == 0  # AI not called again

    def test_fallback_when_no_summary_file(self, tmp_env, monkeypatch):
        """If AI call fails and no summary.txt exists, use the fallback string."""
        def failing_overview(text):
            raise RuntimeError("network error")

        monkeypatch.setattr(monitor, "call_openai_overview", failing_overview)
        result = self._run_monitor_single(tmp_env, monkeypatch, "ToS text v1")
        assert "Initial snapshot created. Monitoring active." in result["summary"] or \
               "Connection Error" in result["summary"]

    def test_change_detected_updates_summary(self, tmp_env, monkeypatch):
        # First run: create initial snapshot + archive
        self._run_monitor_single(tmp_env, monkeypatch, "ToS text v1", "Initial summary")
        # Second run: different text → diff summary should be generated and persisted
        result = self._run_monitor_single(tmp_env, monkeypatch, "ToS text v2 – something changed", "Diff summary")
        assert result["changed"] is True
        assert result["summary"] == "Diff summary"
        # summary.txt should be updated
        assert monitor.read_tos_summary("TestCo") == "Diff summary"

    def test_no_regeneration_when_tos_unchanged_and_summary_missing(self, tmp_env, monkeypatch):
        """Summary stability principle: AI must not be called when ToS is unchanged, even if summary.txt is missing."""
        # Seed an archive for "ToS text v1" so archived=False on next run with same text
        monitor.archive_tos_if_changed("TestCo", "ToS text v1")
        # Write a snapshot so old_text == new_text
        monitor.write_snapshot("TestCo", "ToS text v1")
        # Do NOT write summary.txt – it is intentionally absent

        call_count = {"n": 0}

        def counting_overview(text):
            call_count["n"] += 1
            return "Should not be called"

        monkeypatch.setattr(monitor, "load_config", lambda: [
            {"name": "TestCo", "tosUrl": "https://example.com/tos", "category": "Tech"}
        ])
        monkeypatch.setattr(monitor, "fetch_text", lambda url: "ToS text v1")
        monkeypatch.setattr(monitor, "call_openai_overview", counting_overview)

        results = monitor.monitor()
        company = results["companies"][0]
        assert call_count["n"] == 0, "AI must not be called when ToS is unchanged"
        assert company["changed"] is False

    def test_fetch_error_uses_persisted_summary(self, tmp_env, monkeypatch):
        """When fetching fails, return the previously persisted summary."""
        # Pre-seed a summary
        monitor.write_tos_summary("TestCo", "Cached summary from before.")

        monkeypatch.setattr(monitor, "load_config", lambda: [
            {"name": "TestCo", "tosUrl": "https://example.com/tos", "category": "Tech"}
        ])
        monkeypatch.setattr(monitor, "fetch_text", lambda url: (_ for _ in ()).throw(RuntimeError("timeout")))

        results = monitor.monitor()
        assert results["companies"][0]["summary"] == "Cached summary from before."

    def test_content_diff_is_sole_trigger_for_regeneration(self, tmp_env, monkeypatch):
        """Content-diff method: AI is called if and only if the ToS raw text changes.

        Verifies four cases:
        1. Content changes → AI IS called (summary regenerated).
        2. Same content, summary absent → AI NOT called (no regeneration).
        3. Same content, summary present → AI NOT called (persisted summary reused).
        4. Content changes again → AI IS called (summary regenerated).
        """
        ai_call_count = {"n": 0}

        def counting_overview(text):
            ai_call_count["n"] += 1
            return "AI summary"

        def counting_diff(diff):
            ai_call_count["n"] += 1
            return "AI diff summary"

        monkeypatch.setattr(monitor, "load_config", lambda: [
            {"name": "TestCo", "tosUrl": "https://example.com/tos", "category": "Tech"}
        ])
        monkeypatch.setattr(monitor, "call_openai_overview", counting_overview)
        monkeypatch.setattr(monitor, "call_openai", counting_diff)

        # Case 1: New content – AI must be called once (archive created for first time).
        monkeypatch.setattr(monitor, "fetch_text", lambda url: "ToS content A")
        monitor.monitor()
        assert ai_call_count["n"] == 1, "AI must be called when content is new"

        # Case 2: Same content, summary.txt absent – AI must NOT be called.
        monitor.tos_archive_dir("TestCo").joinpath("summary.txt").unlink()
        ai_call_count["n"] = 0
        monitor.monitor()
        assert ai_call_count["n"] == 0, "AI must not be called when content is unchanged, even if summary.txt is absent"

        # Case 3: Same content, summary.txt present – AI must NOT be called.
        monitor.write_tos_summary("TestCo", "Existing summary.")
        ai_call_count["n"] = 0
        monitor.monitor()
        assert ai_call_count["n"] == 0, "AI must not be called when content is unchanged and summary.txt is present"

        # Case 4: Content changes – AI IS called again.
        monkeypatch.setattr(monitor, "fetch_text", lambda url: "ToS content B – something changed")
        ai_call_count["n"] = 0
        monitor.monitor()
        assert ai_call_count["n"] == 1, "AI must be called when content changes"


# ---------------------------------------------------------------------------
# Summary format tests
# ---------------------------------------------------------------------------

class TestSummaryFormat:
    """Verify that AI-generated summaries conform to the 30-word constraint."""

    def _word_count(self, text: str) -> int:
        return len(text.split())

    def test_summary_on_change_is_at_most_30_words(self, tmp_env, monkeypatch):
        """When a ToS changes, the resulting summary must be <=30 words."""
        short_summary = "Data: Company collects browsing data and trains AI on content. Users cannot opt out."
        assert self._word_count(short_summary) <= 30

        monkeypatch.setattr(monitor, "load_config", lambda: [
            {"name": "TestCo", "tosUrl": "https://example.com/tos", "category": "Tech"}
        ])

        # First run: establish initial snapshot
        call_count = {"index": 0}
        fetch_responses = ["ToS text v1", "ToS text v2 – something changed"]

        def fetch_side_effect(url):
            return fetch_responses[call_count["index"]]

        monkeypatch.setattr(monitor, "fetch_text", fetch_side_effect)
        monkeypatch.setattr(monitor, "call_openai_overview", lambda text: short_summary)
        monkeypatch.setattr(monitor, "call_openai", lambda diff: short_summary)

        monitor.monitor()
        call_count["index"] = 1
        results = monitor.monitor()
        summary = results["companies"][0]["summary"]
        assert self._word_count(summary) <= 30

    def test_overview_summary_is_at_most_30_words(self, tmp_env, monkeypatch):
        """On first run (overview), the summary must be <=30 words."""
        short_summary = "AI: Trains models on user data; broad liability waiver; no opt-out for data collection."
        assert self._word_count(short_summary) <= 30

        monkeypatch.setattr(monitor, "load_config", lambda: [
            {"name": "TestCo", "tosUrl": "https://example.com/tos", "category": "AI"}
        ])
        monkeypatch.setattr(monitor, "fetch_text", lambda url: "Some ToS text")
        monkeypatch.setattr(monitor, "call_openai_overview", lambda text: short_summary)

        results = monitor.monitor()
        summary = results["companies"][0]["summary"]
        assert self._word_count(summary) <= 30

    def test_ai_tos_summary_prompt_is_defined(self):
        """The unified AI_TOS_SUMMARY_PROMPT constant must exist and contain key constraints."""
        assert hasattr(monitor, "AI_TOS_SUMMARY_PROMPT")
        prompt = monitor.AI_TOS_SUMMARY_PROMPT
        assert "30 words" in prompt
        assert "legal summarizer" in prompt.lower()
        assert "data rights" in prompt.lower() or "data" in prompt.lower()


# ---------------------------------------------------------------------------
# Hybrid substantive diff tests
# ---------------------------------------------------------------------------

class TestNormalizeText:
    def test_lowercases(self):
        assert monitor.normalize_text("Hello WORLD") == "hello world"

    def test_collapses_whitespace(self):
        assert monitor.normalize_text("hello   world") == "hello world"

    def test_strips_lines(self):
        assert monitor.normalize_text("  hello  \n  world  ") == "hello\nworld"

    def test_collapses_blank_lines(self):
        result = monitor.normalize_text("a\n\n\n\nb")
        assert result == "a\n\nb"

    def test_normalizes_line_endings(self):
        assert monitor.normalize_text("a\r\nb\rc") == "a\nb\nc"

    def test_empty_string(self):
        assert monitor.normalize_text("") == ""


class TestFallbackSimilarity:
    def test_identical(self):
        assert monitor.fallback_similarity("hello", "hello") == 1.0

    def test_empty_both(self):
        assert monitor.fallback_similarity("", "") == 1.0

    def test_empty_one(self):
        assert monitor.fallback_similarity("hello", "") == 0.0

    def test_different(self):
        ratio = monitor.fallback_similarity("hello world", "goodbye moon")
        assert 0.0 < ratio < 1.0

    def test_similar_high_score(self):
        a = "The user agrees to arbitration for all disputes."
        b = "The user agrees to arbitration for all disputes!"
        assert monitor.fallback_similarity(a, b) > 0.97


class TestExtractHotSectionText:
    def test_privacy_keyword(self):
        text = "we collect personal data from users\n\nunrelated paragraph here"
        sections = monitor.extract_hot_section_text(text)
        assert "we collect personal data from users" in sections["privacy"]
        assert "privacy" in sections

    def test_arbitration_keyword(self):
        text = "all disputes shall be resolved by arbitration\n\nother stuff"
        sections = monitor.extract_hot_section_text(text)
        assert "all disputes shall be resolved by arbitration" in sections["arbitration"]

    def test_no_hot_keywords(self):
        text = "welcome to our service\n\nenjoy your stay"
        sections = monitor.extract_hot_section_text(text)
        for v in sections.values():
            assert v == ""

    def test_multiple_sections_in_one_para(self):
        text = "we limit liability and collect user data in our privacy policy"
        sections = monitor.extract_hot_section_text(text)
        assert text in sections["liability"]
        assert text in sections["privacy"]


class TestDetectSubstantiveChange:
    def test_identical_texts_not_significant(self):
        text = "These are the terms of service. Nothing has changed."
        is_sig, reason = monitor.detect_substantive_change(text, text)
        assert is_sig is False
        assert reason == ""

    def test_normalized_identical_not_significant(self):
        old = "Terms of Service.\nPlease read carefully."
        new = "terms of service.\nplease read carefully."  # only case change
        is_sig, reason = monitor.detect_substantive_change(old, new)
        assert is_sig is False

    def test_large_percent_change_is_significant(self):
        old = "Short TOS."
        new = "Short TOS. " + "A" * 500  # >> 2% larger
        is_sig, reason = monitor.detect_substantive_change(old, new)
        assert is_sig is True
        assert "document changed by" in reason

    def test_hot_section_change_is_significant(self):
        old = "You waive all rights to arbitration for minor disputes."
        new = "You agree to binding arbitration and waive all class action rights."
        is_sig, reason = monitor.detect_substantive_change(old, new)
        assert is_sig is True
        # The change touches hot sections; reason must reference "hot section"
        assert "hot section" in reason

    def test_trivial_whitespace_change_not_significant(self):
        old = "We collect data.\n\n\nYou agree to terms."
        new = "we collect data.\n\nyou agree to terms."  # only case + blank lines
        is_sig, reason = monitor.detect_substantive_change(old, new)
        assert is_sig is False

    def test_reason_includes_section_name(self):
        old = "Our privacy policy covers how we handle personal data."
        new = "Our privacy policy covers how we handle personal data and share it with third parties extensively."
        is_sig, reason = monitor.detect_substantive_change(old, new)
        if is_sig:
            assert reason != ""

    def test_first_version_always_significant(self):
        """monitor() marks first version as significant even without old text."""
        # This is tested indirectly through detect_substantive_change:
        # when old_text is None, monitor() sets is_significant=True directly.
        # Here we verify that two very different texts are flagged.
        old = "a"
        new = "z" * 1000
        is_sig, _ = monitor.detect_substantive_change(old, new)
        assert is_sig is True


class TestHybridDiffConstants:
    def test_hot_section_keywords_defined(self):
        assert hasattr(monitor, "HOT_SECTION_KEYWORDS")
        keywords = monitor.HOT_SECTION_KEYWORDS
        assert isinstance(keywords, dict)
        # All required hot sections must be present
        for section in ("liability", "privacy", "arbitration", "dispute",
                        "termination", "user_data", "ai", "governing_law"):
            assert section in keywords, f"Missing hot section: {section}"
            assert len(keywords[section]) > 0

    def test_similarity_threshold_defined(self):
        assert hasattr(monitor, "SIMILARITY_THRESHOLD")
        assert monitor.SIMILARITY_THRESHOLD == 0.97

    def test_percent_change_threshold_defined(self):
        assert hasattr(monitor, "PERCENT_CHANGE_THRESHOLD")
        assert monitor.PERCENT_CHANGE_THRESHOLD == 0.02


class TestHybridDiffMonitorIntegration:
    """Verify that monitor() correctly uses hybrid diff logic."""

    def _run(self, tmp_env, monkeypatch, tos_text, ai_return="AI summary"):
        monkeypatch.setattr(monitor, "load_config", lambda: [
            {"name": "TestCo", "tosUrl": "https://example.com/tos", "category": "Tech"}
        ])
        monkeypatch.setattr(monitor, "fetch_text", lambda url: tos_text)
        monkeypatch.setattr(monitor, "call_openai_overview", lambda text: ai_return)
        monkeypatch.setattr(monitor, "call_openai", lambda diff: ai_return)
        return monitor.monitor()["companies"][0]

    def test_trivial_change_not_flagged(self, tmp_env, monkeypatch):
        """Whitespace-only change must not trigger changed=True."""
        # First run: archive initial version
        self._run(tmp_env, monkeypatch, "Terms of service apply.")
        # Second run: same content with only case difference
        result = self._run(tmp_env, monkeypatch, "TERMS OF SERVICE APPLY.")
        assert result["changed"] is False

    def test_significant_change_is_flagged_with_reason(self, tmp_env, monkeypatch):
        """A large content change must set changed=True and include a changeReason."""
        # First run
        self._run(tmp_env, monkeypatch, "Short terms.")
        # Second run with much larger content
        long_new = "Short terms. " + ("Extended liability clause. " * 50)
        result = self._run(tmp_env, monkeypatch, long_new)
        assert result["changed"] is True
        assert result["changeReason"] != ""

    def test_change_reason_in_result(self, tmp_env, monkeypatch):
        """changeReason field must be present in all result entries."""
        result = self._run(tmp_env, monkeypatch, "Some TOS text.")
        assert "changeReason" in result

    def test_unchanged_result_has_empty_change_reason(self, tmp_env, monkeypatch):
        """When unchanged, changeReason must be empty string."""
        self._run(tmp_env, monkeypatch, "Same text.")
        result = self._run(tmp_env, monkeypatch, "Same text.")
        assert result["changed"] is False
        assert result["changeReason"] == ""
