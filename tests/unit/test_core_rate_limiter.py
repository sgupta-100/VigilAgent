"""Tests for backend.core.rate_limiter — RateLimiter, token bucket, cleanup."""
import time
import asyncio
import pytest
from unittest.mock import patch, MagicMock
from backend.core.rate_limiter import RateLimiter, rate_limiter, rate_limit


class TestRateLimiter:
    def test_init(self):
        rl = RateLimiter()
        assert "default" in rl._limits
        assert "/api/ai" in rl._limits

    def test_configure_limit(self):
        rl = RateLimiter()
        rl.configure_limit("/custom", 100)
        assert rl._limits["/custom"] == 100

    def test_get_limit_exact(self):
        rl = RateLimiter()
        assert rl._get_limit("/api/ai") == 20

    def test_get_limit_pattern(self):
        rl = RateLimiter()
        assert rl._get_limit("/api/ai/mutations") == 20

    def test_get_limit_default(self):
        rl = RateLimiter()
        assert rl._get_limit("/unknown/endpoint") == 60

    @pytest.mark.asyncio
    async def test_allows_under_limit(self):
        rl = RateLimiter()
        result = await rl.check_rate_limit("1.2.3.4", "/api/test")
        assert result is True

    @pytest.mark.asyncio
    async def test_rate_limited(self):
        rl = RateLimiter()
        rl._limits["/test"] = 2
        await rl.check_rate_limit("1.2.3.4", "/test")
        await rl.check_rate_limit("1.2.3.4", "/test")
        with pytest.raises(Exception) as exc_info:
            await rl.check_rate_limit("1.2.3.4", "/test")
        assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_different_ips_independent(self):
        rl = RateLimiter()
        rl._limits["/test"] = 1
        await rl.check_rate_limit("1.1.1.1", "/test")
        # Different IP should still work
        result = await rl.check_rate_limit("2.2.2.2", "/test")
        assert result is True

    @pytest.mark.asyncio
    async def test_different_endpoints_independent(self):
        rl = RateLimiter()
        rl._limits["/a"] = 1
        rl._limits["/b"] = 1
        await rl.check_rate_limit("1.1.1.1", "/a")
        result = await rl.check_rate_limit("1.1.1.1", "/b")
        assert result is True

    @pytest.mark.asyncio
    async def test_cleanup_old_buckets(self):
        rl = RateLimiter()
        await rl.check_rate_limit("1.1.1.1", "/test")
        # Simulate old bucket by backdating
        for ep in rl._buckets["1.1.1.1"]:
            tokens, _ = rl._buckets["1.1.1.1"][ep]
            rl._buckets["1.1.1.1"][ep] = (tokens, time.time() - 7200)
        await rl.cleanup_old_buckets(max_age_seconds=3600)
        assert "1.1.1.1" not in rl._buckets


class TestGlobalRateLimiter:
    def test_singleton(self):
        assert isinstance(rate_limiter, RateLimiter)


class TestRateLimitDecorator:
    def test_decorator_exists(self):
        assert callable(rate_limit())
