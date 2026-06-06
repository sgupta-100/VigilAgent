"""Tests for backend.agents._shared.agent_mixins — SkillRecallMixin, ControlSignalMixin."""
import pytest
from backend.agents._shared.agent_mixins import SkillRecallMixin, ControlSignalMixin


class TestSkillRecallMixin:
    def test_recall_skills_empty(self):
        class TestAgent(SkillRecallMixin):
            pass
        agent = TestAgent()
        result = agent.recall_skills("http://example.com", "SQL_INJECTION")
        assert isinstance(result, list)

    def test_skill_cache_bounded(self):
        class TestAgent(SkillRecallMixin):
            pass
        agent = TestAgent()
        cache = agent._skill_cache()
        assert isinstance(cache, dict)
        assert hasattr(agent, '_SKILL_CACHE_MAX')
        assert agent._SKILL_CACHE_MAX == 500


class TestControlSignalMixin:
    def test_throttle(self):
        class TestAgent(ControlSignalMixin):
            name = "test_agent"
            def __init__(self):
                self._throttled = False
                self._stealth_mode = False
        agent = TestAgent()
        agent._handle_throttle("THROTTLE")
        assert agent._throttled is True

    def test_resume(self):
        class TestAgent(ControlSignalMixin):
            name = "test_agent"
            def __init__(self):
                self._throttled = True
                self._stealth_mode = True
        agent = TestAgent()
        agent._handle_throttle("RESUME")
        assert agent._throttled is False
        assert agent._stealth_mode is False
