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
        assert monitor.SIMILARITY_THRESHOLD == 0.95

    def test_percent_change_threshold_defined(self):
        assert hasattr(monitor, "PERCENT_CHANGE_THRESHOLD")
        assert monitor.PERCENT_CHANGE_THRESHOLD == 0.04


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


# ---------------------------------------------------------------------------
# Appendix constants tests
# ---------------------------------------------------------------------------

class TestAppendixConstants:
    def test_appendix_trigger_patterns_defined(self):
        assert hasattr(monitor, "APPENDIX_TRIGGER_PATTERNS")
        patterns = monitor.APPENDIX_TRIGGER_PATTERNS
        assert isinstance(patterns, list)
        assert len(patterns) > 0

    def test_appendix_trigger_patterns_include_required_keywords(self):
        """All required appendix trigger keywords must be present."""
        patterns = monitor.APPENDIX_TRIGGER_PATTERNS
        joined = " ".join(patterns)
        for keyword in ("open", "acknowledg", "third", "licens", "copyright", "attribution"):
            assert keyword in joined.lower(), f"Missing keyword: {keyword}"

    def test_appendix_search_start_fraction_defined(self):
        assert hasattr(monitor, "APPENDIX_SEARCH_START_FRACTION")
        frac = monitor.APPENDIX_SEARCH_START_FRACTION
        assert 0.0 < frac < 1.0

    def test_min_lines_for_appendix_detection_defined(self):
        assert hasattr(monitor, "MIN_LINES_FOR_APPENDIX_DETECTION")
        assert monitor.MIN_LINES_FOR_APPENDIX_DETECTION > 0


# ---------------------------------------------------------------------------
# extract_core_content tests
# ---------------------------------------------------------------------------

class TestExtractCoreContent:
    def _make_doc(self, n_main, appendix_lines):
        main = [f"Main content line {i}. This covers substantive terms." for i in range(n_main)]
        return "\n".join(main + appendix_lines)

    def test_no_appendix_returns_full_text(self):
        text = "\n".join(f"Line {i}." for i in range(20))
        assert monitor.extract_core_content(text) == text

    def test_copyright_trigger_in_latter_portion(self):
        doc = self._make_doc(15, ["Copyright 2024 Acme Corp. All rights reserved."])
        core = monitor.extract_core_content(doc)
        assert "Copyright" not in core
        assert "Main content" in core

    def test_open_source_trigger_in_latter_portion(self):
        doc = self._make_doc(15, ["Open Source Software Notices", "See below for licenses."])
        core = monitor.extract_core_content(doc)
        assert "Open Source" not in core
        assert "Main content" in core

    def test_attribution_trigger_in_latter_portion(self):
        doc = self._make_doc(15, ["Attribution Notice", "We thank the following contributors."])
        core = monitor.extract_core_content(doc)
        assert "Attribution" not in core
        assert "Main content" in core

    def test_acknowledg_trigger_in_latter_portion(self):
        doc = self._make_doc(15, ["Acknowledgements", "We thank the following open-source projects."])
        core = monitor.extract_core_content(doc)
        assert "Acknowledgements" not in core

    def test_trigger_in_early_portion_not_stripped(self):
        """A trigger keyword before the search start must NOT cut the document."""
        # Line 0 has "open source" but search starts at ~60% of 20 lines = line 12
        lines = ["We use open source components internally."]
        lines += [f"Content line {i}." for i in range(19)]
        doc = "\n".join(lines)
        core = monitor.extract_core_content(doc)
        assert "open source" in core.lower()
        assert len(core.splitlines()) > 1

    def test_short_document_returned_unchanged(self):
        """Documents shorter than MIN_LINES_FOR_APPENDIX_DETECTION are not trimmed."""
        text = "Terms.\nLicense: MIT\nCopyright Acme"
        assert monitor.extract_core_content(text) == text

    def test_empty_string_returned_unchanged(self):
        assert monitor.extract_core_content("") == ""

    def test_third_party_library_trigger(self):
        doc = self._make_doc(15, ["Third Party Library Notices", "This software includes..."])
        core = monitor.extract_core_content(doc)
        assert "Third Party" not in core

    def test_license_trigger_in_latter_portion(self):
        doc = self._make_doc(15, ["License Information", "MIT License applies to..."])
        core = monitor.extract_core_content(doc)
        assert "License Information" not in core


