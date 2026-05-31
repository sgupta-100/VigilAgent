"""Unit tests for IntegrationCoordinator (deep-system-integration task 1.6).

Smoke-grade coverage of the six behaviours called out in the task:
  * initialization with all flags off
  * event routing when disabled
  * circuit breaker opens on repeated failures
  * batch processing flushes on size threshold
  * batch processing flushes on timeout
  * metrics snapshot shape

Architecture invariants honoured:
  §9   scope-is-law   — every URL/host is a fake .local; no real network.
  §11  two-LLM        — no LLM bindings touched; collaborators are mocks.
  §29.13 non-blocking — async collaborators are AsyncMock; the batch
                        drainer is exercised through ``asyncio.sleep``.

These tests intentionally use no Redis / no LLM / no Docker; they validate
the coordinator's internal contract against in-memory test doubles.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.core.integration_config import IntegrationConfig
from backend.core.integration_coordinator import IntegrationCoordinator

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------
class _FakeBus:
    """Minimal pub/sub bus matching the coordinator's subscribe surface."""

    def __init__(self) -> None:
        self.handlers: Dict[str, List[Any]] = {}

    async def subscribe(self, event_type: str, handler) -> None:
        self.handlers.setdefault(event_type, []).append(handler)

    async def publish(self, event_type: str, data: Dict[str, Any], **kw) -> None:
        scan_id = kw.get("scan_id", "unit-test")
        for h in self.handlers.get(event_type, []):
            await h({"data": data, "scan_id": scan_id})


def _make_config(**overrides: Any) -> IntegrationConfig:
    """Phase-1 default: every feature flag OFF."""
    base: Dict[str, Any] = dict(
        enable_browser_learning=False,
        enable_cross_system_healing=False,
        enable_forensic_learning=False,
        enable_intelligent_routing=False,
        event_batch_size=10,
        event_batch_timeout_ms=50,
        max_concurrent_learning=2,
        circuit_breaker_threshold=5,
        circuit_breaker_timeout_s=60,
    )
    base.update(overrides)
    return IntegrationConfig(**base)


def _build(config: IntegrationConfig | None = None):
    """Construct a coordinator wired to AsyncMock collaborators."""
    bus = _FakeBus()
    learning_engine = MagicMock(name="LearningEngine")
    learning_engine.learn_from_browser_vulnerability = AsyncMock(return_value=True)
    learning_engine.learn_framework_pattern = AsyncMock(return_value=True)
    coord = IntegrationCoordinator(
        bus=bus,
        learning_engine=learning_engine,
        skill_library=MagicMock(name="SkillLibrary"),
        health_monitor=MagicMock(name="HealthMonitor"),
        healing_engine=MagicMock(name="HealingEngine"),
        browser_orchestrator=MagicMock(name="BrowserOrchestrator"),
        config=config or _make_config(),
    )
    return coord, bus, learning_engine


# ---------------------------------------------------------------------------
# 1.6 — required test cases
# ---------------------------------------------------------------------------
async def test_initialization_with_all_flags_off() -> None:
    """Pre-``initialize()``: no subscriptions, no batch task running."""
    coord, bus, _ = _build()
    assert bus.handlers == {}
    assert coord._batch_task is None
    assert coord._initialized is False
    # Flags really are off.
    assert coord.config.enable_browser_learning is False
    assert coord.config.enable_cross_system_healing is False


async def test_event_routing_when_disabled() -> None:
    """Flags OFF → handler skips downstream call and bumps events_skipped."""
    coord, bus, learning_engine = _build()  # all flags OFF
    try:
        await coord.initialize()
        await bus.publish(
            "VULN_CONFIRMED",
            {"vuln_type": "XSS", "url": "https://t.local/"},
            scan_id="off-1",
        )
        await bus.publish(
            "BROWSER_DISCOVERY",
            {"framework": "React", "routes": ["/r/0"]},
            scan_id="off-2",
        )
        await bus.publish(
            "AGENT_FAILURE", {"reason": "crash"}, scan_id="off-3"
        )
        learning_engine.learn_from_browser_vulnerability.assert_not_awaited()
        learning_engine.learn_framework_pattern.assert_not_awaited()
        assert coord.get_integration_metrics()["events_skipped"] >= 3
    finally:
        await coord.shutdown()


