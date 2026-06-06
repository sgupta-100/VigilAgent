"""Tests for backend.core.telemetry — Telemetry, TelemetrySpan."""
import time
from unittest.mock import patch
from backend.core.telemetry import Telemetry, TelemetrySpan


class TestTelemetrySpan:
    def test_creation(self):
        span = TelemetrySpan(name="test_op")
        assert span.name == "test_op"
        assert span.start_time > 0

    def test_finish(self):
        span = TelemetrySpan(name="test_op")
        time.sleep(0.01)
        span.finish()
        assert span.end_time > 0
        assert span.duration_ms >= 0

    def test_finish_with_error(self):
        span = TelemetrySpan(name="test_op")
        span.finish(error="something failed")
        assert span.error == "something failed"


class TestTelemetry:
    def test_init(self):
        t = Telemetry()
        assert t._spans == []
        assert t._counters == {}

    def test_start_span(self):
        t = Telemetry()
        span = t.start_span("op1")
        assert isinstance(span, TelemetrySpan)
        assert span.name == "op1"

    def test_record_counter(self):
        t = Telemetry()
        t.record_counter("requests", 1)
        t.record_counter("requests", 5)
        assert t._counters["requests"] == 6

    def test_get_summary(self):
        t = Telemetry()
        t.start_span("op1")
        t.record_counter("req", 10)
        summary = t.get_summary()
        assert "spans" in summary
        assert "counters" in summary
        assert summary["counters"]["req"] == 10

    def test_reset(self):
        t = Telemetry()
        t.record_counter("x", 1)
        t.reset()
        assert t._counters == {}