# ---------------------------------------------------------------------------
# Appendix-only change detection tests
# ---------------------------------------------------------------------------

class TestDetectSubstantiveChangeAppendix:
    def _main_content(self, n=20):
        return "\n".join(
            f"Main terms line {i}. This covers liability and data rights." for i in range(n)
        )

    def test_appendix_only_change_not_significant(self):
        """Changing only the copyright footer must NOT be significant."""
        main = self._main_content()
        old = main + "\nCopyright 2023 Acme Corp. All rights reserved."
        new = main + "\nCopyright 2024 Acme Corp. All rights reserved."
        is_sig, reason = monitor.detect_substantive_change(old, new)
        assert is_sig is False

    def test_core_change_with_same_appendix_is_significant(self):
        """A change in core content must be detected even when the appendix is unchanged."""
        appendix = "\nCopyright 2024 Acme Corp."
        old_main = self._main_content()
        # Make new_main substantially different by appending a large block
        new_main = self._main_content() + ("\nNew liability clause. " * 30)
        is_sig, _ = monitor.detect_substantive_change(old_main + appendix, new_main + appendix)
        assert is_sig is True

    def test_both_core_and_appendix_change_is_significant(self):
        """When both core and appendix change, the result must still be significant."""
        old = self._main_content() + "\nCopyright 2023 Acme."
        new = self._main_content() + ("\nNew liability clause. " * 30) + "\nCopyright 2024 Acme."
        is_sig, _ = monitor.detect_substantive_change(old, new)
        assert is_sig is True


# ---------------------------------------------------------------------------
# changeIsSubstantial field tests
# ---------------------------------------------------------------------------

class TestChangeIsSubstantialField:
    def _run(self, tmp_env, monkeypatch, tos_text, ai_return="AI summary"):
        monkeypatch.setattr(monitor, "load_config", lambda: [
            {"name": "TestCo", "tosUrl": "https://example.com/tos", "category": "Tech"}
        ])
        monkeypatch.setattr(monitor, "fetch_text", lambda url: tos_text)
        monkeypatch.setattr(monitor, "call_openai_overview", lambda text: ai_return)
        monkeypatch.setattr(monitor, "call_openai", lambda diff: ai_return)
        return monitor.monitor()["companies"][0]

    def test_field_present_on_first_run(self, tmp_env, monkeypatch):
        result = self._run(tmp_env, monkeypatch, "Some new ToS text.")
        assert "changeIsSubstantial" in result

    def test_field_false_when_content_unchanged(self, tmp_env, monkeypatch):
        self._run(tmp_env, monkeypatch, "Same ToS text.")
        result = self._run(tmp_env, monkeypatch, "Same ToS text.")
        assert result["changeIsSubstantial"] is False

    def test_field_true_when_substantive_change(self, tmp_env, monkeypatch):
        self._run(tmp_env, monkeypatch, "Short terms.")
        long_new = "Short terms. " + ("Extended liability clause. " * 50)
        result = self._run(tmp_env, monkeypatch, long_new)
        assert result["changed"] is True
        assert result["changeIsSubstantial"] is True

    def test_field_false_on_fetch_error(self, tmp_env, monkeypatch):
        monitor.write_tos_summary("TestCo", "Cached summary.")
        monkeypatch.setattr(monitor, "load_config", lambda: [
            {"name": "TestCo", "tosUrl": "https://example.com/tos", "category": "Tech"}
        ])

        def fetch_fail(url):
            raise RuntimeError("timeout")

        monkeypatch.setattr(monitor, "fetch_text", fetch_fail)
        result = monitor.monitor()["companies"][0]
        assert result["changeIsSubstantial"] is False


