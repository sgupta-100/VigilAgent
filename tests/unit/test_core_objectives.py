"""Tests for backend.core.objectives — ObjectivePlan, ObjectiveTransitionError."""
import pytest
from backend.core.objectives import ObjectivePlan, ObjectiveTransitionError


class TestObjectiveTransitionError:
    def test_is_value_error(self):
        assert issubclass(ObjectiveTransitionError, ValueError)


class TestObjectivePlan:
    def test_creation(self):
        op = ObjectivePlan()
        assert op is not None
        assert isinstance(op.objectives, list)
