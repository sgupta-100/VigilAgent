"""Tests for backend.core.performance_tracker — ActionRecord, PerformanceMetrics, PerformanceTracker."""
import time
import pytest
from backend.core.performance_tracker import ActionRecord, PerformanceMetrics, PerformanceTracker


class TestActionRecord:
    def test_creation(self):
        ar = ActionRecord(action="scan", start_time=time.time())
        assert ar.action == "scan"
        assert ar.end_time is None

    def test_finish(self):
        ar = ActionRecord(action="scan", start_time=time.time())
        ar.finish()
        assert ar.end_time is not None
        assert ar.duration_ms >= 0


class TestPerformanceMetrics:
    def test_creation(self):
        pm = PerformanceMetrics()
        assert pm.total_actions == 0
        assert pm.avg_latency_ms == 0.0


class TestPerformanceTracker:
    def test_creation(self):
        pt = PerformanceTracker()
        assert pt is not None

    def test_start_finish(self):
        pt = PerformanceTracker()
        action = pt.start_action("test_op")
        assert action is not None
        time.sleep(0.01)
        pt.finish_action(action)
        assert action.end_time is not None

    def test_get_metrics(self):
        pt = PerformanceTracker()
        metrics = pt.get_metrics()
        assert isinstance(metrics, PerformanceMetrics)

    def test_reset(self):
        pt = PerformanceTracker()
        pt.reset()
        metrics = pt.get_metrics()
        assert metrics.total_actions == 0
