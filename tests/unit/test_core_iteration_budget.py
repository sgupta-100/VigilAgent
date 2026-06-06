"""Tests for backend.core.iteration_budget — iteration budget management."""
import pytest


class TestIterationBudget:
    def test_import(self):
        from backend.core.iteration_budget import IterationBudget
        budget = IterationBudget(max_iterations=100)
        assert budget.max_iterations == 100

    def test_remaining(self):
        from backend.core.iteration_budget import IterationBudget
        budget = IterationBudget(max_iterations=10)
        budget.consume()
        budget.consume()
        assert budget.remaining == 8

    def test_exhausted(self):
        from backend.core.iteration_budget import IterationBudget
        budget = IterationBudget(max_iterations=2)
        budget.consume()
        budget.consume()
        assert budget.exhausted is True

    def test_not_exhausted(self):
        from backend.core.iteration_budget import IterationBudget
        budget = IterationBudget(max_iterations=5)
        budget.consume()
        assert budget.exhausted is False
