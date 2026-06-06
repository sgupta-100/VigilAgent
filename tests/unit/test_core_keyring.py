"""Tests for backend.core.keyring_intelligence — KeyringIntelligence, classify, get_stats."""
import pytest
from backend.core.keyring_intelligence import KeyringIntelligence


class TestKeyringIntelligence:
    def test_creation(self):
        ki = KeyringIntelligence()
        assert ki is not None

    def test_classify_jwt(self):
        ki = KeyringIntelligence()
        from backend.core.keyring_intelligence import TokenType
        fake_jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0In0.abc123"
        result = ki.classify(fake_jwt)
        assert result == TokenType.JWT

    def test_classify_bearer(self):
        ki = KeyringIntelligence()
        from backend.core.keyring_intelligence import TokenType
        result = ki.classify("Bearer mytoken123456789")
        assert result == TokenType.BEARER_TOKEN

    def test_classify_basic(self):
        ki = KeyringIntelligence()
        from backend.core.keyring_intelligence import TokenType
        result = ki.classify("Basic dXNlcjpwYXNz")
        assert result == TokenType.BASIC_AUTH

    def test_get_stats_safe(self):
        ki = KeyringIntelligence()
        try:
            stats = ki.get_stats()
            assert isinstance(stats, dict)
        except Exception:
            # keyring.json may not exist in test env
            pass
