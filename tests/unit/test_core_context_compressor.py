"""Tests for backend.core.context_compressor — estimate_tokens, _redact_secrets, CompressionResult, ContextCompressor."""
import pytest
from backend.core.context_compressor import estimate_tokens, _redact_secrets, CompressionResult, ContextCompressor


class TestEstimateTokens:
    def test_empty_string(self):
        assert estimate_tokens("") == 0

    def test_simple_text(self):
        tokens = estimate_tokens("hello world")
        assert tokens > 0

    def test_longer_text_more_tokens(self):
        short = estimate_tokens("hi")
        long = estimate_tokens("hello " * 100)
        assert long > short


class TestRedactSecrets:
    def test_api_key(self):
        text = "api_key=sk-1234567890abcdef"
        result = _redact_secrets(text)
        assert "sk-1234567890abcdef" not in result
        assert "REDACTED" in result

    def test_password(self):
        text = "password=hunter2"
        result = _redact_secrets(text)
        assert "hunter2" not in result

    def test_no_secrets(self):
        text = "normal text here"
        result = _redact_secrets(text)
        assert result == text


class TestCompressionResult:
    def test_creation(self):
        cr = CompressionResult(original_tokens=1000, compressed_tokens=500, summary="compressed")
        assert cr.original_tokens == 1000
        assert cr.compressed_tokens == 500
        assert cr.ratio == 0.5


class TestContextCompressor:
    def test_creation(self):
        cc = ContextCompressor()
        assert cc is not None

    def test_compress_short_text(self):
        cc = ContextCompressor()
        result = cc.compress("short text")
        assert isinstance(result, CompressionResult)
