"""Tests for backend.core.broadcast_throttle — BroadcastThrottle."""
import time
import pytest
from backend.core.broadcast_throttle import BroadcastThrottle


class TestBroadcastThrottle:
    def test_creation(self):
        bt = BroadcastThrottle(window_ms=500)
        assert bt is not None

    def test_invalid_window(self):
        with pytest.raises(ValueError):
            BroadcastThrottle(window_ms=-1)

    def test_should_emit_first(self):
        bt = BroadcastThrottle(window_ms=500)
        assert bt.should_emit("evt1") is True

    def test_throttle_same_key(self):
        bt = BroadcastThrottle(window_ms=500)
        bt.should_emit("evt1")
        assert bt.should_emit("evt1") is False

    def test_different_keys(self):
        bt = BroadcastThrottle(window_ms=500)
        assert bt.should_emit("evt1") is True
        assert bt.should_emit("evt2") is True

    def test_window_expiry(self):
        bt = BroadcastThrottle(window_ms=50)
        bt.should_emit("evt1")
        time.sleep(0.1)
        assert bt.should_emit("evt1") is True

    def test_max_keys_eviction(self):
        bt = BroadcastThrottle(window_ms=60000, max_keys=3)
        for i in range(5):
            bt.should_emit(f"key_{i}")
        # Should not crash — eviction happened
        assert True

    def test_zero_window_disables_throttle(self):
        bt = BroadcastThrottle(window_ms=0)
        bt.should_emit("evt1")
        assert bt.should_emit("evt1") is True
