"""Property tests for browser health monitoring (deep-system-integration §7.3 + 7.6).

Covers:
  * Task 7.3 — Property 15 (Browser Metric Tracking) + Property 21 (Universal
    Health Monitoring): every well-formed BrowserHealthMetrics report is stored
    verbatim, scored into [0, 1], and round-trips through ``get_browser_health``.
  * Task 7.6 — Property 22 (Browser Health Impact Alerts) + the §4.5 score
    formula: scores are deterministic / monotonic and the alert hook fires
    exactly when ``score < 0.4`` (the spec-fixed alert threshold).

Architecture invariants honoured:
  §11   two-LLM exclusivity   — no LLM imports.
  §17   ≥2-signal evidence    — health monitoring is observability only; it
                                 never confirms vulnerabilities, so the
                                 ≥2-signal gate is upstream and unaffected.
  §29.13 non-blocking         — pure-CPU scoring on the hot path; no I/O.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Optional

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from backend.core.agent_health_monitor import (
    AgentHealthMonitor,
    BrowserHealthMetrics,
    HealthAlert,
)


# ---------------------------------------------------------------------------
# Smart generators — constrain to the documented input domain so the §4.5
# formula doesn't get fed garbage that downstream code already clamps away.
# Hypothesis still explores boundary values because we use min/max on each
# field; keeping the domain realistic matches the §29.13 "no foot-guns".
# ---------------------------------------------------------------------------
_browser_metrics = st.builds(
    BrowserHealthMetrics,
    active_contexts=st.integers(min_value=0, max_value=200),
    context_memory_mb=st.floats(
        min_value=0.0, max_value=8192.0, allow_nan=False, allow_infinity=False
    ),
    page_load_time_ms=st.floats(
        min_value=0.0, max_value=20000.0, allow_nan=False, allow_infinity=False
    ),
    screenshot_time_ms=st.floats(
        min_value=0.0, max_value=10000.0, allow_nan=False, allow_infinity=False
    ),
    browser_error_rate=st.floats(
        min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False
    ),
    timestamp=st.floats(
        min_value=0.0, max_value=2_000_000_000.0, allow_nan=False, allow_infinity=False
    ),
)


def _fresh_monitor() -> AgentHealthMonitor:
    """Brand-new AgentHealthMonitor — never reuse the module-level singleton in
    property tests so prior runs / dedup state don't leak between examples."""
    return AgentHealthMonitor()


def _last_browser_alert(monitor: AgentHealthMonitor) -> Optional[HealthAlert]:
    """Return the most recent alert tagged with ``category='browser_health'``."""
    for alert in reversed(monitor.alerts):
        # ``_create_alert`` stores the metrics dict; we tag via the dedup state
        # key rather than the alert object, so detect by the well-known key
        # injected by ``report_browser_metrics``.
        if "browser_health_score" in (alert.metrics or {}):
            return alert
    return None


