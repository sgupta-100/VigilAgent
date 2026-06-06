"""Tests for backend.reporting.hackerone — HackerOne report rendering."""
import pytest
from backend.reporting.hackerone import render_hackerone_report


class TestRenderHackeroneReport:
    def test_basic_finding(self):
        finding = {
            "type": "SQL Injection",
            "severity": "high",
            "url": "http://example.com/api/users",
            "description": "SQL injection in login form",
            "evidence": "payload: ' OR 1=1--",
            "remediation": "Use parameterized queries",
        }
        result = render_hackerone_report(finding)
        assert "SQL Injection" in result
        assert "http://example.com" in result

    def test_minimal_finding(self):
        finding = {"type": "XSS", "severity": "medium", "url": "http://a.com"}
        result = render_hackerone_report(finding)
        assert isinstance(result, str)
        assert len(result) > 0
