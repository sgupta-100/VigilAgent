"""Tests for backend.core.perf — TTLCache."""
import time
import pytest
from backend.core.perf import TTLCache


class TestTTLCache:
    def test_set_get(self):
        cache = TTLCache(ttl_seconds=10)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_miss(self):
        cache = TTLCache(ttl_seconds=10)
        assert cache.get("missing") is None

    def test_ttl_expiry(self):
        cache = TTLCache(ttl_seconds=0.1)
        cache.set("key1", "value1")
        time.sleep(0.15)
        assert cache.get("key1") is None

    def test_get_or_compute(self):
        cache = TTLCache(ttl_seconds=10)
        result = cache.get_or_compute("k1", lambda: "computed")
        assert result == "computed"
        # Second call should hit cache
        result2 = cache.get_or_compute("k1", lambda: "other")
        assert result2 == "computed"

    def test_invalidate(self):
        cache = TTLCache(ttl_seconds=10)
        cache.set("k1", "v1")
        cache.invalidate()
        assert cache.get("k1") is None

    def test_invalidate_prefix(self):
        cache = TTLCache(ttl_seconds=10)
        cache.set("prefix_a", "1")
        cache.set("prefix_b", "2")
        cache.set("other_c", "3")
        cache.invalidate(prefix="prefix")
        assert cache.get("prefix_a") is None
        assert cache.get("other_c") == "3"

    def test_delete(self):
        cache = TTLCache(ttl_seconds=10)
        cache.set("k1", "v1")
        cache.delete("k1")
        assert cache.get("k1") is None

    def test_len(self):
        cache = TTLCache(ttl_seconds=10)
        cache.set("a", 1)
        cache.set("b", 2)
        assert len(cache) == 2

    def test_contains(self):
        cache = TTLCache(ttl_seconds=10)
        cache.set("k1", "v1")
        assert "k1" in cache
        assert "k2" not in cache
