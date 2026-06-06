"""Tests for backend.core.tracing — TracingConfig, NoOpTracer, NoOpSpan, trace_span."""
import pytest
from backend.core.tracing import (
    TracingConfig, NoOpTracer, NoOpSpan, trace_span,
    get_tracer, shutdown_tracing,
)


class TestTracingConfig:
    def test_defaults(self):
        tc = TracingConfig()
        assert tc.enabled is False
        assert tc.service_name == "vigilagent"


class TestNoOpTracer:
    def test_start_span(self):
        tracer = NoOpTracer()
        span = tracer.start_span("test")
        assert isinstance(span, NoOpSpan)


class TestNoOpSpan:
    def test_set_attribute(self):
        span = NoOpSpan()
        span.set_attribute("key", "value")
        assert span is not None

    def test_add_event(self):
        span = NoOpSpan()
        span.add_event("event_name", {"key": "val"})
        assert span is not None

    def test_end(self):
        span = NoOpSpan()
        span.end()
        assert span is not None

    def test_context_manager(self):
        with NoOpSpan() as span:
            assert span is not None


class TestTraceSpan:
    def test_context_manager(self):
        with trace_span("test_op") as span:
            assert span is not None


class TestGetTracer:
    def test_returns_tracer(self):
        tracer = get_tracer()
        assert tracer is not None


class TestShutdownTracing:
    def test_no_error(self):
        shutdown_tracing()
