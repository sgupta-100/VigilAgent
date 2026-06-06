"""Tests for backend.core.context — ScanContext, transcript, event dedup, cancellation."""
import pytest
from unittest.mock import MagicMock
from backend.core.context import ScanContext


class TestScanContext:
    def test_init_defaults(self):
        sc = ScanContext()
        assert sc.scan_id  # UUID auto-generated
        assert sc.baseline_cache == {}
        assert sc.diff_cache == {}
        assert sc.is_cancelled is False

    def test_init_custom_id(self):
        sc = ScanContext(scan_id="my-scan-123")
        assert sc.scan_id == "my-scan-123"

    def test_transcript_starts_empty(self):
        sc = ScanContext()
        assert len(sc.transcript) == 0
        assert sc.transcript_text() == ""

    def test_append_event(self):
        sc = ScanContext()
        event = MagicMock()
        event.payload = {"url": "http://example.com"}
        event.timestamp = "2026-01-01T00:00:00"
        event.type = MagicMock()
        event.type.value = "LIVE_ATTACK"
        event.source = "Alpha"
        event.id = "evt-1"
        event.scan_id = "scan-1"

        block = sc.append_event(event)
        assert "[Event]" in block
        assert "http://example.com" in block
        assert len(sc.transcript) == 1

    def test_transcript_bounded(self):
        sc = ScanContext()
        for i in range(6000):
            event = MagicMock()
            event.payload = {"i": i}
            event.timestamp = None
            event.type = MagicMock()
            event.type.value = "TEST"
            event.source = "test"
            event.id = str(i)
            event.scan_id = "s1"
            sc.append_event(event)
        # Should be capped at 5000
        assert len(sc.transcript) == 5000

    def test_transcript_text_tail(self):
        sc = ScanContext()
        for i in range(10):
            event = MagicMock()
            event.payload = {"i": i}
            event.timestamp = None
            event.type = MagicMock()
            event.type.value = "TEST"
            event.source = "test"
            event.id = str(i)
            event.scan_id = "s1"
            sc.append_event(event)
        text = sc.transcript_text(tail=3)
        assert text.count("[Event]") == 3

    def test_cancelled_flag(self):
        sc = ScanContext()
        sc.is_cancelled = True
        assert sc.is_cancelled is True

    def test_workflow_state(self):
        sc = ScanContext()
        sc.workflow_state["key"] = "value"
        assert sc.workflow_state["key"] == "value"

    def test_event_queue(self):
        sc = ScanContext()
        assert sc.event_queue.empty()
