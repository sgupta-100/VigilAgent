"""
Shared async fixtures for the deep-system-integration E2E suite (tasks 15.1–15.4).

Every external dependency is replaced with an in-memory fake or
``unittest.mock.AsyncMock`` so the suite runs offline:

  * No real DVWA / target server.
  * No real browser (``browser_orchestrator`` is a MagicMock).
  * No Redis, Postgres, or Cortex/LLM bindings.

Architecture invariants honoured:
  * §29.13 non-blocking — every collaborator is async and returns immediately.
  * §11 two-LLM exclusivity — no LLM calls; Cortex paths are mocked when used.
  * §17 ≥2-signal evidence — tests assert routing only; they never fabricate
    confirmations on the bus from inside the coordinator.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Tuple
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.core.integration_config import IntegrationConfig
from backend.core.integration_coordinator import IntegrationCoordinator


# ---------------------------------------------------------------------------
# In-memory event bus — matches the surface IntegrationCoordinator subscribes to.
# ---------------------------------------------------------------------------
class FakeBus:
    """Tiny pub/sub used by the E2E suite.

    The real ``EventBus`` is a richer surface (HiveEvent dispatch, telemetry,
    websocket fan-out, …). For E2E routing assertions we only need the two
    methods the coordinator actually calls: ``subscribe`` + ``publish``.
    Handlers receive a dict ``{"data": <payload>, "scan_id": <str>}`` so the
    coordinator's ``_event_data`` / ``_event_scan_id`` helpers light up
    exactly the same way they do in production.
    """

    def __init__(self) -> None:
        self.handlers: Dict[str, List[Any]] = {}
        self.published: List[Tuple[str, Dict[str, Any], str]] = []

    async def subscribe(self, event_type: str, handler) -> None:
        self.handlers.setdefault(event_type, []).append(handler)

    async def publish(self, event_type: str, data: Dict[str, Any], **kw) -> None:
        scan_id = kw.get("scan_id", "e2e")
        self.published.append((event_type, data, scan_id))
        for h in self.handlers.get(event_type, []):
            await h({"data": data, "scan_id": scan_id})


# ---------------------------------------------------------------------------
# In-memory learning engine — tracks vulnerabilities, workflows and patterns
# without touching disk. Mirrors the contract IntegrationCoordinator depends on
# (see backend/core/learning_engine.py docstrings on `learn_from_browser_*`).
# ---------------------------------------------------------------------------
class InMemoryLearningEngine:
    """Stub LearningEngine that just records what it was asked to learn.

    Surface intentionally narrow: only the three methods the coordinator and
    the cross-system bridge call. Everything is async to satisfy §29.13.
    """

    def __init__(self) -> None:
        self.vulns_learned: List[Tuple[Dict[str, Any], str]] = []
        self.workflows_learned: List[Tuple[Dict[str, Any], str]] = []
        self.framework_patterns: List[Tuple[str, List[str]]] = []
        # Hybrid skills synthesized when an HTTP+browser pair is seen on the
        # same URL (used by the cross-system-learning E2E test, 15.3).
        self.hybrid_skills: List[Dict[str, Any]] = []

    async def learn_from_browser_vulnerability(
        self, vuln_data: Dict[str, Any], scan_id: str
    ) -> bool:
        self.vulns_learned.append((vuln_data, scan_id))
        return True

    async def learn_browser_workflow(
        self, workflow: Dict[str, Any], scan_id: str
    ) -> bool:
        self.workflows_learned.append((workflow, scan_id))
        return True

    async def learn_framework_pattern(
        self, framework: Any, routes: List[str]
    ) -> bool:
        # Coordinator forwards whatever the discovery event carried; framework
        # may be None / "" — we accept gracefully (see learning_engine.py
        # `learn_framework_pattern` graceful no-op contract).
        self.framework_patterns.append((framework, list(routes or [])))
        return True

    def synthesize_hybrid_skill(
        self, http_vuln: Dict[str, Any], browser_vuln: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compose a hybrid skill from an HTTP-shape vuln and a browser-shape
        vuln on the same URL (task 15.3 helper). Pure in-memory stub; the real
        composition logic lives in ``BrowserSkillLibraryExtension.compose_workflows``.
        """
        skill = {
            "id": f"hybrid::{http_vuln.get('url')}",
            "name": "Hybrid HTTP+Browser exploit",
            "execution_context": "hybrid",
            "http_signature": http_vuln,
            "browser_signature": browser_vuln,
            "tags": ("hybrid", "browser_automation", "http_origin"),
        }
        self.hybrid_skills.append(skill)
        return skill


# ---------------------------------------------------------------------------
# In-memory skill library — only the surface E2E tests need.
# ---------------------------------------------------------------------------
class InMemorySkillLibrary:
    """Records skills added during a scan; size used as a growth assertion."""

    def __init__(self) -> None:
        self.skills: List[Dict[str, Any]] = []

    async def add_browser_skill(self, skill: Dict[str, Any]) -> bool:
        self.skills.append(dict(skill))
        return True

    def __len__(self) -> int:
        return len(self.skills)


