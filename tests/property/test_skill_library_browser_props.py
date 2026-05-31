"""Property-based tests for BrowserSkillLibraryExtension.

Covers:
  * Task 5.4 — Property 3 (High-Confidence Skill Distribution) and
                Property 10 (Unified Skill Storage).
  * Task 5.6 — Property 11 (Capability-Based Skill Filtering).
  * Task 5.8 — Property 55 (Workflow Composition).

Architecture invariants honoured:
  §9   scope-is-law   — every skill is stored under a private temp brain dir;
                        no host data is fabricated.
  §11  two-LLM        — skills are pure data; no LLM bindings touched.
  §29.13 non-blocking — extension methods are synchronous; no asyncio at all.
"""

from __future__ import annotations

import shutil
import tempfile
import uuid
from typing import Any, Dict, FrozenSet, List

import pytest

# Hypothesis is required for these property tests; degrade gracefully when
# the dependency is missing so collection still succeeds elsewhere.
hypothesis = pytest.importorskip("hypothesis")
from hypothesis import HealthCheck, assume, given, settings, strategies as st

from backend.core.skill_library import (
    BrowserSkill,
    BrowserSkillLibraryExtension,
    SkillLibrary,
)


# ---------------------------------------------------------------------------
# Helpers + strategies
# ---------------------------------------------------------------------------
_CAPABILITY_VOCAB = ("http", "browser", "stealth", "session")
_FRAMEWORKS = ("React", "Vue", "Angular")
_CONTEXTS = ("browser_required", "http_only", "hybrid")


def _fresh_library() -> tuple[SkillLibrary, BrowserSkillLibraryExtension, str]:
    tmp = tempfile.mkdtemp(prefix="sl-prop-")
    lib = SkillLibrary(brain_dir=tmp)
    return lib, BrowserSkillLibraryExtension(lib), tmp


def _cleanup(tmp: str) -> None:
    shutil.rmtree(tmp, ignore_errors=True)


@st.composite
def _semver(draw) -> str:
    return f"{draw(st.integers(0, 9))}.{draw(st.integers(0, 9))}.{draw(st.integers(0, 9))}"


@st.composite
def _browser_skill(draw) -> BrowserSkill:
    """Generate a unique BrowserSkill with valid contract fields."""
    caps: FrozenSet[str] = frozenset(
        draw(
            st.sets(
                st.sampled_from(_CAPABILITY_VOCAB),
                min_size=1,
                max_size=len(_CAPABILITY_VOCAB),
            )
        )
    )
    return BrowserSkill(
        # Use uuid4 so generated examples never collide on skill_id, which
        # is the dedupe key inside ``add_browser_skill``.
        skill_id=f"sk-{uuid.uuid4().hex[:12]}",
        name=draw(st.text(min_size=1, max_size=20, alphabet=st.characters(min_codepoint=97, max_codepoint=122))),
        description="",
        skill_type=draw(st.sampled_from(["payload", "endpoint", "chain", "evasion"])),
        execution_context=draw(st.sampled_from(_CONTEXTS)),
        browser_requirements={
            "stealth": draw(st.booleans()),
            "session": draw(st.booleans()),
            "framework": draw(st.sampled_from(_FRAMEWORKS)),
        },
        workflow_steps=[],
        evidence_requirements={},
        version=draw(_semver()),
        required_capabilities=caps,
        success_count=draw(st.integers(0, 100)),
        failure_count=draw(st.integers(0, 100)),
        confidence=draw(st.floats(min_value=0.0, max_value=1.0)),
    )


