"""Shared helpers for the agent family.

This package collects small, behaviour-preserving mixins that abstract the
boilerplate that was duplicated across the agent family (skill recall caches,
aiohttp session lifecycle, Zeta governance signal handling, ScanContext event
recording). The mixins are deliberately narrow — they just package the *exact*
patterns that already existed in each agent so the migration is a 1:1
substitution with no behaviour drift.

See ``backend.agents._shared.agent_mixins`` for the public mixin classes.
"""

from backend.agents._shared.agent_mixins import (
    ControlSignalMixin,
    ScanContextRecorderMixin,
    SessionLifecycleMixin,
    SkillRecallMixin,
)

__all__ = [
    "ControlSignalMixin",
    "ScanContextRecorderMixin",
    "SessionLifecycleMixin",
    "SkillRecallMixin",
]
