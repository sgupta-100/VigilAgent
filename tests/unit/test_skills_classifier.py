"""Tests for backend.skills.classifier — domain and risk classification."""
import pytest
from backend.skills.classifier import classify_domain, classify_risk, is_offensive, needs_network


class TestClassifyDomain:
    def test_web_keywords(self):
        result = classify_domain("SQL injection in web form")
        assert isinstance(result, str)

    def test_network_keywords(self):
        result = classify_domain("port scanning and service enumeration")
        assert isinstance(result, str)


class TestClassifyRisk:
    def test_safe_text(self):
        result = classify_risk("read-only directory listing")
        assert isinstance(result, str)

    def test_offensive_hint(self):
        result = classify_risk("exploitation attempt", offensive_hint=True)
        assert isinstance(result, str)


class TestIsOffensive:
    def test_exploit_text(self):
        assert is_offensive("remote code execution exploit") is True

    def test_safe_text(self):
        assert is_offensive("directory listing") is False


class TestNeedsNetwork:
    def test_port_scan(self):
        assert needs_network("port scan on target") is True

    def test_file_read(self):
        assert needs_network("read local file") is False
