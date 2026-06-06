"""Tests for backend.parsers.recon.base — ParsedEntity, utility functions."""
import pytest
from backend.parsers.recon.base import (
    ParsedEntity, extract_host, extract_query_params, is_valid_domain,
    is_ip_address, redact_secret,
)


class TestParsedEntity:
    def test_creation(self):
        pe = ParsedEntity(tool="nmap", kind="host", value="192.168.1.1")
        assert pe.tool == "nmap"
        assert pe.kind == "host"
        assert pe.value == "192.168.1.1"


class TestExtractHost:
    def test_url(self):
        assert extract_host("http://example.com:8080/path") == "example.com"

    def test_bare_host(self):
        assert extract_host("example.com") == "example.com"

    def test_ip(self):
        assert extract_host("192.168.1.1") == "192.168.1.1"


class TestExtractQueryParams:
    def test_with_params(self):
        result = extract_query_params("http://a.com?foo=bar&baz=1")
        assert len(result) == 2
        assert any(p["name"] == "foo" and p["value"] == "bar" for p in result)

    def test_no_params(self):
        result = extract_query_params("http://a.com")
        assert result == []


class TestIsValidDomain:
    def test_valid(self):
        assert is_valid_domain("example.com") is True

    def test_invalid(self):
        assert is_valid_domain("not a domain") is False

    def test_subdomain(self):
        assert is_valid_domain("sub.example.com") is True


class TestIsIpAddress:
    def test_valid_ip(self):
        assert is_ip_address("192.168.1.1") is True

    def test_not_ip(self):
        assert is_ip_address("example.com") is False

    def test_ipv6(self):
        assert is_ip_address("::1") is True


class TestRedactSecret:
    def test_long_value(self):
        result = redact_secret("sk-1234567890abcdef")
        assert len(result) < len("sk-1234567890abcdef")
        assert result.startswith("sk-1")

    def test_short_value(self):
        result = redact_secret("ab", visible_chars=4)
        assert result == "ab"