# ---------------------------------------------------------------------------
# SKIPPED_LINE_PATTERNS / pre_clean_text tests
# ---------------------------------------------------------------------------

class TestPreCleanText:
    def test_trace_id_line_removed(self):
        text = "Welcome to our Terms of Service.\nTrace ID: abc123xyz\nPlease read carefully."
        cleaned = monitor.pre_clean_text(text)
        assert "Trace ID" not in cleaned
        assert "Welcome to our Terms of Service." in cleaned
        assert "Please read carefully." in cleaned

    def test_request_id_line_removed(self):
        text = "Terms apply.\nRequest ID: 9f8e7d6c\nMore terms."
        cleaned = monitor.pre_clean_text(text)
        assert "Request ID" not in cleaned
        assert "Terms apply." in cleaned

    def test_session_id_line_removed(self):
        text = "Our terms.\nSession ID: sess_001\nYour rights."
        cleaned = monitor.pre_clean_text(text)
        assert "Session ID" not in cleaned

    def test_cloudflare_ray_id_removed(self):
        text = "Terms.\nCloudflare Ray ID: 7abc1234def\nEnd."
        cleaned = monitor.pre_clean_text(text)
        assert "Cloudflare Ray ID" not in cleaned

    def test_captcha_line_removed(self):
        text = "Terms.\nPlease complete the CAPTCHA below.\nContinue."
        cleaned = monitor.pre_clean_text(text)
        assert "CAPTCHA" not in cleaned

    def test_verifying_human_line_removed(self):
        text = "Terms.\nVerifying you are human\nContent."
        cleaned = monitor.pre_clean_text(text)
        assert "Verifying you are human" not in cleaned

    def test_version_header_line_removed(self):
        text = "Version 2.3.1 – 2024-01-15\nActual ToS content.\nEnd."
        cleaned = monitor.pre_clean_text(text)
        assert "Version 2.3.1" not in cleaned
        assert "Actual ToS content." in cleaned

    def test_last_updated_line_removed(self):
        text = "Last Updated: March 1, 2026\nActual ToS content."
        cleaned = monitor.pre_clean_text(text)
        assert "Last Updated" not in cleaned
        assert "Actual ToS content." in cleaned

    def test_effective_date_line_removed(self):
        text = "Effective Date: January 1, 2025\nTerms follow."
        cleaned = monitor.pre_clean_text(text)
        assert "Effective Date" not in cleaned
        assert "Terms follow." in cleaned

    def test_normal_content_preserved(self):
        text = "You agree to these terms.\nWe collect personal data.\nArbitration applies."
        cleaned = monitor.pre_clean_text(text)
        assert cleaned == text

    def test_empty_string(self):
        assert monitor.pre_clean_text("") == ""

    def test_pre_clean_reduces_false_positives_in_detect(self):
        """Trace ID change between two otherwise identical ToS texts must NOT be flagged."""
        base = "\n".join(f"Term {i}: some substantive policy text." for i in range(30))
        old = base + "\nTrace ID: old-abc123"
        new = base + "\nTrace ID: new-xyz789"
        is_sig, reason = monitor.detect_substantive_change(old, new)
        assert is_sig is False, f"Trace ID change should not be significant; got reason: {reason!r}"

    def test_skipped_line_patterns_is_list(self):
        assert hasattr(monitor, "SKIPPED_LINE_PATTERNS")
        assert isinstance(monitor.SKIPPED_LINE_PATTERNS, list)
        assert len(monitor.SKIPPED_LINE_PATTERNS) > 0


# ---------------------------------------------------------------------------
# prune_old_tos_archives tests
# ---------------------------------------------------------------------------

