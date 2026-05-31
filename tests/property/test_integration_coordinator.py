"""Unit tests for IntegrationCoordinator (deep-system-integration task 1.6).

Covers:
  * Initialization (subscribe to VULN_CONFIRMED / BROWSER_DISCOVERY /
    AGENT_FAILURE; idempotent re-init; batch drainer task started).
  * Event routing under feature flags ON / OFF.
  * Circuit breaker behaviour on the vulnerability path.
  * Discovery batch processing (size-trigger and timeout-trigger).

Architecture invariants honoured:
  §9   scope-is-law   — no real network calls; all targets are fake URLs.
  §11  two-LLM        — no LLM imports touched; all collaborators are mocks.
  §29.13 non-blocking — every collaborator is an ``AsyncMock`` and the
                        coordinator's batch drainer is exercised through
                        ``await asyncio.sleep`` rather than blocking ``time``.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.core.integration_config import IntegrationConfig
from backend.core.integration_coordinator import (
    IntegrationCoordinator,
    _LocalCircuitBreaker,
)

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# In-memory test doubles
# ---------------------------------------------------------------------------
class _FakeBus:
    """Minimal pub/sub bus matching IntegrationCoordinator's subscribe surface."""

    def __init__(self) -> None:
        self.handlers: Dict[str, List[Any]] = {}

    async def subscribe(self, event_type: str, handler) -> None:
        self.handlers.setdefault(event_type, []).append(handler)

    async def publish(self, event_type: str, data: Dict[str, Any], **kw) -> None:
        scan_id = kw.get("scan_id", "unit-test")
        for h in self.handlers.get(event_type, []):
            await h({"data": data, "scan_id": scan_id})


def _make_config(**overrides: Any) -> IntegrationConfig:
    """Default: everything OFF (matches spec Phase-1 default)."""
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


def _make_learning_engine() -> MagicMock:
    eng = MagicMock(name="LearningEngine")
    eng.learn_from_browser_vulnerability = AsyncMock(return_value=True)
    eng.learn_framework_pattern = AsyncMock(return_value=True)
    return eng


def _build(coord_config: IntegrationConfig | None = None):
    bus = _FakeBus()
    learning_engine = _make_learning_engine()
    coord = IntegrationCoordinator(
        bus=bus,
        learning_engine=learning_engine,
        skill_library=MagicMock(name="SkillLibrary"),
        health_monitor=MagicMock(name="HealthMonitor"),
        healing_engine=MagicMock(name="HealingEngine"),
        browser_orchestrator=MagicMock(name="BrowserOrchestrator"),
        config=coord_config or _make_config(),
    )
    return coord, bus, learning_engine


# ---------------------------------------------------------------------------
# 1.6.a — Initialization
# ---------------------------------------------------------------------------
class TestInitialization:
    """initialize() subscribes to all three event types and starts the drainer."""

    async def test_initialize_subscribes_to_all_event_types(self) -> None:
        coord, bus, _ = _build()
        try:
            await coord.initialize()
            assert "VULN_CONFIRMED" in bus.handlers
            assert "BROWSER_DISCOVERY" in bus.handlers
            assert "AGENT_FAILURE" in bus.handlers
        finally:
            await coord.shutdown()

    async def test_initialize_starts_batch_drainer_task(self) -> None:
        coord, _, _ = _build()
        try:
            await coord.initialize()
            assert coord._batch_task is not None
            assert not coord._batch_task.done()
        finally:
            await coord.shutdown()

    async def test_initialize_is_idempotent(self) -> None:
        coord, bus, _ = _build()
        try:
            await coord.initialize()
            await coord.initialize()  # second call is no-op
            # Each event type should still have exactly one handler registered.
            for event_type in ("VULN_CONFIRMED", "BROWSER_DISCOVERY", "AGENT_FAILURE"):
                assert len(bus.handlers[event_type]) == 1
        finally:
            await coord.shutdown()

    async def test_get_integration_metrics_initial_state(self) -> None:
        coord, _, _ = _build()
        metrics = coord.get_integration_metrics()
        assert metrics["events_processed"] == 0
        assert metrics["events_failed"] == 0
        assert metrics["pending_discoveries"] == 0
        assert metrics["features_enabled"]["browser_learning"] is False


# ---------------------------------------------------------------------------
# 1.6.b — Event routing
# ---------------------------------------------------------------------------
class TestEventRouting:
    """Vuln / discovery / failure paths honour feature flags."""

    async def test_vulnerability_skipped_when_browser_learning_off(self) -> None:
        coord, bus, learning_engine = _build()  # default: all flags OFF
        try:
            await coord.initialize()
            await bus.publish(
                "VULN_CONFIRMED",
                {"vuln_type": "XSS", "url": "https://t.local/"},
                scan_id="off-1",
            )
            learning_engine.learn_from_browser_vulnerability.assert_not_awaited()
            assert coord.get_integration_metrics()["events_skipped"] >= 1
        finally:
            await coord.shutdown()

    async def test_vulnerability_routed_when_browser_learning_on(self) -> None:
        coord, bus, learning_engine = _build(
            _make_config(enable_browser_learning=True)
        )
        try:
            await coord.initialize()
            payload = {"vuln_type": "SQLi", "url": "https://t.local/api"}
            await bus.publish("VULN_CONFIRMED", payload, scan_id="on-1")
            learning_engine.learn_from_browser_vulnerability.assert_awaited_once()
            args, _ = learning_engine.learn_from_browser_vulnerability.call_args
            assert args[0] == payload
            assert args[1] == "on-1"
            assert coord.get_integration_metrics()["events_processed"] == 1
        finally:
            await coord.shutdown()

    async def test_failure_event_skipped_when_cross_healing_off(self) -> None:
        coord, bus, _ = _build()
        try:
            await coord.initialize()
            await bus.publish("AGENT_FAILURE", {"reason": "crash"}, scan_id="f")
            assert coord.get_integration_metrics()["events_skipped"] >= 1
        finally:
            await coord.shutdown()

    async def test_failure_event_processed_when_cross_healing_on(self) -> None:
        coord, bus, _ = _build(_make_config(enable_cross_system_healing=True))
        try:
            await coord.initialize()
            await bus.publish("AGENT_FAILURE", {"reason": "crash"}, scan_id="f")
            assert coord.get_integration_metrics()["events_processed"] == 1
        finally:
            await coord.shutdown()


