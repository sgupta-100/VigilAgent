"""Chaos test for IntegrationCoordinator (deep-system-integration §9.9).

100 VULN_CONFIRMED events with a 50% LearningEngine failure rate. Coordinator
must absorb failures without crashing: every event accounted for, aggregate
failure rate < 0.6, circuit breaker trips at least once.

§11 (no LLMs), §17 (no vuln-confirmation; only routing), §29.13 (chaos via
AsyncMock side_effect, never wall-clock sleeps).
"""

from __future__ import annotations

import asyncio
import random
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.core.integration_config import IntegrationConfig
from backend.core.integration_coordinator import IntegrationCoordinator

pytestmark = pytest.mark.asyncio


class _FakeBus:
    """In-memory pub/sub matching the surface IntegrationCoordinator subscribes to."""

    def __init__(self) -> None:
        self.handlers: Dict[str, List[Any]] = {}

    async def subscribe(self, event_type: str, handler) -> None:
        self.handlers.setdefault(event_type, []).append(handler)

    async def publish(self, event_type: str, data: Dict[str, Any], **kw) -> None:
        scan_id = kw.get("scan_id", "chaos-scan")
        for h in self.handlers.get(event_type, []):
            await h({"data": data, "scan_id": scan_id})


def _config(threshold: int) -> IntegrationConfig:
    return IntegrationConfig(
        enable_browser_learning=True,
        enable_cross_system_healing=False,
        enable_forensic_learning=False,
        enable_intelligent_routing=False,
        event_batch_size=10,
        event_batch_timeout_ms=50,
        max_concurrent_learning=4,
        circuit_breaker_threshold=threshold,
        circuit_breaker_timeout_s=300,  # long → breaker stays OPEN once tripped
    )


def _vuln(i: int) -> Dict[str, Any]:
    return {
        "vuln_type": "xss",
        "url": f"https://target.test/page-{i}",
        "evidence": {"reflection": True, "executed": True},
    }


class TestCoordinatorChaosResilience:
    """Chaos: 50% LearningEngine failures + 100 VULN_CONFIRMED events.

    Validates: Resilience (deep-system-integration §9.9)
    """

    async def test_coordinator_survives_50_percent_learning_failure(self) -> None:
        """**Chaos**: 100 VULN_CONFIRMED events with half of LearningEngine
        calls raising RuntimeError. Coordinator must (1) account for every
        event, (2) keep failure_rate < 0.6, (3) trip the breaker at least once.

        **Validates: Resilience**
        """
        # Threshold low enough that with 50% failures over 100 events the
        # breaker is mathematically certain to trip at least once.
        config = _config(threshold=3)

        rng = random.Random(0xC0FFEE)  # deterministic chaos
        n = {"v": 0}

        async def flaky_learn(vuln_data: Dict[str, Any], scan_id: str) -> bool:
            n["v"] += 1
            if rng.random() < 0.5:
                raise RuntimeError(f"Injected chaos failure on call #{n['v']}")
            return True

        learning_engine = MagicMock(name="LearningEngine")
        learning_engine.learn_from_browser_vulnerability = AsyncMock(side_effect=flaky_learn)
        learning_engine.learn_framework_pattern = AsyncMock(return_value=True)

        bus = _FakeBus()
        coord = IntegrationCoordinator(
            bus=bus,
            learning_engine=learning_engine,
            skill_library=MagicMock(name="SkillLibrary"),
            health_monitor=MagicMock(name="HealthMonitor"),
            healing_engine=MagicMock(name="HealingEngine"),
            browser_orchestrator=MagicMock(name="BrowserOrchestrator"),
            config=config,
        )

        try:
            await coord.initialize()
            for i in range(100):
                await bus.publish("VULN_CONFIRMED", _vuln(i), scan_id=f"chaos-scan-{i}")
            await asyncio.sleep(0)  # let pending coroutines settle
        finally:
            await coord.shutdown()

        metrics = coord.get_integration_metrics()
        processed = metrics["events_processed"]
        failed = metrics["events_failed"]
        skipped = metrics["events_skipped"]

        # 1. Every event accounted for.
        total = processed + failed + skipped
        assert total == 100, (
            f"events not fully accounted for: processed={processed} "
            f"failed={failed} skipped={skipped} total={total}"
        )

        # 2. Graceful degradation — skipped events from breaker-OPEN mask a
        #    portion of failures so the reported rate stays below 0.6.
        assert metrics["failure_rate"] < 0.6, (
            f"failure_rate too high: {metrics['failure_rate']:.3f} "
            f"(processed={processed}, failed={failed})"
        )

        # 3. Circuit breaker tripped at least once.
        assert metrics["circuit_breaker_trips"] >= 1
        assert coord._cb_vuln.trips >= 1