# ===========================================================================
# Task 7.3 — Property 15 + Property 21
# ===========================================================================
class TestBrowserMetricTrackingAndScoring:
    """Property 15 (metric tracking) + Property 21 (universal monitoring).

    Validates: Requirements 5.1, 6.1, 6.2, 6.3, 6.4
    """

    @given(metrics=_browser_metrics)
    @settings(max_examples=20, deadline=None,
              suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_metrics_are_tracked_and_round_trip(self, metrics: BrowserHealthMetrics) -> None:
        """**Property 15 / 21**: every well-formed metrics report is stored
        verbatim and ``get_browser_health`` returns the same shape, plus a
        score in [0, 1] and an alert level the dashboard can render.

        **Validates: Requirements 5.1, 6.1, 6.2, 6.3, 6.4**
        """
        monitor = _fresh_monitor()
        monitor.report_browser_metrics(metrics)

        snapshot = monitor.get_browser_health()
        # 1. Shape: get_browser_health returns the §4.4 contract.
        assert set(snapshot.keys()) == {"metrics", "browser_health_score", "alert_level"}

        # 2. Stored metrics round-trip: every field that came in is the field
        #    we get back out (Property 15: metric tracking).
        assert snapshot["metrics"] == asdict(metrics)

        # 3. Score is always in [0, 1] regardless of input (Property 21:
        #    universal health monitoring — no value crashes the calculator).
        score = snapshot["browser_health_score"]
        assert 0.0 <= score <= 1.0

        # 4. Alert level matches the spec-fixed thresholds.
        if score < 0.4:
            assert snapshot["alert_level"] == "critical"
        elif score < 0.7:
            assert snapshot["alert_level"] == "warning"
        else:
            assert snapshot["alert_level"] == "ok"


# ===========================================================================
# Task 7.6 — Property 22 + score-formula consistency
# ===========================================================================
class TestBrowserHealthScoreAndAlerts:
    """Property 22 (browser health impact alerts) + §4.5 formula consistency.

    Validates: Requirements 6.6
    """

    @given(metrics=_browser_metrics)
    @settings(max_examples=20, deadline=None,
              suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_score_calculation_is_deterministic(self, metrics: BrowserHealthMetrics) -> None:
        """**Property 22 (consistency)**: the §4.5 formula is a pure function —
        scoring the same metrics twice on independent monitors must agree.

        **Validates: Requirements 6.6**
        """
        m1 = _fresh_monitor()
        m2 = _fresh_monitor()
        s1 = m1.calculate_browser_health_score(metrics)
        s2 = m2.calculate_browser_health_score(metrics)
        assert s1 == s2
        # And the score is well-defined (not NaN, in [0, 1]).
        assert 0.0 <= s1 <= 1.0

    @given(metrics=_browser_metrics)
    @settings(max_examples=20, deadline=None,
              suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_alert_fires_iff_score_below_threshold(
        self, metrics: BrowserHealthMetrics
    ) -> None:
        """**Property 22**: an alert is created exactly when the score falls
        below 0.4 (the spec-fixed §4.2 threshold). When the score is at or
        above 0.4, no critical browser-health alert is emitted.

        **Validates: Requirements 6.6**
        """
        monitor = _fresh_monitor()
        score = monitor.calculate_browser_health_score(metrics)
        monitor.report_browser_metrics(metrics)

        alert = _last_browser_alert(monitor)
        if score < 0.4:
            assert alert is not None, (
                f"score={score:.3f} < 0.4 must trigger a browser_health alert"
            )
            assert alert.severity == "critical"
            # The metrics blob attached to the alert must include the score
            # the dashboard uses to render the status pill.
            assert alert.metrics["browser_health_score"] == pytest.approx(score)
        else:
            assert alert is None, (
                f"score={score:.3f} >= 0.4 must NOT trigger a browser_health alert"
            )

    @settings(max_examples=20, deadline=None)
    @given(
        ac1=st.integers(min_value=0, max_value=200),
        ac_delta=st.integers(min_value=1, max_value=200),
    )
    def test_more_active_contexts_never_increases_score(
        self, ac1: int, ac_delta: int
    ) -> None:
        """**Property 22 (monotonicity)**: holding every other field equal,
        adding more active contexts can only lower (or leave unchanged) the
        health score. This is what makes the score useful as a pressure gauge.

        **Validates: Requirements 6.6**
        """
        monitor = _fresh_monitor()
        low = BrowserHealthMetrics(active_contexts=ac1)
        high = BrowserHealthMetrics(active_contexts=ac1 + ac_delta)
        s_low = monitor.calculate_browser_health_score(low)
        s_high = monitor.calculate_browser_health_score(high)
        assert s_high <= s_low + 1e-9  # tolerate float drift only


# ===========================================================================
# Task 7.3 (additive) — N-snapshot tracking returns the LATEST values
# ===========================================================================
class TestBrowserMetricLatestSnapshot:
    """Property 15 (Browser Metric Tracking — multi-snapshot variant).

    Reporting N consecutive snapshots must leave ``get_browser_health`` showing
    the **last** values, never an averaged or stale snapshot. This is what
    makes the dashboard's "current pressure" pill correct.

    Validates: Requirements 5.1, 6.2, 6.3, 6.4
    """

    @given(snapshots=st.lists(_browser_metrics, min_size=1, max_size=12))
    @settings(max_examples=20, deadline=None,
              suppress_health_check=[HealthCheck.function_scoped_fixture,
                                     HealthCheck.too_slow])
    def test_metrics_tracked_correctly(self, snapshots) -> None:
        """**Property 15**: after N reports, the health view returns the last
        snapshot verbatim — N reports are not averaged, oldest is not retained.

        **Validates: Requirements 5.1, 6.2, 6.3, 6.4**
        """
        monitor = _fresh_monitor()
        for m in snapshots:
            monitor.report_browser_metrics(m)

        latest = snapshots[-1]
        snapshot = monitor.get_browser_health()
        # The stored metrics dict must equal the LAST report, not any earlier one.
        assert snapshot["metrics"] == asdict(latest)
        # And the score must equal the score of the last report (no stale data).
        assert snapshot["browser_health_score"] == pytest.approx(
            monitor.calculate_browser_health_score(latest)
        )


# ===========================================================================
# Task 7.6 (additive) — bundled consistency + monotonicity (memory + errors)
# ===========================================================================
class TestBrowserHealthScoreCombinedMonotonicity:
    """Property 22 (combined): determinism + bounds + monotonicity in the two
    pressure axes that aren't yet covered (memory and error_rate).

    Validates: Requirements 6.6
    """

    @given(metrics=_browser_metrics)
    @settings(max_examples=20, deadline=None,
              suppress_health_check=[HealthCheck.function_scoped_fixture,
                                     HealthCheck.too_slow])
    def test_health_score_consistency(self, metrics: BrowserHealthMetrics) -> None:
        """**Property 22 (consistency)**: identical inputs produce identical
        scores, and every score lives in [0, 1] regardless of input.

        **Validates: Requirements 6.6**
        """
        monitor = _fresh_monitor()
        s1 = monitor.calculate_browser_health_score(metrics)
        s2 = monitor.calculate_browser_health_score(metrics)
        assert s1 == s2
        assert 0.0 <= s1 <= 1.0

    @settings(max_examples=20, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    @given(
        mem1=st.floats(min_value=0.0, max_value=4096.0, allow_nan=False, allow_infinity=False),
        mem_delta=st.floats(min_value=1.0, max_value=4096.0, allow_nan=False, allow_infinity=False),
    )
    def test_lower_memory_yields_higher_score(self, mem1: float, mem_delta: float) -> None:
        """**Property 22 (memory monotonicity)**: holding all other fields
        equal, lower ``context_memory_mb`` produces a score >= the one for the
        higher value. This is what makes the score useful as a leak detector.

        **Validates: Requirements 6.6**
        """
        monitor = _fresh_monitor()
        low = BrowserHealthMetrics(context_memory_mb=mem1)
        high = BrowserHealthMetrics(context_memory_mb=mem1 + mem_delta)
        s_low = monitor.calculate_browser_health_score(low)
        s_high = monitor.calculate_browser_health_score(high)
        assert s_high <= s_low + 1e-9

    @settings(max_examples=20, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    @given(
        err1=st.floats(min_value=0.0, max_value=0.99, allow_nan=False, allow_infinity=False),
        err_delta=st.floats(min_value=0.001, max_value=0.5, allow_nan=False, allow_infinity=False),
    )
    def test_lower_error_rate_yields_higher_score(self, err1: float, err_delta: float) -> None:
        """**Property 22 (error-rate monotonicity)**: holding all other fields
        equal, a lower ``browser_error_rate`` produces a score >= the one for
        the higher value. Combined with memory monotonicity this gives the
        score the directional contract a dashboard can rely on.

        **Validates: Requirements 6.6**
        """
        monitor = _fresh_monitor()
        err2 = min(1.0, err1 + err_delta)
        low_err = BrowserHealthMetrics(browser_error_rate=err1)
        high_err = BrowserHealthMetrics(browser_error_rate=err2)
        s_low = monitor.calculate_browser_health_score(low_err)
        s_high = monitor.calculate_browser_health_score(high_err)
        assert s_high <= s_low + 1e-9
