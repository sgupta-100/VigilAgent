"""
E2E / Chaos — deep-system-integration task 15.4 (event storm).

Push 1000 ``BROWSER_DISCOVERY`` events through ``_on_discovery`` rapidly and
verify:

  * No exception escapes the coordinator (it absorbs the storm).
  * ``metrics.batches_flushed > 0`` (event batching actually fired —
    the storm wasn't processed one-by-one, defeating the design).
  * ``metrics.events_failed == 0`` (the in-memory learning engine has no
    reason to fail; failures here would mean the coordinator's plumbing
    leaked an exception out of the gather()).

Architecture invariants honoured:
  * §29.13 non-blocking — the coordinator buffers under an asyncio.Lock and
    drains in a background task; no blocking I/O.
  * §11 two-LLM exclusivity — no LLM bindings touched.
  * §17 ≥2-signal evidence — discovery events are pre-confirmation by
    construction; no synthetic vulnerabilities are placed on the bus.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List

import pytest

from backend.core.integration_coordinator import IntegrationCoordinator

from tests.e2e.conftest import (
    FakeBus,
    InMemoryLearningEngine,
    InMemorySkillLibrary,
    make_e2e_config,
)
from unittest.mock import AsyncMock, MagicMock


pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Storm parameters
# ---------------------------------------------------------------------------
STORM_SIZE = 1000
BATCH_SIZE = 50  # the coordinator's flush threshold for this test


def _make_discovery(i: int) -> Dict[str, Any]:
    """Generate a tiny BROWSER_DISCOVERY-shaped payload."""
    framework = ("React", "Vue", "Angular", "Svelte", "Next")[i % 5]
    # Routes are a small slice; we don't need a huge payload to stress batching.
    routes = [f"/storm/{i}/a", f"/storm/{i}/b"]
    return {"framework": framework, "routes": routes}


# ---------------------------------------------------------------------------
# 15.4 — event storm
# ---------------------------------------------------------------------------
async def test_event_storm_1000_discoveries_does_not_crash():
    """1000 BROWSER_DISCOVERY events absorbed without exception or failure."""
    bus = FakeBus()
    learning_engine = InMemoryLearningEngine()
    skill_library = InMemorySkillLibrary()
    health_monitor = MagicMock(name="HealthMonitor")
    healing_engine = MagicMock(name="RecoveryEngine")
    healing_engine.heal_browser_crash = AsyncMock(return_value=True)
    browser_orchestrator = MagicMock(name="BrowserOrchestrator")

    coord = IntegrationCoordinator(
        bus=bus,
        learning_engine=learning_engine,
        skill_library=skill_library,
        health_monitor=health_monitor,
        healing_engine=healing_engine,
        browser_orchestrator=browser_orchestrator,
        config=make_e2e_config(
            event_batch_size=BATCH_SIZE,
            event_batch_timeout_ms=50,
        ),
    )
    await coord.initialize()

    try:
        # Fire the storm — call _on_discovery directly (the spec phrasing) AND
        # also exercise a few via the bus to prove the subscription path works
        # end-to-end. The directly-driven loop is the bulk of the storm so
        # we can be deterministic about timing.
        tasks: List[asyncio.Task] = []
        for i in range(STORM_SIZE):
            event = {"data": _make_discovery(i), "scan_id": "storm"}
            # No await/gather here — we want them queued as fast as possible
            # to genuinely race for the batch lock (chaos intent).
            tasks.append(asyncio.create_task(coord._on_discovery(event)))

        # Drain the dispatch wave. Anything that raises here would fail the
        # test: a crashing coordinator would surface the exception via gather.
        await asyncio.gather(*tasks)

        # Allow the background drain task to flush whatever didn't hit the
        # in-handler size threshold. Sleep just a touch longer than the
        # batch timeout so we get at least one drainer tick.
        await asyncio.sleep(0.25)

        # Force a final flush of any tail < BATCH_SIZE so events_processed
        # reaches STORM_SIZE deterministically.
        async with coord._batch_lock:
            await coord._flush_discovery_batch_locked()

        metrics = coord.get_integration_metrics()

        # --- Primary spec assertions --------------------------------------
        assert metrics["events_failed"] == 0, (
            f"event storm produced failures: {metrics}"
        )
        assert metrics["batches_flushed"] > 0, (
            f"batching never fired during storm: {metrics}"
        )

        # --- Secondary correctness assertions -----------------------------
        # The coordinator should have processed every queued event (each
        # flushed batch increments events_processed by len(batch)).
        assert metrics["events_processed"] >= STORM_SIZE, (
            f"expected ≥{STORM_SIZE} processed, got {metrics['events_processed']}"
        )
        # And no events should be left buffered after the explicit final flush.
        assert metrics["pending_discoveries"] == 0

        # The in-memory learning engine should have received exactly one
        # learn_framework_pattern call per event (since we drove STORM_SIZE
        # events and there's no dedup at this layer).
        assert len(learning_engine.framework_patterns) == STORM_SIZE
    finally:
        await coord.shutdown()


async def test_event_storm_via_bus_subscribe_path_also_safe():
    """Smaller storm through the actual bus.publish path — proves subscription works under load."""
    bus = FakeBus()
    learning_engine = InMemoryLearningEngine()
    healing_engine = MagicMock(name="RecoveryEngine")
    healing_engine.heal_browser_crash = AsyncMock(return_value=True)

    coord = IntegrationCoordinator(
        bus=bus,
        learning_engine=learning_engine,
        skill_library=MagicMock(name="SkillLibrary"),
        health_monitor=MagicMock(name="HealthMonitor"),
        healing_engine=healing_engine,
        browser_orchestrator=MagicMock(name="BrowserOrchestrator"),
        config=make_e2e_config(event_batch_size=20, event_batch_timeout_ms=50),
    )
    await coord.initialize()

    try:
        N = 200
        for i in range(N):
            await bus.publish("BROWSER_DISCOVERY", _make_discovery(i), scan_id="bus-storm")

        # Let the drainer tick.
        await asyncio.sleep(0.2)
        async with coord._batch_lock:
            await coord._flush_discovery_batch_locked()

        metrics = coord.get_integration_metrics()
        assert metrics["events_failed"] == 0
        assert metrics["batches_flushed"] > 0
        assert metrics["events_processed"] >= N
    finally:
        await coord.shutdown()