@st.composite
def _workflow_skill(draw) -> BrowserSkill:
    """Generate a workflow skill (skill_type=workflow, has workflow_steps)."""
    framework = draw(st.sampled_from(_FRAMEWORKS))
    n_steps = draw(st.integers(1, 4))
    steps = [
        {"action": "step", "index": i, "framework": framework}
        for i in range(n_steps)
    ]
    return BrowserSkill(
        skill_id=f"wf-{uuid.uuid4().hex[:12]}",
        name=draw(st.text(min_size=1, max_size=20, alphabet=st.characters(min_codepoint=97, max_codepoint=122))),
        skill_type="workflow",
        execution_context="browser_required",
        browser_requirements={
            "stealth": draw(st.booleans()),
            "session": draw(st.booleans()),
            "framework": framework,
        },
        workflow_steps=steps,
        evidence_requirements={},
        version="1.0.0",
        required_capabilities=frozenset(
            draw(
                st.sets(
                    st.sampled_from(_CAPABILITY_VOCAB),
                    min_size=1,
                    max_size=len(_CAPABILITY_VOCAB),
                )
            )
        ),
        confidence=draw(st.floats(min_value=0.0, max_value=1.0)),
    )


# ---------------------------------------------------------------------------
# Task 5.4 — Property 3 + Property 10: Storage & retrieval
# ---------------------------------------------------------------------------
@given(skills=st.lists(_browser_skill(), min_size=1, max_size=8, unique_by=lambda s: s.skill_id))
@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_property_3_and_10_unified_skill_storage_round_trip(
    skills: List[BrowserSkill],
) -> None:
    """**Validates: Requirements 1.6, 4.1, 4.2**

    Property 3: High-Confidence Skill Distribution — every skill that has
    been added to the library is queryable by a capability superset.

    Property 10: Unified Skill Storage — all browser skills land in the same
    metadata store and are retrievable by ``search_browser_skills``.
    """
    _, ext, tmp = _fresh_library()
    try:
        added: List[BrowserSkill] = []
        for skill in skills:
            if ext.add_browser_skill(skill, {}):
                added.append(skill)
        # Every accepted skill must end up in the metadata index.
        for skill in added:
            assert skill.skill_id in ext.library.metadata

        # Search with the universal capability superset must surface every
        # added (non-deprecated) skill.
        full_caps = list(_CAPABILITY_VOCAB)
        results = ext.search_browser_skills(agent_capabilities=full_caps, limit=1000)
        result_ids = {s.skill_id for s in results}
        for skill in added:
            if not skill.deprecated:
                assert skill.skill_id in result_ids, (
                    f"skill {skill.skill_id} missing from search results"
                )
    finally:
        _cleanup(tmp)


@given(skill=_browser_skill())
@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_property_10_no_duplicate_skill_ids(skill: BrowserSkill) -> None:
    """**Validates: Requirements 4.1, 4.2**

    Property 10 (dedupe sub-property): adding the same ``skill_id`` twice
    must return False on the second call and must NOT create a duplicate
    metadata row.
    """
    _, ext, tmp = _fresh_library()
    try:
        first = ext.add_browser_skill(skill, {})
        second = ext.add_browser_skill(skill, {})
        assert first is True
        assert second is False
        # Exactly one metadata entry exists.
        assert sum(1 for k in ext.library.metadata if k == skill.skill_id) == 1
    finally:
        _cleanup(tmp)


# ---------------------------------------------------------------------------
# Task 5.6 — Property 11: Capability-Based Skill Filtering
# ---------------------------------------------------------------------------
@given(
    skills=st.lists(_browser_skill(), min_size=1, max_size=6, unique_by=lambda s: s.skill_id),
    agent_caps=st.sets(st.sampled_from(_CAPABILITY_VOCAB), min_size=1, max_size=len(_CAPABILITY_VOCAB)),
)
@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_property_11_capability_filtering(
    skills: List[BrowserSkill], agent_caps: set
) -> None:
    """**Validates: Requirements 4.3**

    Property 11: Capability-Based Skill Filtering. For any agent capability
    set, ``search_browser_skills``:

      a) returns a subset of the stored skills,
      b) every returned skill's ``required_capabilities`` is a subset of the
         agent capabilities (the filter is a strict subset check),
      c) deprecated skills are excluded.
    """
    _, ext, tmp = _fresh_library()
    try:
        for skill in skills:
            ext.add_browser_skill(skill, {})

        results = ext.search_browser_skills(
            agent_capabilities=list(agent_caps), limit=1000
        )

        all_ids = {s.skill_id for s in skills}
        result_ids = {s.skill_id for s in results}
        # a) Subset.
        assert result_ids.issubset(all_ids)
        # b) Capability subset check.
        for s in results:
            assert s.required_capabilities.issubset(agent_caps), (
                f"{s.skill_id} requires {set(s.required_capabilities)} "
                f"but agent only has {agent_caps}"
            )
        # c) No deprecated skills slip through. Use library metadata so we
        #    inspect the persisted state rather than the in-memory dataclass.
        for s in results:
            assert ext.library.metadata[s.skill_id].get("deprecated", False) is False
    finally:
        _cleanup(tmp)


