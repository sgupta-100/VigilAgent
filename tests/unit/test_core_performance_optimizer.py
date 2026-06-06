"""Tests for backend.core.performance_optimizer — PerformanceOptimizer."""
import pytest


class TestPerformanceOptimizer:
    def test_import(self):
        from backend.core.performance_optimizer import PerformanceOptimizer
        po = PerformanceOptimizer()
        assert po is not None