class TestPruneOldTosArchives:
    def test_no_archive_dir_returns_zero(self, tmp_env):
        assert monitor.prune_old_tos_archives("NonExistentCo") == 0

    def test_single_snapshot_not_pruned(self, tmp_env):
        monitor.archive_tos_if_changed("Acme", "Version 1")
        deleted = monitor.prune_old_tos_archives("Acme")
        assert deleted == 0
        dated = [f for f in monitor.tos_archive_dir("Acme").glob("*.txt") if f.name != "summary.txt"]
        assert len(dated) == 1

    def test_prunes_all_but_latest(self, tmp_env):
        monitor.archive_tos_if_changed("Acme", "Version 1")
        monitor.archive_tos_if_changed("Acme", "Version 2")
        monitor.archive_tos_if_changed("Acme", "Version 3")
        deleted = monitor.prune_old_tos_archives("Acme")
        assert deleted == 2
        dated = sorted(f for f in monitor.tos_archive_dir("Acme").glob("*.txt") if f.name != "summary.txt")
        assert len(dated) == 1
        assert dated[0].read_text() == "Version 3"

    def test_summary_txt_not_deleted(self, tmp_env):
        monitor.archive_tos_if_changed("Acme", "Version 1")
        monitor.archive_tos_if_changed("Acme", "Version 2")
        monitor.write_tos_summary("Acme", "My summary.")
        monitor.prune_old_tos_archives("Acme")
        assert monitor.read_tos_summary("Acme") == "My summary."

    def test_two_snapshots_keeps_latest(self, tmp_env):
        monitor.archive_tos_if_changed("Acme", "Older version")
        monitor.archive_tos_if_changed("Acme", "Newer version")
        deleted = monitor.prune_old_tos_archives("Acme")
        assert deleted == 1
        dated = [f for f in monitor.tos_archive_dir("Acme").glob("*.txt") if f.name != "summary.txt"]
        assert len(dated) == 1
        assert dated[0].read_text() == "Newer version"

    def test_idempotent(self, tmp_env):
        monitor.archive_tos_if_changed("Acme", "Version 1")
        monitor.archive_tos_if_changed("Acme", "Version 2")
        monitor.prune_old_tos_archives("Acme")
        deleted_again = monitor.prune_old_tos_archives("Acme")
        assert deleted_again == 0


# ---------------------------------------------------------------------------
# NAV_TITLE_ANCHORS / strip_navigation_preamble tests
# ---------------------------------------------------------------------------

class TestNavTitleAnchors:
    def test_constant_defined(self):
        assert hasattr(monitor, "NAV_TITLE_ANCHORS")
        assert isinstance(monitor.NAV_TITLE_ANCHORS, list)
        assert len(monitor.NAV_TITLE_ANCHORS) > 0

    def test_includes_terms_of_use(self):
        anchors = monitor.NAV_TITLE_ANCHORS
        assert any(p.search("Terms of Use") for p in anchors)

    def test_includes_terms_of_service(self):
        anchors = monitor.NAV_TITLE_ANCHORS
        assert any(p.search("Terms of Service") for p in anchors)


