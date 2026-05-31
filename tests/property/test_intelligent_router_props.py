"""Property-based tests for ``backend.core.intelligent_router.IntelligentRouter``.

Covers spec ``deep-system-integration`` tasks 13.3 (method recommendation)
and 13.5 (engine selection).

Architecture invariants honoured:
  §9   scope-is-law       — targets are advisory dicts; nothing here grants
                            scope.
  §11  two-LLM exclusivity — router decisions are pure rules + learned
                            patterns; no LLM calls in the test path.
  §17  ≥2-signal advisory — recommendations are not findings; tests assert
                            decision shape only.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict
from unittest.mock import AsyncMock

import pytest

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import HealthCheck, given, settings, strategies as st

from backend.core.intelligent_router import (
    ENGINE_OPENCLAW,
    ENGINE_PINCHTAB,
    METHOD_BROWSER_ONLY,
    METHOD_HTTP_ONLY,
    METHOD_HYBRID,
    IntelligentRouter,
)


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------
class _FakePattern:
    """Stand-in for ``LearningPattern`` exposing only the attributes the
    router reads in ``_lookup_learned_method``. Avoids importing the
    learning_engine module (and its heavy deps) into the test path.
    """

    def __init__(
        self,
        pattern_data: Dict[str, Any],
        success_count: int,
        failure_count: int = 0,
        pattern_type: str = "method_effectiveness",
    ) -> None:
        self.pattern_type = pattern_type
        self.pattern_data = pattern_data
        self.success_count = success_count
        self.failure_count = failure_count

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0


def _engine_with_patterns(patterns: Dict[str, _FakePattern]) -> SimpleNamespace:
    """Build a learning_engine stub with a patterns dict + AsyncMock saver."""
    return SimpleNamespace(
        patterns=patterns,
        _save_patterns=AsyncMock(return_value=None),
    )


# ---------------------------------------------------------------------------
# Property 59 — Method Recommendation Based on Patterns  (Task 13.3)
# ---------------------------------------------------------------------------
class TestRecommendMethodMatchesLearnedPatterns:
    """**Validates: Requirements 17.2, 17.5**

    Property 59 — when a learned ``method_effectiveness`` pattern exists for
    a target characteristic triple with ``success_rate ≥ 0.7`` AND
    ``success_count ≥ 3``, ``recommend_method`` returns that pattern's
    method, overriding the static rules.
    """

    @settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    @given(
        framework=st.sampled_from(["react", "vue", "angular", "django"]),
        has_js=st.booleans(),
        content_type_class=st.sampled_from(["browser", "http", "other"]),
        seeded_method=st.sampled_from([METHOD_HTTP_ONLY, METHOD_BROWSER_ONLY, METHOD_HYBRID]),
        observations=st.integers(min_value=3, max_value=20),
    )
    def test_learned_pattern_overrides_rules(
        self,
        framework: str,
        has_js: bool,
        content_type_class: str,
        seeded_method: str,
        observations: int,
    ) -> None:
        # Seed exactly one effective pattern for the triple.
        patterns: Dict[str, _FakePattern] = {
            "method_effectiveness_seed": _FakePattern(
                pattern_data={
                    "framework": framework,
                    "has_js": has_js,
                    "content_type_class": content_type_class,
                    "method": seeded_method,
                },
                # success_rate is success_count / (success+failure) = 1.0 here
                # which clears the ≥0.7 threshold; observations >= 3 clears
                # the success_count gate.
                success_count=observations,
                failure_count=0,
            ),
        }
        learning_engine = _engine_with_patterns(patterns)
        router = IntelligentRouter(learning_engine=learning_engine, browser_orchestrator=AsyncMock())

        # Build a target whose extracted characteristics produce the same
        # triple. Content-Type tokens are mapped by the router.
        ct_token_by_class = {
            "browser": "text/html",
            "http": "application/json",
            "other": "application/octet-stream",
        }
        target = {
            "framework": framework,
            "has_js": has_js,
            "no_js": not has_js,
            "content_type": ct_token_by_class[content_type_class],
        }

        result = router.recommend_method(target)
        assert result == seeded_method, (
            f"learned override failed: triple=({framework},{has_js},{content_type_class}) "
            f"seeded={seeded_method!r} got={result!r}"
        )

    @settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    @given(observations=st.integers(min_value=0, max_value=2))
    def test_low_evidence_does_not_override_rules(self, observations: int) -> None:
        # Below the 3-observation gate, the router must fall through to
        # rule-based logic. Use a pure HTTP target so the rule answer is
        # unambiguous: no_js=True → http_only.
        patterns: Dict[str, _FakePattern] = {
            "method_effectiveness_seed": _FakePattern(
                pattern_data={
                    "framework": "",
                    "has_js": False,
                    "content_type_class": "other",
                    "method": METHOD_BROWSER_ONLY,  # would mislead if honoured
                },
                success_count=observations,
                failure_count=0,
            ),
        }
        learning_engine = _engine_with_patterns(patterns)
        router = IntelligentRouter(learning_engine=learning_engine)

        result = router.recommend_method({"no_js": True})
        assert result == METHOD_HTTP_ONLY


# ---------------------------------------------------------------------------
# Property 60 — Complexity-Based Engine Selection  (Task 13.5)
# ---------------------------------------------------------------------------
class TestComplexityBasedEngineSelection:
    """**Validates: Requirements 17.3**

    Property 60 — simple tasks (low complexity, no stealth, single step)
    select PinchTab; tasks crossing any of (complexity ≥ 3, stealth flag,
    multi-step) select OpenClaw.
    """

    @settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    @given(complexity=st.integers(min_value=0, max_value=2))
    def test_simple_tasks_select_pinchtab(self, complexity: int) -> None:
        router = IntelligentRouter(browser_orchestrator=AsyncMock())
        task = {"action": "navigate", "complexity": complexity}
        assert router.select_browser_engine(task) == ENGINE_PINCHTAB

    @settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    @given(complexity=st.integers(min_value=3, max_value=10))
    def test_high_complexity_selects_openclaw(self, complexity: int) -> None:
        router = IntelligentRouter(browser_orchestrator=AsyncMock())
        assert router.select_browser_engine({"complexity": complexity}) == ENGINE_OPENCLAW

    @settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    @given(stealth_flag=st.sampled_from(["stealth", "stealth_required"]))
    def test_stealth_always_selects_openclaw(self, stealth_flag: str) -> None:
        router = IntelligentRouter(browser_orchestrator=AsyncMock())
        # complexity is low, but stealth must still force OpenClaw.
        task = {"action": "navigate", "complexity": 0, stealth_flag: True}
        assert router.select_browser_engine(task) == ENGINE_OPENCLAW

    @settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    @given(step_count=st.integers(min_value=2, max_value=8))
    def test_multi_step_selects_openclaw(self, step_count: int) -> None:
        router = IntelligentRouter(browser_orchestrator=AsyncMock())
        task = {"steps": [{"a": i} for i in range(step_count)], "complexity": 0}
        assert router.select_browser_engine(task) == ENGINE_OPENCLAW
