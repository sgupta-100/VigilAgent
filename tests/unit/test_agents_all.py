"""Tests for backend.agents modules — gamma, kappa, delta, omega, prism, zeta, chi, lambda."""
import pytest


class TestAgentGamma:
    def test_import(self):
        from backend.agents.gamma import GammaAgent
        assert GammaAgent is not None


class TestAgentKappa:
    def test_import(self):
        from backend.agents.kappa import KappaAgent
        assert KappaAgent is not None


class TestAgentDelta:
    def test_import(self):
        from backend.agents.delta import AgentDelta
        assert AgentDelta is not None


class TestAgentOmega:
    def test_import(self):
        from backend.agents.omega import OmegaAgent
        assert OmegaAgent is not None


class TestAgentPrism:
    def test_import(self):
        from backend.agents.prism import AgentPrism
        assert AgentPrism is not None


class TestAgentZeta:
    def test_import(self):
        from backend.agents.zeta import ZetaAgent
        assert ZetaAgent is not None


class TestAgentChi:
    def test_import(self):
        from backend.agents.chi import AgentChi
        assert AgentChi is not None


class TestAgentLambda:
    def test_import(self):
        from backend.agents.lambda_agent import LambdaAgent
        assert LambdaAgent is not None