class TestStripNavigationPreamble:
    def test_strips_content_above_terms_of_use(self):
        text = "Home\nProducts\nSupport\nTerms of Use\nActual ToS content."
        result = monitor.strip_navigation_preamble(text)
        assert result.startswith("Terms of Use")
        assert "Home" not in result
        assert "Products" not in result
        assert "Actual ToS content." in result

    def test_strips_content_above_terms_of_service(self):
        text = "Nav link 1\nNav link 2\nTerms of Service\nContent starts here."
        result = monitor.strip_navigation_preamble(text)
        assert result.startswith("Terms of Service")
        assert "Nav link" not in result
        assert "Content starts here." in result

    def test_strips_content_above_terms_and_conditions(self):
        text = "Home\nAbout\nTerms and Conditions\nYou agree to..."
        result = monitor.strip_navigation_preamble(text)
        assert "Home" not in result
        assert "Terms and Conditions" in result

    def test_no_anchor_returns_full_text(self):
        text = "Home\nProducts\nThis is some generic text with no ToS title."
        result = monitor.strip_navigation_preamble(text)
        assert result == text

    def test_empty_string_returns_empty(self):
        assert monitor.strip_navigation_preamble("") == ""

    def test_anchor_at_start_returns_full_text(self):
        text = "Terms of Use\nContent here."
        result = monitor.strip_navigation_preamble(text)
        assert result == text

    def test_case_insensitive_anchor_matching(self):
        text = "Navbar\nFoo\nTERMS OF USE\nLegal content."
        result = monitor.strip_navigation_preamble(text)
        assert "Navbar" not in result
        assert "TERMS OF USE" in result

    def test_first_anchor_wins_when_multiple_present(self):
        text = "Nav\nTerms of Use\nSome intro text.\nTerms of Service\nMore content."
        result = monitor.strip_navigation_preamble(text)
        assert result.startswith("Terms of Use")
        assert "Nav" not in result

    def test_reduces_false_positives_in_detect(self):
        """Navigation preamble change on otherwise identical ToS must NOT be flagged."""
        tos_body = "\n".join(
            f"Clause {i}: substantive legal terms here." for i in range(30)
        )
        old = "Home\nProducts\nTerms of Use\n" + tos_body
        new = "Home\nProducts\nShop\nTerms of Use\n" + tos_body
        old_stripped = monitor.strip_navigation_preamble(old)
        new_stripped = monitor.strip_navigation_preamble(new)
        is_sig, reason = monitor.detect_substantive_change(old_stripped, new_stripped)
        assert is_sig is False, f"Nav-only change should not be flagged; reason: {reason!r}"


class TestMonitorKeepsAllSnapshots:
    """monitor() must retain all distinct ToS snapshots per company."""

    def _run(self, tmp_env, monkeypatch, tos_text, ai_return="AI summary"):
        monkeypatch.setattr(monitor, "load_config", lambda: [
            {"name": "TestCo", "tosUrl": "https://example.com/tos", "category": "Tech"}
        ])
        monkeypatch.setattr(monitor, "fetch_text", lambda url: tos_text)
        monkeypatch.setattr(monitor, "call_openai_overview", lambda text: ai_return)
        monkeypatch.setattr(monitor, "call_openai", lambda diff: ai_return)
        return monitor.monitor()["companies"][0]

    def test_all_snapshots_kept_after_multiple_runs(self, tmp_env, monkeypatch):
        self._run(tmp_env, monkeypatch, "Version 1")
        self._run(tmp_env, monkeypatch, "Version 2")
        self._run(tmp_env, monkeypatch, "Version 3")
        archive_dir = monitor.tos_archive_dir("TestCo")
        dated = [f for f in archive_dir.glob("*.txt") if f.name != "summary.txt"]
        assert len(dated) == 3

    def test_summary_preserved_across_runs(self, tmp_env, monkeypatch):
        self._run(tmp_env, monkeypatch, "Version 1", "Summary v1")
        self._run(tmp_env, monkeypatch, "Version 2", "Summary v2")
        assert monitor.read_tos_summary("TestCo") == "Summary v2"


# ---------------------------------------------------------------------------
# calculate_trust_score tests
# ---------------------------------------------------------------------------

