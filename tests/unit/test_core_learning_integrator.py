"""Tests for backend.core.learning_integrator — LearningIntegrator."""
import pytest
from backend.core.learning_integrator import LearningIntegrator
from backend.core.self_awareness_config import get_self_awareness_config


class TestLearningIntegrator:
    def test_creation(self):
        config = get_self_awareness_config()
        li = LearningIntegrator(agent_id="alpha", config=config)
        assert li.agent_id == "alpha"
