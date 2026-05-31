"""Property-based tests for the browser learning engine extension.

Covers tasks 3.3 (Property 1 + Idempotency of Vulnerability Learning) and
3.6 (Property 5: Browser-Based Recommendations) from the
deep-system-integration spec.

Architecture invariants honoured:
  §9   scope-is-law   — every generated URL points at a fake .local host.
  §11  two-LLM        — no LLM calls; learn_from_browser_vulnerability is a
                        pure structural pattern extractor.
  §29.13 non-blocking — async work runs through ``asyncio.run`` inside the
                        property's helper, never inside Hypothesis itself.
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import pytest

# Hypothesis is required for these property tests; degrade gracefully when
# the dependency is missing so collection still succeeds elsewhere.
hypothesis = pytest.importorskip("hypothesis")
from hypothesis import HealthCheck, given, settings, strategies as st

from backend.core.learning_engine import ContinuousLearningEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _fresh_engine() -> ContinuousLearningEngine:
    """Build a learning engine rooted at a private temp brain dir.

    The directory is cleaned up by the strategy via the ``addfinalizer`` we
    drive from a fixture below — this helper itself returns a brand-new
    engine for each Hypothesis example so state never leaks across runs.
    """
    tmp = tempfile.mkdtemp(prefix="le-prop-")
    eng = ContinuousLearningEngine(brain_dir=tmp)
    eng.__test_tmpdir = tmp  # type: ignore[attr-defined]
    return eng


def _cleanup_engine(engine: ContinuousLearningEngine) -> None:
    tmp = getattr(engine, "__test_tmpdir", None)
    if tmp:
        shutil.rmtree(tmp, ignore_errors=True)


def _run(coro):
    """§29.13 — only ``asyncio.run`` calls live inside helpers."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------
# All hosts are fake .local — no real-network surface (§9).
_VULN_TYPES = st.sampled_from(["XSS", "SQLi", "CSRF", "SSRF", "RCE"])
_METHODS = st.sampled_from(["GET", "POST", "PUT", "DELETE"])
_FRAMEWORKS = st.sampled_from(["React", "Vue", "Angular", None])

_PATH_SEGMENT = st.from_regex(r"[a-z][a-z0-9_-]{0,15}", fullmatch=True)
_URL = st.builds(
    lambda host, segments: "https://"
    + host
    + "/"
    + "/".join(segments),
    st.sampled_from(["a.local", "b.local", "c.local"]),
    st.lists(_PATH_SEGMENT, min_size=1, max_size=3),
)


@st.composite
def _browser_vulnerability(draw) -> Dict[str, Any]:
    """Generate a browser-confirmed vulnerability payload."""
    return {
        "type": draw(_VULN_TYPES),
        "url": draw(_URL),
        "method": draw(_METHODS),
        "payload": draw(st.text(min_size=1, max_size=120)),
        "framework": draw(_FRAMEWORKS),
        "stealth_required": draw(st.booleans()),
        "session_required": draw(st.booleans()),
    }


# ---------------------------------------------------------------------------
# Task 3.3 — Property 1 + Idempotency of Vulnerability Learning
# ---------------------------------------------------------------------------
@given(vuln=_browser_vulnerability())
@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_property_1_idempotent_browser_vulnerability_learning(vuln: Dict[str, Any]) -> None:
    """**Validates: Requirements 1.1, 1.2, 1.3, 1.5**

    Property 1: Browser Skill Creation and Tagging.
    Property: Idempotency of Vulnerability Learning.

    For any browser-confirmed vulnerability, ``learn_from_browser_vulnerability``:
      a) returns True on first call (skill creation),
      b) returns False on a replay within the 5-minute idempotency window
         (no duplicate skill created),
      c) the resulting pattern is tagged with ``execution_context = browser_required``
         and carries a ``browser_context`` block (browser_automation tagging).
    """
    engine = _fresh_engine()
    try:
        first = _run(engine.learn_from_browser_vulnerability(vuln, "scan-prop-1"))
        assert first is True, "first learn must succeed"

        # b) Idempotent replay — same data inside the 5-minute window.
        replay = _run(engine.learn_from_browser_vulnerability(vuln, "scan-prop-1"))
        assert replay is False, (
            "replaying the same fingerprint inside the idempotency window "
            "must return False"
        )

        # a + c) Exactly one new browser_vulnerability pattern was stored,
        #        and it carries the required browser-automation tags.
        browser_patterns = [
            p
            for p in engine.patterns.values()
            if p.pattern_type == "browser_vulnerability"
        ]
        assert len(browser_patterns) == 1
        pattern = browser_patterns[0]
        assert pattern.pattern_data.get("execution_context") == "browser_required"
        assert isinstance(pattern.pattern_data.get("browser_context"), dict)
        # The vuln_type must round-trip onto the pattern unchanged.
        assert pattern.pattern_data.get("vuln_type") == vuln["type"]
    finally:
        _cleanup_engine(engine)