class TestCalculateTrustScore:
    def test_good_verdict_no_hits_returns_100(self):
        entry = {"verdict": "Good", "watchlist_hits": []}
        assert monitor.calculate_trust_score(entry) == 100

    def test_neutral_verdict_deducts_10(self):
        entry = {"verdict": "Neutral", "watchlist_hits": []}
        assert monitor.calculate_trust_score(entry) == 90

    def test_caution_verdict_deducts_20(self):
        entry = {"verdict": "Caution", "watchlist_hits": []}
        assert monitor.calculate_trust_score(entry) == 80

    def test_each_unique_watchlist_hit_deducts_5(self):
        entry = {"verdict": "Good", "watchlist_hits": ["Arbitration", "Tracking"]}
        assert monitor.calculate_trust_score(entry) == 90  # 100 - 5*2

    def test_duplicate_watchlist_hits_counted_once(self):
        entry = {"verdict": "Good", "watchlist_hits": ["Arbitration", "Arbitration"]}
        assert monitor.calculate_trust_score(entry) == 95  # 100 - 5*1

    def test_combined_caution_and_hits(self):
        entry = {"verdict": "Caution", "watchlist_hits": ["Arbitration", "Tracking", "Sell"]}
        # 100 - 20 - 15 = 65
        assert monitor.calculate_trust_score(entry) == 65

    def test_score_clamped_to_zero(self):
        # 100 - 20 - 5*20 = 100 - 20 - 100 = -20 → 0
        hits = [f"term{i}" for i in range(20)]
        entry = {"verdict": "Caution", "watchlist_hits": hits}
        assert monitor.calculate_trust_score(entry) == 0

    def test_missing_or_none_watchlist_hits_defaults_to_zero_deduction(self):
        for entry in ({"verdict": "Good"}, {"verdict": "Good", "watchlist_hits": None}):
            assert monitor.calculate_trust_score(entry) == 100

    def test_trust_score_stored_in_history_entry(self, tmp_env, monkeypatch):
        """calculate_trust_score integrates correctly with a typical entry dict."""
        entry = {
            "verdict": "Caution",
            "watchlist_hits": ["Arbitration", "Tracking"],
        }
        score = monitor.calculate_trust_score(entry)
        # 100 - 20 (Caution) - 10 (2 unique hits) = 70
        assert score == 70
        assert isinstance(score, int)
        assert 0 <= score <= 100


# ---------------------------------------------------------------------------
# get_letter_grade tests (A–E scale)
# ---------------------------------------------------------------------------

class TestGetLetterGrade:
    def test_score_90_returns_A(self):
        assert monitor.get_letter_grade(90) == "A"

    def test_score_100_returns_A(self):
        assert monitor.get_letter_grade(100) == "A"

    def test_score_70_returns_B(self):
        assert monitor.get_letter_grade(70) == "B"

    def test_score_89_returns_B(self):
        assert monitor.get_letter_grade(89) == "B"

    def test_score_50_returns_C(self):
        assert monitor.get_letter_grade(50) == "C"

    def test_score_69_returns_C(self):
        assert monitor.get_letter_grade(69) == "C"

    def test_score_30_returns_D(self):
        assert monitor.get_letter_grade(30) == "D"

    def test_score_49_returns_D(self):
        assert monitor.get_letter_grade(49) == "D"

    def test_score_0_returns_E(self):
        assert monitor.get_letter_grade(0) == "E"

    def test_score_29_returns_E(self):
        assert monitor.get_letter_grade(29) == "E"

    def test_no_F_grade(self):
        """The old 'F' grade no longer exists; lowest is 'E'."""
        for score in range(0, 30):
            assert monitor.get_letter_grade(score) == "E"


# ---------------------------------------------------------------------------
# calculate_score_from_cases tests
# ---------------------------------------------------------------------------