async def test_circuit_breaker_opens_on_repeated_failures() -> None:
    """Threshold consecutive failures trip the breaker; further calls skip."""
    coord, bus, learning_engine = _build(
        _make_config(enable_browser_learning=True, circuit_breaker_threshold=3)
    )
    learning_engine.learn_from_browser_vulnerability = AsyncMock(
        side_effect=RuntimeError("synthetic")
    )
    try:
        await coord.initialize()
        for i in range(3):
            await bus.publish(
                "VULN_CONFIRMED",
                {"vuln_type": "XSS", "url": f"https://t.local/{i}"},
                scan_id=f"cb-{i}",
            )
        assert coord._cb_vuln.trips == 1
        m = coord.get_integration_metrics()
        assert m["events_failed"] == 3
        assert m["circuit_breaker_trips"] >= 1

        # Breaker now OPEN → subsequent call is dropped silently.
        before = learning_engine.learn_from_browser_vulnerability.await_count
        await bus.publish(
            "VULN_CONFIRMED",
            {"vuln_type": "XSS", "url": "https://t.local/skipped"},
            scan_id="cb-skip",
        )
        assert (
            learning_engine.learn_from_browser_vulnerability.await_count == before
        )
        assert coord.get_integration_metrics()["events_skipped"] >= 1
    finally:
        await coord.shutdown()


async def test_batch_processing_flushes_on_size() -> None:
    """Discovery buffer hits ``event_batch_size`` → synchronous flush."""
    coord, bus, learning_engine = _build(
        _make_config(
            enable_browser_learning=True,
            event_batch_size=3,
            event_batch_timeout_ms=10_000,  # large — size-trigger only
        )
    )
    try:
        await coord.initialize()
        for i in range(3):
            await bus.publish(
                "BROWSER_DISCOVERY",
                {"framework": "React", "routes": [f"/r/{i}"]},
                scan_id="b-size",
            )
        assert learning_engine.learn_framework_pattern.await_count == 3
        m = coord.get_integration_metrics()
        assert m["batches_flushed"] == 1
        assert m["last_batch_size"] == 3
        assert m["pending_discoveries"] == 0
    finally:
        await coord.shutdown()


async def test_batch_processing_flushes_on_timeout() -> None:
    """Background drainer fires after the timeout window elapses."""
    coord, bus, learning_engine = _build(
        _make_config(
            enable_browser_learning=True,
            event_batch_size=100,        # never hit by size
            event_batch_timeout_ms=50,   # short timeout
        )
    )
    try:
        await coord.initialize()
        await bus.publish(
            "BROWSER_DISCOVERY",
            {"framework": "Vue", "routes": ["/x"]},
            scan_id="b-time",
        )
        await asyncio.sleep(0.2)  # let the drainer wake at least once
        assert learning_engine.learn_framework_pattern.await_count == 1
        assert coord.get_integration_metrics()["batches_flushed"] >= 1
    finally:
        await coord.shutdown()


async def test_metrics_snapshot_shape() -> None:
    """``get_integration_metrics()`` returns the documented keys."""
    coord, _, _ = _build()
    m = coord.get_integration_metrics()
    expected_top_level = {
        "events_processed",
        "events_failed",
        "events_skipped",
        "failure_rate",
        "circuit_breaker_trips",
        "pending_discoveries",
        "batches_flushed",
        "last_batch_size",
        "features_enabled",
    }
    assert expected_top_level.issubset(m.keys())
    assert isinstance(m["features_enabled"], dict)
    assert {
        "browser_learning",
        "cross_system_healing",
        "forensic_learning",
        "intelligent_routing",
    }.issubset(m["features_enabled"].keys())
    assert m["events_processed"] == 0
    assert m["failure_rate"] == 0.0
    assert m["pending_discoveries"] == 0