# ---------------------------------------------------------------------------
# Config helper
# ---------------------------------------------------------------------------
def make_e2e_config(**overrides: Any) -> IntegrationConfig:
    """Build an IntegrationConfig with all integration flags ON.

    Tight batch caps so discovery storms flush quickly without leaning on the
    sleep-based drainer. Concurrency cap is small but >1 so the semaphore is
    exercised in the storm test (15.4).
    """
    base: Dict[str, Any] = dict(
        enable_browser_learning=True,
        enable_cross_system_healing=True,
        enable_forensic_learning=True,
        enable_intelligent_routing=True,
        event_batch_size=50,           # storm test (15.4) needs multiple flushes
        event_batch_timeout_ms=50,
        max_concurrent_learning=4,
        circuit_breaker_threshold=10000,  # never trip during E2E
        circuit_breaker_timeout_s=60,
    )
    base.update(overrides)
    return IntegrationConfig(**base)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def fake_bus() -> FakeBus:
    """Fresh in-memory bus per test."""
    return FakeBus()


@pytest.fixture
def in_memory_learning_engine() -> InMemoryLearningEngine:
    """Fresh in-memory learning engine per test."""
    return InMemoryLearningEngine()


@pytest.fixture
def in_memory_skill_library() -> InMemorySkillLibrary:
    """Fresh in-memory skill library per test."""
    return InMemorySkillLibrary()


@pytest.fixture
def fake_browser_orchestrator() -> MagicMock:
    """MagicMock standing in for the real BrowserOrchestrator.

    All the methods the E2E suite exercises are async (§29.13).
    """
    bo = MagicMock(name="BrowserOrchestrator")
    bo.create_context = AsyncMock(return_value={"context_id": "ctx-fresh"})
    bo.close_context = AsyncMock(return_value=True)
    bo.restart_context = AsyncMock(return_value={"context_id": "ctx-fresh"})
    bo.get_active_contexts = MagicMock(return_value=[])
    return bo


@pytest.fixture
def fake_health_monitor() -> MagicMock:
    """HealthMonitor stub with the browser-health surface used in 15.x."""
    hm = MagicMock(name="HealthMonitor")
    hm.report_browser_metrics = MagicMock()
    hm.get_browser_health = MagicMock(
        return_value={
            "active_contexts": 0,
            "context_memory_mb": 0.0,
            "page_load_time_ms": 0,
            "browser_error_rate": 0.0,
            "health_score": 1.0,
        }
    )
    return hm


@pytest.fixture
def fake_recovery_engine() -> MagicMock:
    """RecoveryEngine stub returning a fresh context on heal_browser_crash."""
    re = MagicMock(name="RecoveryEngine")
    re.heal_browser_crash = AsyncMock(return_value={"recovered": True, "context_id": "ctx-fresh"})
    re.heal_browser_memory = AsyncMock(return_value=True)
    re.adapt_browser_strategy = AsyncMock()
    return re


@pytest.fixture
async def integrated_coordinator(
    fake_bus: FakeBus,
    in_memory_learning_engine: InMemoryLearningEngine,
    in_memory_skill_library: InMemorySkillLibrary,
    fake_health_monitor: MagicMock,
    fake_recovery_engine: MagicMock,
    fake_browser_orchestrator: MagicMock,
):
    """Yield a fully wired IntegrationCoordinator with auto-shutdown.

    Returns a tuple ``(coord, bus, learning_engine, skill_library,
    health_monitor, recovery_engine, browser_orchestrator)`` so every test can
    pull just the pieces it cares about.
    """
    coord = IntegrationCoordinator(
        bus=fake_bus,
        learning_engine=in_memory_learning_engine,
        skill_library=in_memory_skill_library,
        health_monitor=fake_health_monitor,
        healing_engine=fake_recovery_engine,
        browser_orchestrator=fake_browser_orchestrator,
        config=make_e2e_config(),
    )
    await coord.initialize()
    try:
        yield (
            coord,
            fake_bus,
            in_memory_learning_engine,
            in_memory_skill_library,
            fake_health_monitor,
            fake_recovery_engine,
            fake_browser_orchestrator,
        )
    finally:
        await coord.shutdown()


@pytest.fixture
def settle():
    """Helper that yields control so background drain tasks can tick.

    Use as: ``await settle(times=5)`` — sleeps ``times`` event-loop iterations.
    Plain (non-async) fixture returning an async callable: pytest-asyncio in
    auto mode hands the callable to the test without awaiting it.
    """

    async def _settle(times: int = 3, delay: float = 0.06) -> None:
        for _ in range(times):
            await asyncio.sleep(delay)

    return _settle