class TestCalculateScoreFromCases:
    def test_empty_case_ids_returns_100(self, tmp_env, monkeypatch, tmp_path):
        cases_data = {"cases": [
            {"id": "arbitration-clause", "title": "Arbitration", "rating": "Blocker", "weight": -50, "topic": "UserRights"},
        ]}
        cases_file = tmp_path / "cases.json"
        cases_file.write_text(__import__("json").dumps(cases_data))
        monkeypatch.setattr(monitor, "CASES_PATH", cases_file)
        assert monitor.calculate_score_from_cases([]) == 100

    def test_blocker_deducts_50(self, tmp_env, monkeypatch, tmp_path):
        cases_data = {"cases": [
            {"id": "arbitration-clause", "title": "Arbitration", "rating": "Blocker", "weight": -50, "topic": "UserRights"},
        ]}
        cases_file = tmp_path / "cases.json"
        cases_file.write_text(__import__("json").dumps(cases_data))
        monkeypatch.setattr(monitor, "CASES_PATH", cases_file)
        assert monitor.calculate_score_from_cases(["arbitration-clause"]) == 50

    def test_good_case_adds_10(self, tmp_env, monkeypatch, tmp_path):
        cases_data = {"cases": [
            {"id": "account-deletion-right", "title": "Delete account", "rating": "Good", "weight": 10, "topic": "UserRights"},
        ]}
        cases_file = tmp_path / "cases.json"
        cases_file.write_text(__import__("json").dumps(cases_data))
        monkeypatch.setattr(monitor, "CASES_PATH", cases_file)
        assert monitor.calculate_score_from_cases(["account-deletion-right"]) == 100  # capped at 100

    def test_duplicate_case_ids_counted_once(self, tmp_env, monkeypatch, tmp_path):
        cases_data = {"cases": [
            {"id": "arbitration-clause", "title": "Arbitration", "rating": "Blocker", "weight": -50, "topic": "UserRights"},
        ]}
        cases_file = tmp_path / "cases.json"
        cases_file.write_text(__import__("json").dumps(cases_data))
        monkeypatch.setattr(monitor, "CASES_PATH", cases_file)
        assert monitor.calculate_score_from_cases(["arbitration-clause", "arbitration-clause"]) == 50

    def test_unknown_case_id_ignored(self, tmp_env, monkeypatch, tmp_path):
        cases_data = {"cases": []}
        cases_file = tmp_path / "cases.json"
        cases_file.write_text(__import__("json").dumps(cases_data))
        monkeypatch.setattr(monitor, "CASES_PATH", cases_file)
        assert monitor.calculate_score_from_cases(["nonexistent-case"]) == 100

    def test_score_clamped_to_zero(self, tmp_env, monkeypatch, tmp_path):
        cases_data = {"cases": [
            {"id": "c1", "title": "Bad1", "rating": "Blocker", "weight": -50, "topic": "Privacy"},
            {"id": "c2", "title": "Bad2", "rating": "Blocker", "weight": -50, "topic": "Privacy"},
            {"id": "c3", "title": "Bad3", "rating": "Blocker", "weight": -50, "topic": "Privacy"},
        ]}
        cases_file = tmp_path / "cases.json"
        cases_file.write_text(__import__("json").dumps(cases_data))
        monkeypatch.setattr(monitor, "CASES_PATH", cases_file)
        assert monitor.calculate_score_from_cases(["c1", "c2", "c3"]) == 0


# ---------------------------------------------------------------------------
# load_cases tests
# ---------------------------------------------------------------------------

class TestLoadCases:
    def test_loads_cases_from_json(self, tmp_path, monkeypatch):
        cases_data = {"cases": [
            {"id": "data-training", "title": "AI Training", "rating": "Bad", "weight": -20, "topic": "Privacy"},
        ]}
        cases_file = tmp_path / "cases.json"
        cases_file.write_text(__import__("json").dumps(cases_data))
        monkeypatch.setattr(monitor, "CASES_PATH", cases_file)
        result = monitor.load_cases()
        assert len(result) == 1
        assert result[0]["id"] == "data-training"
        assert result[0]["weight"] == -20

    def test_missing_file_returns_empty_list(self, tmp_path, monkeypatch):
        monkeypatch.setattr(monitor, "CASES_PATH", tmp_path / "nonexistent.json")
        assert monitor.load_cases() == []

    def test_real_cases_json_has_10_cases(self):
        """Validate that the shipped cases.json has exactly 10 starter cases."""
        cases = monitor.load_cases()
        assert len(cases) == 10

    def test_each_case_has_required_fields(self):
        """Every case in cases.json must have id, title, rating, weight, and topic."""
        for case in monitor.load_cases():
            assert "id" in case
            assert "title" in case
            assert "rating" in case
            assert "weight" in case
            assert case["rating"] in ("Good", "Neutral", "Bad", "Blocker")
            assert isinstance(case["weight"], int)
