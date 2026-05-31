"""Property-based tests for ``backend.core.forensic_learning_bridge.ForensicLearningBridge``.

Covers spec ``deep-system-integration`` tasks 13.8 (evidence quality
scoring) and 13.10 (evidence value learning).

Architecture invariants honoured:
  §9   scope-is-law       — evidence dicts are advisory metadata; nothing
                            in this test grants scope.
  §11  two-LLM exclusivity — quality scoring is rule-based; no LLM calls.
  §17  ≥2-signal advisory — quality score is a meta-metric over evidence
                            already gathered, not a re-verification.
  §29.13 non-blocking      — ``asyncio.run`` drives the async writer once
                            per example.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any, Dict, Set
from unittest.mock import AsyncMock

import pytest

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import HealthCheck, given, settings, strategies as st

from backend.core.forensic_learning_bridge import (
    _EVIDENCE_TYPE_MAP,
    ForensicLearningBridge,
)


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------
def _engine_stub() -> SimpleNamespace:
    """Stub learning_engine: real ``patterns`` dict + AsyncMock saver."""
    return SimpleNamespace(
        patterns={},
        _save_patterns=AsyncMock(return_value=None),
    )


# Strategy: pick a vuln_type that has a deterministic requirement set.
_known_vuln_type = st.sampled_from(["xss", "sqli"])


@st.composite
def _evidence_subset_strategy(draw, vuln_type: str) -> Dict[str, Any]:
    """Generate an evidence dict containing a SUBSET of the required types
    for ``vuln_type``, plus optional unrelated extras.
    """
    required = sorted(_EVIDENCE_TYPE_MAP[vuln_type])
    chosen = draw(st.lists(st.sampled_from(required), unique=True, min_size=0, max_size=len(required)))
    bundle: Dict[str, Any] = {"vuln_type": vuln_type}
    for tok in chosen:
        bundle[tok] = f"evidence-blob-for-{tok}"
    # Optional extras (capped) — exercise the bonus path without breaking
    # required-set arithmetic.
    extras = draw(st.lists(
        st.sampled_from(["request_response", "timing", "har", "video"]),
        unique=True, min_size=0, max_size=2,
    ))
    for tok in extras:
        if tok not in bundle:
            bundle[tok] = "extra-blob"
    return bundle


# ---------------------------------------------------------------------------
# Property 32 — Evidence Quality Analysis  (Task 13.8)
# ---------------------------------------------------------------------------
class TestEvidenceQualityScoring:
    """**Validates: Requirements 9.2**

    Property 32 — for a given vuln_type, more required evidence types
    present implies a non-decreasing ``score`` and a non-increasing
    ``missing`` set; missing required types are correctly identified.
    """

    @settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    @given(vuln_type=_known_vuln_type, data=st.data())
    def test_score_monotonic_in_required_coverage(self, vuln_type: str, data: Any) -> None:
        bridge = ForensicLearningBridge()
        required: Set[str] = _EVIDENCE_TYPE_MAP[vuln_type]
        required_sorted = sorted(required)

        # Pick how many required types to include in the SMALL bundle.
        small_n = data.draw(st.integers(min_value=0, max_value=len(required_sorted) - 1), label="small_n")
        # LARGE bundle adds at least one more required type.
        extra_n = data.draw(st.integers(min_value=1, max_value=len(required_sorted) - small_n), label="extra_n")

        small_keys = required_sorted[:small_n]
        large_keys = required_sorted[: small_n + extra_n]

        small_bundle: Dict[str, Any] = {"vuln_type": vuln_type, **{k: "blob" for k in small_keys}}
        large_bundle: Dict[str, Any] = {"vuln_type": vuln_type, **{k: "blob" for k in large_keys}}

        small_result = bridge.analyze_evidence_quality(small_bundle)
        large_result = bridge.analyze_evidence_quality(large_bundle)

        # Adding required evidence must not lower the score.
        assert large_result["score"] >= small_result["score"], (
            f"score regressed: small={small_result['score']} large={large_result['score']}"
        )
        # And must not grow the missing set.
        assert set(large_result["missing"]).issubset(set(small_result["missing"])), (
            f"missing set grew when more evidence was added: "
            f"small={small_result['missing']} large={large_result['missing']}"
        )

    @settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    @given(vuln_type=_known_vuln_type, evidence=st.data())
    def test_missing_identifies_absent_required_types(self, vuln_type: str, evidence: Any) -> None:
        bridge = ForensicLearningBridge()
        bundle = evidence.draw(_evidence_subset_strategy(vuln_type), label="bundle")

        result = bridge.analyze_evidence_quality(bundle)
        present_keys = {k for k, v in bundle.items() if k not in {"vuln_type", "type"} and v}
        required = _EVIDENCE_TYPE_MAP[vuln_type]

        # Core invariant: every required type NOT in the bundle must be in `missing`.
        expected_missing = sorted(required - present_keys)
        assert result["missing"] == expected_missing
        # Score is in [0,1] regardless of inputs.
        assert 0.0 <= result["score"] <= 1.0


# ---------------------------------------------------------------------------
# Property 33 — Evidence Value Learning  (Task 13.10)
# ---------------------------------------------------------------------------
class TestEvidenceValueLearning:
    """**Validates: Requirements 9.3**

    Property 33 — calling ``learn_evidence_requirements`` repeatedly for
    the same ``(vuln_type, evidence_type)`` increments ``success_count``
    monotonically, and ``success_rate`` (the value score) rises toward 1.0.
    """

    @settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    @given(
        vuln_type=_known_vuln_type,
        repeats=st.integers(min_value=1, max_value=6),
    )
    def test_repeated_observations_increase_value_score(
        self, vuln_type: str, repeats: int
    ) -> None:
        engine = _engine_stub()
        bridge = ForensicLearningBridge(learning_engine=engine)

        # Use the canonical first required type for this vuln class so the
        # pattern_id is stable across repeats. The bridge will mint exactly
        # one row keyed by (vuln_type, evidence_type).
        ev_type = sorted(_EVIDENCE_TYPE_MAP[vuln_type])[0]
        bundle = {"vuln_type": vuln_type, ev_type: "blob"}

        async def _drive() -> None:
            for i in range(repeats):
                ok = await bridge.learn_evidence_requirements(
                    vuln_type=vuln_type, evidence=bundle, scan_id=f"scan-{i}",
                )
                assert ok is True

        asyncio.run(_drive())

        # Exactly one pattern row should exist for this (vuln_type, ev_type).
        rows = [
            p for p in engine.patterns.values()
            if p.pattern_type == "evidence_requirement"
            and p.pattern_data.get("vuln_type") == vuln_type
            and p.pattern_data.get("evidence_type") == ev_type
        ]
        assert len(rows) == 1, f"expected single pattern row, got {len(rows)}"
        row = rows[0]

        # success_count tracks repeats; success_rate is 1.0 (no failures).
        assert row.success_count == repeats
        assert row.success_rate == 1.0
        # Confidence rises with sample size; for repeats >= 1 it must be > 0.
        assert row.confidence > 0.0

    @settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    @given(vuln_type=_known_vuln_type)
    def test_distinct_evidence_types_get_distinct_rows(self, vuln_type: str) -> None:
        engine = _engine_stub()
        bridge = ForensicLearningBridge(learning_engine=engine)

        # Bundle contains every required type for the vuln_type in one shot.
        ev_types = sorted(_EVIDENCE_TYPE_MAP[vuln_type])
        bundle: Dict[str, Any] = {"vuln_type": vuln_type}
        for tok in ev_types:
            bundle[tok] = "blob"

        async def _drive() -> bool:
            return await bridge.learn_evidence_requirements(
                vuln_type=vuln_type, evidence=bundle, scan_id="single",
            )

        assert asyncio.run(_drive()) is True

        rows = [
            p for p in engine.patterns.values()
            if p.pattern_type == "evidence_requirement"
            and p.pattern_data.get("vuln_type") == vuln_type
        ]
        # One row per required evidence type.
        assert len(rows) == len(ev_types)
        learned_types = {p.pattern_data["evidence_type"] for p in rows}
        assert learned_types == set(ev_types)