@given(skill=_browser_skill())
@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_property_11_deprecated_skills_excluded(skill: BrowserSkill) -> None:
    """**Validates: Requirements 4.3**

    Property 11 (deprecation sub-property): once a skill is deprecated via
    ``deprecate_skill``, ``search_browser_skills`` must not return it even
    when the agent's capabilities trivially satisfy the filter.
    """
    _, ext, tmp = _fresh_library()
    try:
        assume(ext.add_browser_skill(skill, {}))
        ext.deprecate_skill(skill.skill_id, reason="superseded")
        results = ext.search_browser_skills(
            agent_capabilities=list(_CAPABILITY_VOCAB), limit=1000
        )
        assert all(r.skill_id != skill.skill_id for r in results)
    finally:
        _cleanup(tmp)


# ---------------------------------------------------------------------------
# Task 5.8 — Property 55: Workflow Composition
# ---------------------------------------------------------------------------
@given(workflows=st.lists(_workflow_skill(), min_size=2, max_size=4, unique_by=lambda s: s.skill_id))
@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_property_55_workflow_composition(workflows: List[BrowserSkill]) -> None:
    """**Validates: Requirements 16.4**

    Property 55: Workflow Composition. For any set of compatible workflow
    skills:

      a) ``compose_workflows`` returns a single composed BrowserSkill,
      b) the composed ``workflow_steps`` is the in-order concatenation of
         every constituent's ``workflow_steps`` (no step lost or added),
      c) the composed ``required_capabilities`` is the union of every
         constituent's required capabilities.
    """
    # Constrain: composition contract requires identical framework across
    # constituents. Pick the first skill's framework and project everything
    # else onto it.
    framework = workflows[0].browser_requirements.get("framework")
    for w in workflows:
        w.browser_requirements["framework"] = framework

    _, ext, tmp = _fresh_library()
    try:
        composed = ext.compose_workflows(workflows)
        # a) Single composed skill returned.
        assert composed is not None
        assert isinstance(composed, BrowserSkill)

        # b) Steps = concatenation in order.
        expected_steps: List[Dict[str, Any]] = []
        for w in workflows:
            expected_steps.extend(w.workflow_steps)
        assert composed.workflow_steps == expected_steps
        assert len(composed.workflow_steps) == sum(
            len(w.workflow_steps) for w in workflows
        )

        # c) required_capabilities is the union.
        expected_caps: set = set()
        for w in workflows:
            expected_caps |= set(w.required_capabilities)
        assert set(composed.required_capabilities) == expected_caps
    finally:
        _cleanup(tmp)


@given(workflows=st.lists(_workflow_skill(), min_size=2, max_size=3, unique_by=lambda s: s.skill_id))
@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_property_55_browser_requirements_or_merged(
    workflows: List[BrowserSkill],
) -> None:
    """**Validates: Requirements 16.4**

    Property 55 (requirements-merge sub-property): boolean fields in
    ``browser_requirements`` are OR-merged across constituents (per the
    extension's documented merge rule for ``stealth`` and ``session``).
    """
    framework = workflows[0].browser_requirements.get("framework")
    for w in workflows:
        w.browser_requirements["framework"] = framework

    _, ext, tmp = _fresh_library()
    try:
        composed = ext.compose_workflows(workflows)
        assert composed is not None
        for key in ("stealth", "session"):
            expected = any(
                bool(w.browser_requirements.get(key, False)) for w in workflows
            )
            assert composed.browser_requirements.get(key, False) is expected
    finally:
        _cleanup(tmp)
