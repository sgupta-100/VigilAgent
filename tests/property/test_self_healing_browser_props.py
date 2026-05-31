"""Property tests for browser self-healing (deep-system-integration §9.x).

Covers tasks 9.2 / 9.4 / 9.6 / 9.8 — Properties 6, 7/17, 8, 9.

§11 (no LLMs), §17 (no vuln-confirmation here), §29.13 (no wall-clock sleeps —
backoff/recovery windows are simulated via timestamp mutation).
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from backend.core.recovery_engine import (
    BrowserSelfHealingExtension,
    SelfHealingEngine,
)

pytestmark = pytest.mark.asyncio


def _fresh_browser_healing() -> BrowserSelfHealingExtension:
    """Fresh healing pair so per-agent restart_count state never leaks."""
    return BrowserSelfHealingExtension(SelfHealingEngine(brain_dir="brain"))


def _orchestrator_mock() -> MagicMock:
    """BrowserOrchestrator double exposing the surface heal_* introspect."""
    orch = MagicMock(name="BrowserOrchestrator")
    orch.restart_context = AsyncMock(return_value=True)
    orch.restore_session = AsyncMock(return_value=True)
    orch.close_idle_contexts = AsyncMock(return_value=3)
    orch.clear_context_pool = AsyncMock(return_value=None)
    return orch


def _stub_browser_health(monkeypatch) -> None:
    """heal_browser_crash reads browser_health_monitor.get_browser_health
    before doing anything; return non-None so it proceeds."""
    from backend.core import agent_health_monitor as ahm
    mock_bhm = MagicMock()
    mock_bhm.get_browser_health.return_value = {"health_score": 10}
    monkeypatch.setattr(ahm, "browser_health_monitor", mock_bhm)


# ===========================================================================
# Task 9.2 — Browser Crash Detection and Recovery
# ===========================================================================
class TestBrowserCrashRecovery:
    """Property 6 — heal_browser_crash restarts and applies exponential backoff.

    Validates: Requirements 3.1, 3.2, 3.5
    """

    async def test_crash_recovery_restarts_context(self, monkeypatch) -> None:
        """**Property 6**: a crash heal restarts context, restores session,
        bumps restart_count, and records a recovery entry.

        **Validates: Requirements 3.1, 3.2, 3.5**
        """
        agent = "omega"
        healing = _fresh_browser_healing()
        orch = _orchestrator_mock()
        _stub_browser_health(monkeypatch)

        ok = await healing.heal_browser_crash(agent, orch)

        assert ok is True
        assert healing.browser_restart_counts[agent] == 1
        orch.restart_context.assert_awaited_once_with(agent)
        orch.restore_session.assert_awaited_once_with(agent)
        assert any(
            r.action_type == "browser_restart" and r.agent_name == agent
            for r in healing.engine.recovery_history
        )

    async def test_exponential_backoff_blocks_rapid_restarts(self, monkeypatch) -> None:
        """**Property 6 (backoff)**: a second heal inside the per-attempt
        backoff window must NOT issue a new restart_context call. Backoff
        delays are [5,10,30,60,300]s for attempts 0..4.

        **Validates: Requirements 3.5**
        """
        agent = "omega-2"
        healing = _fresh_browser_healing()
        orch = _orchestrator_mock()
        _stub_browser_health(monkeypatch)

        first = await healing.heal_browser_crash(agent, orch)
        assert first is True
        # Force "now" to be just after the last restart so the second attempt
        # is inside the 10s window (attempt index 1).
        healing.last_browser_restart[agent] = time.time()
        orch.restart_context.reset_mock()
        orch.restore_session.reset_mock()

        second = await healing.heal_browser_crash(agent, orch)

        assert second is False
        orch.restart_context.assert_not_called()
        orch.restore_session.assert_not_called()
        assert healing.browser_restart_counts[agent] == 1


# ===========================================================================
# Task 9.4 — Browser Memory Management
# ===========================================================================
class TestBrowserMemoryHealing:
    """Property 7 / 17 — heal_browser_memory closes idle contexts.

    Validates: Requirements 3.3, 5.3
    """

    @given(idle_count=st.integers(min_value=0, max_value=50))
    @settings(max_examples=20, deadline=None,
              suppress_health_check=[HealthCheck.function_scoped_fixture,
                                     HealthCheck.too_slow])
    async def test_memory_management_closes_idle_contexts(self, idle_count: int) -> None:
        """**Property 7 / 17**: regardless of how many idle contexts exist,
        heal_browser_memory closes them, clears the pool, and returns True.

        **Validates: Requirements 3.3, 5.3**
        """
        agent = "omega"
        healing = _fresh_browser_healing()
        orch = _orchestrator_mock()
        orch.close_idle_contexts = AsyncMock(return_value=idle_count)

        ok = await healing.heal_browser_memory(agent, orch)

        assert ok is True
        orch.close_idle_contexts.assert_awaited_once_with(agent)
        orch.clear_context_pool.assert_awaited_once_with(agent)
        assert any(
            r.action_type == "memory_cleanup" and r.agent_name == agent
            for r in healing.engine.recovery_history
        )


# ===========================================================================
# Task 9.6 — Browser Strategy Adaptation
# ===========================================================================
class TestBrowserStrategyAdaptation:
    """Property 8 — repeated failures push strategy through stealth → reduced
    concurrency → HTTP fallback.

    Validates: Requirements 3.4
    """

    @given(reason=st.sampled_from(
        ["high_error_rate", "rate_limited", "waf_detected", "repeated_failures"]
    ))
    @settings(max_examples=20, deadline=None,
              suppress_health_check=[HealthCheck.function_scoped_fixture,
                                     HealthCheck.too_slow])
    async def test_strategy_adaptation_falls_back(self, reason: str) -> None:
        """**Property 8**: every documented failure reason yields the §9.5
        contract — stealth+concurrency=1 for traffic signals, HTTP fallback
        for WAF / repeated failures.

        **Validates: Requirements 3.4**
        """
        agent = "omega"
        healing = _fresh_browser_healing()

        strategy = await healing.adapt_browser_strategy(agent, reason)

        assert {"mode", "concurrency", "fallback_to_http"} <= set(strategy.keys())
        if reason in ("high_error_rate", "rate_limited"):
            assert strategy["mode"] == "stealth"
            assert strategy["concurrency"] == 1
        if reason in ("waf_detected", "repeated_failures"):
            assert strategy["fallback_to_http"] is True
        assert any(
            r.action_type == "browser_strategy_change" and r.agent_name == agent
            for r in healing.engine.recovery_history
        )


# ===========================================================================
# Task 9.8 — Browser Circuit Breaker
# ===========================================================================
class TestBrowserCircuitBreaker:
    """Property 9 — circuit opens after threshold and recovers later.

    Validates: Requirements 3.6
    """

    @given(failures=st.integers(min_value=5, max_value=20))
    @settings(max_examples=20, deadline=None,
              suppress_health_check=[HealthCheck.function_scoped_fixture,
                                     HealthCheck.too_slow])
    async def test_circuit_breaker_opens_after_threshold(self, failures: int) -> None:
        """**Property 9 (open)**: after N >= 5 consecutive failures the breaker
        is OPEN and rejects requests; after the 30s recovery window it
        half-opens and lets the next probe through.

        **Validates: Requirements 3.6**
        """
        target = "https://victim.test/api"
        healing = _fresh_browser_healing()

        for _ in range(failures):
            healing.record_browser_result(target, success=False)

        cb_status = healing.get_browser_circuit_breaker(target)
        assert cb_status is not None
        assert cb_status["state"] == "open"
        assert healing.check_browser_circuit_breaker(target) is False

        # Simulate 31s elapsed via timestamp mutation (§29.13: no real sleep).
        breaker = healing.engine.circuit_breakers[f"browser:{target}"]
        breaker.opened_at = time.time() - 31.0
        assert healing.check_browser_circuit_breaker(target) is True
        assert breaker.state == "half_open"

    async def test_circuit_breaker_closes_after_consecutive_success(self) -> None:
        """**Property 9 (close)**: in half-open, three consecutive successes
        close the breaker and reset the failure counter.

        **Validates: Requirements 3.6**
        """
        target = "https://recovers.test/"
        healing = _fresh_browser_healing()
        for _ in range(5):
            healing.record_browser_result(target, success=False)

        breaker = healing.engine.circuit_breakers[f"browser:{target}"]
        breaker.state = "half_open"
        breaker.success_count = 0

        for _ in range(3):
            healing.record_browser_result(target, success=True)

        assert breaker.state == "closed"
        assert breaker.failure_count == 0