@given(vuln=_browser_vulnerability(), n_replays=st.integers(min_value=2, max_value=4))
@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_idempotency_no_duplicate_patterns_under_repeated_replays(
    vuln: Dict[str, Any], n_replays: int
) -> None:
    """**Validates: Requirements 1.1, 1.2, 1.3, 1.5**

    Property: Idempotency of Vulnerability Learning (stronger form).

    For any number of replays of the same vulnerability fingerprint within the
    idempotency window, exactly one ``browser_vulnerability`` pattern exists
    and every replay after the first returns False.
    """
    engine = _fresh_engine()
    try:
        results: List[bool] = []
        for _ in range(n_replays):
            results.append(
                _run(engine.learn_from_browser_vulnerability(vuln, "scan-replay"))
            )
        # First call True; every subsequent call False.
        assert results[0] is True
        assert all(r is False for r in results[1:])

        # No duplicate patterns regardless of the number of replays.
        browser_patterns = [
            p
            for p in engine.patterns.values()
            if p.pattern_type == "browser_vulnerability"
        ]
        assert len(browser_patterns) == 1
    finally:
        _cleanup_engine(engine)


# ---------------------------------------------------------------------------
# Task 3.6 — Property 5: Browser-Based Recommendations
# ---------------------------------------------------------------------------
@given(
    vulns=st.lists(_browser_vulnerability(), min_size=1, max_size=5, unique_by=lambda v: (v["url"], v["type"], v["payload"], v["method"])),
)
@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_property_5_recommendations_are_subset_of_stored_patterns(
    vulns: List[Dict[str, Any]],
) -> None:
    """**Validates: Requirements 2.5, 2.6**

    Property 5: Browser-Based Recommendations.

    For any set of stored browser-vulnerability patterns:
      a) ``get_browser_recommendations`` returns a structured dict with
         ``workflows`` / ``payloads`` / ``framework_specific`` lists,
      b) every returned ``payload`` row references a ``pattern_id`` that
         actually exists in the engine's pattern store (subset property),
      c) the ``confidence`` field is a float in [0.0, 1.0].
    """
    engine = _fresh_engine()
    try:
        # Seed the engine with the generated vulnerabilities.
        for v in vulns:
            _run(engine.learn_from_browser_vulnerability(v, "scan-reco"))

        target_url = vulns[0]["url"]
        recs = _run(engine.get_browser_recommendations({"url": target_url}))

        # a) Shape contract.
        assert isinstance(recs, dict)
        for key in ("workflows", "payloads", "framework_specific", "confidence"):
            assert key in recs
        assert isinstance(recs["workflows"], list)
        assert isinstance(recs["payloads"], list)
        assert isinstance(recs["framework_specific"], list)

        # b) Subset: every returned payload's pattern_id is in the store.
        stored_ids = set(engine.patterns.keys())
        for entry in recs["payloads"]:
            assert "pattern_id" in entry
            assert entry["pattern_id"] in stored_ids

        # c) Confidence bounds.
        assert isinstance(recs["confidence"], float)
        assert 0.0 <= recs["confidence"] <= 1.0
    finally:
        _cleanup_engine(engine)


@given(
    vulns=st.lists(_browser_vulnerability(), min_size=2, max_size=5, unique_by=lambda v: (v["url"], v["type"], v["payload"], v["method"])),
)
@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_property_5_payloads_ranked_by_confidence(vulns: List[Dict[str, Any]]) -> None:
    """**Validates: Requirements 2.5, 2.6**

    Property 5 (ranking sub-property): the ``payloads`` list is sorted by
    ``confidence`` descending — the engine's contract is "rank by
    confidence and success_rate, reverse=True".
    """
    engine = _fresh_engine()
    try:
        for v in vulns:
            _run(engine.learn_from_browser_vulnerability(v, "scan-rank"))

        target_url = vulns[0]["url"]
        recs = _run(engine.get_browser_recommendations({"url": target_url}))
        confidences = [p["confidence"] for p in recs["payloads"]]
        assert confidences == sorted(confidences, reverse=True)
    finally:
        _cleanup_engine(engine)