# ---------------------------------------------------------------------------
# 1.6.c — Circuit breaker
# ---------------------------------------------------------------------------
class TestCircuitBreaker:
    """The local breaker trips after N consecutive learn failures."""

    async def test_breaker_trips_after_threshold_consecutive_failures(self) -> None:
        coord, bus, learning_engine = _build(
            _make_config(
                enable_browser_learning=True,
                circuit_breaker_threshold=3,
            )
        )
        learning_engine.learn_from_browser_vulnerability = AsyncMock(
            side_effect=RuntimeError("synthetic")
        )
        try:
            await coord.initialize()
            # Drive 3 failures to trip the breaker.
            for i in range(3):
                await bus.publish(
                    "VULN_CONFIRMED",
                    {"vuln_type": "XSS", "url": f"https://t.local/{i}"},
                    scan_id=f"cb-{i}",
                )
            assert coord._cb_vuln.trips == 1
            metrics_after_trip = coord.get_integration_metrics()
            assert metrics_after_trip["events_failed"] == 3
            assert metrics_after_trip["circuit_breaker_trips"] >= 1

            # 4th call: breaker is OPEN → coordinator should skip silently.
            calls_before = (
                learning_engine.learn_from_browser_vulnerability.await_count
            )
            await bus.publish(
                "VULN_CONFIRMED",
                {"vuln_type": "XSS", "url": "https://t.local/skipped"},
                scan_id="cb-skip",
            )
            calls_after = (
                learning_engine.learn_from_browser_vulnerability.await_count
            )
            assert calls_after == calls_before  # blocked by open circuit
            assert coord.get_integration_metrics()["events_skipped"] >= 1
        finally:
            await coord.shutdown()

    async def test_local_circuit_breaker_resets_on_success(self) -> None:
        breaker = _LocalCircuitBreaker(name="t", failure_threshold=3, recovery_timeout=60)
        # Two failures, then a success: counter must reset to zero.
        for _ in range(2):
            with pytest.raises(RuntimeError):
                await breaker.call(lambda: _raise(RuntimeError("boom")))
        await breaker.call(lambda: _ok("yay"))
        assert breaker._failures == 0
        assert breaker.trips == 0


async def _raise(exc: BaseException) -> None:
    raise exc


async def _ok(value: Any) -> Any:
    return value


# ---------------------------------------------------------------------------
# 1.6.d — Batch processing
# ---------------------------------------------------------------------------
class TestBatchProcessing:
    """Discovery events are buffered and flushed by size or timeout."""

    async def test_discovery_batch_flushes_on_size_threshold(self) -> None:
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
            # Three items hit the size threshold → flush triggered synchronously.
            assert (
                learning_engine.learn_framework_pattern.await_count == 3
            )
            metrics = coord.get_integration_metrics()
            assert metrics["batches_flushed"] == 1
            assert metrics["last_batch_size"] == 3
            assert metrics["pending_discoveries"] == 0
        finally:
            await coord.shutdown()

    async def test_discovery_batch_flushes_on_timeout(self) -> None:
        coord, bus, learning_engine = _build(
            _make_config(
                enable_browser_learning=True,
                event_batch_size=100,         # never hit by size
                event_batch_timeout_ms=50,    # fast timeout
            )
        )
        try:
            await coord.initialize()
            await bus.publish(
                "BROWSER_DISCOVERY",
                {"framework": "Vue", "routes": ["/x"]},
                scan_id="b-time",
            )
            # Wait for the drainer to fire at least once.
            await asyncio.sleep(0.2)
            assert learning_engine.learn_framework_pattern.await_count == 1
            assert coord.get_integration_metrics()["batches_flushed"] >= 1
        finally:
            await coord.shutdown()

    async def test_discovery_skipped_when_browser_learning_off(self) -> None:
        coord, bus, learning_engine = _build()  # default OFF
        try:
            await coord.initialize()
            await bus.publish(
                "BROWSER_DISCOVERY",
                {"framework": "Angular", "routes": ["/a"]},
                scan_id="b-off",
            )
            # No flush should happen — buffer must remain empty too.
            await asyncio.sleep(0.1)
            learning_engine.learn_framework_pattern.assert_not_awaited()
        finally:
            await coord.shutdown()

    async def test_shutdown_flushes_remaining_batch(self) -> None:
        coord, bus, learning_engine = _build(
            _make_config(
                enable_browser_learning=True,
                event_batch_size=10,
                event_batch_timeout_ms=10_000,
            )
        )
        await coord.initialize()
        await bus.publish(
            "BROWSER_DISCOVERY",
            {"framework": "Svelte", "routes": ["/s"]},
            scan_id="b-shut",
        )
        # Buffer holds 1 item < size threshold; shutdown must flush it.
        await coord.shutdown()
        assert learning_engine.learn_framework_pattern.await_count == 1
