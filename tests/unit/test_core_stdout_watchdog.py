"""Tests for backend.core.stdout_watchdog — WatchdogResult, _fallback_summary, watch_output."""
import pytest
from backend.core.stdout_watchdog import WatchdogResult, _fallback_summary


class TestWatchdogResult:
    def test_creation(self):
        wr = WatchdogResult(success=True, output="test", truncated=False)
        assert wr.success is True
        assert wr.output == "test"
        assert wr.truncated is False


class TestFallbackSummary:
    def test_short_text(self):
        result = _fallback_summary("hello world", 100)
        assert result == "hello world"

    def test_long_text_truncated(self):
        result = _fallback_summary("x" * 200, 50)
        assert len(result) <= 60  # 50 + "...[truncated]" overhead

    def test_empty(self):
        result = _fallback_summary("", 100)
        assert result == ""
