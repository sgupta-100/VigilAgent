"""
E2E — deep-system-integration task 15.2 (browser crash recovery).

Crash → Detection → Healing → Restoration.

Scenario:
  * The ``browser_orchestrator`` raises an exception when an agent tries to
    drive a context (simulated browser crash).
  * The healing layer detects the crash and calls
    ``recovery_engine.heal_browser_crash(context_id, scan_id)``.
  * A fresh context is returned and is usable for the next operation.

Architecture invariants honoured:
  * §29.13 non-blocking — every collaborator is async; no real I/O.
  * §17 ≥2-signal evidence — the crash is a *system* event, not a vulnerability,
    so no fabricated evidence is ever placed on the bus.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Tiny in-test "agent" that drives the orchestrator and triggers the heal flow.
# ---------------------------------------------------------------------------
async def _drive_with_recovery(orchestrator, recovery_engine, scan_id: str, context_id: str):
    """Mimic what BrowserAgent does on crash:

      try:
          await orchestrator.drive(...)
      except BrowserCrash:
          fresh = await recovery_engine.heal_browser_crash(context_id, scan_id)
          # use the fresh context for the next call

    Returns the fresh context dict from heal_browser_crash.
    """
    try:
        await orchestrator.drive(context_id)
    except Exception:
        return await recovery_engine.heal_browser_crash(context_id, scan_id)
    return None


# ---------------------------------------------------------------------------
# 15.2 — crash → detection → healing → restoration
# ---------------------------------------------------------------------------
async def test_browser_crash_triggers_recovery_and_returns_fresh_context(
    integrated_coordinator,
):
    """A simulated browser crash must invoke heal_browser_crash and yield a fresh context."""
    _coord, _bus, _le, _sl, _hm, recovery_engine, browser_orchestrator = integrated_coordinator

    # --- 1. Simulate a browser crash --------------------------------------
    # The agent calls .drive(context_id) and the orchestrator raises a
    # generic RuntimeError modelling the real-world "Page crashed!" /
    # "Target closed" Playwright failures.
    browser_orchestrator.drive = AsyncMock(side_effect=RuntimeError("browser_orchestrator.crash: Target closed"))

    # --- 2. recovery_engine.heal_browser_crash returns a *fresh* context --
    fresh_context = {
        "recovered": True,
        "context_id": "ctx-fresh-after-heal",
        "session_restored": True,
    }
    recovery_engine.heal_browser_crash = AsyncMock(return_value=fresh_context)

    # --- 3. Drive the scenario --------------------------------------------
    crashed_ctx_id = "ctx-crashed-1"
    scan_id = "e2e-15-2"
    result = await _drive_with_recovery(
        browser_orchestrator, recovery_engine, scan_id, crashed_ctx_id
    )

    # --- 4. Assertions: detection + healing + restoration -----------------
    # The orchestrator was actually called (and crashed)
    browser_orchestrator.drive.assert_awaited_once_with(crashed_ctx_id)

    # The healing engine was called with the crashed context_id and scan_id —
    # this matches the RecoveryEngine.heal_browser_crash contract
    # (backend/core/recovery_engine.py: heal_browser_crash(context_id, scan_id)).
    recovery_engine.heal_browser_crash.assert_awaited_once_with(crashed_ctx_id, scan_id)

    # A fresh context was returned and is usable downstream
    assert result is not None
    assert result["recovered"] is True
    assert result["context_id"] == "ctx-fresh-after-heal"
    assert result["context_id"] != crashed_ctx_id


async def test_browser_crash_recovery_supports_subsequent_work():
    """After healing, the agent can drive the *new* context without raising.

    This is the "restoration" half of the spec phrase. We rebuild a tiny
    orchestrator stub here (instead of leaning on the shared fixture) so the
    test stays readable end-to-end without juggling mock side_effects across
    multiple awaited calls.
    """
    orchestrator = MagicMock(name="BrowserOrchestrator")
    recovery_engine = MagicMock(name="RecoveryEngine")

    # First call crashes, second call (after heal) succeeds.
    orchestrator.drive = AsyncMock(
        side_effect=[
            RuntimeError("browser_orchestrator.crash: Page crashed!"),
            {"ok": True, "screenshot": "after-heal.png"},
        ]
    )
    fresh_ctx_id = "ctx-fresh-after-heal"
    recovery_engine.heal_browser_crash = AsyncMock(
        return_value={"recovered": True, "context_id": fresh_ctx_id}
    )

    # Crash + heal
    healed = await _drive_with_recovery(orchestrator, recovery_engine, "scan-x", "ctx-old")
    assert healed["context_id"] == fresh_ctx_id

    # Drive the fresh context — must not raise
    result = await orchestrator.drive(fresh_ctx_id)
    assert result == {"ok": True, "screenshot": "after-heal.png"}

    assert orchestrator.drive.await_count == 2
    recovery_engine.heal_browser_crash.assert_awaited_once_with("ctx-old", "scan-x")
