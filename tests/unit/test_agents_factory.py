"""Tests for backend.agents.factory — agent discovery."""
import pytest
from backend.agents.factory import discover_agent_classes, _agent_key


class TestAgentKey:
    def test_normalizes(self):
        assert _agent_key("AlphaAgent") == "alpha"
        assert _agent_key("BetaAgent") == "beta"
        assert _agent_key("AgentChi") == "chi"


class TestDiscoverAgentClasses:
    def test_returns_dict(self):
        result = discover_agent_classes()
        assert isinstance(result, dict)
        assert len(result) > 0

    def test_contains_known_agents(self):
        result = discover_agent_classes()
        assert "alpha" in result
        assert "beta" in result
        assert "sigma" in result
