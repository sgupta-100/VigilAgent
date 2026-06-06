"""Tests for backend.reporting.sarif — SARIF report generation."""
import pytest
from backend.reporting.sarif import findings_to_sarif, _sarif_level


class TestSarifLevel:
    def test_critical(self):
        assert _sarif_level("critical") == "error"

    def test_high(self):
        assert _sarif_level("high") == "error"

    def test_medium(self):
        assert _sarif_level("medium") == "warning"

    def test_low(self):
        assert _sarif_level("low") == "note"

    def test_info(self):
        assert _sarif_level("info") == "note"

    def test_unknown(self):
        assert _sarif_level("unknown") == "warning"


class TestFindingsToSarif:
    def test_empty_findings(self):
        result = findings_to_sarif([])
        assert result["version"] == "2.1.0"
        assert result["runs"]

    def test_with_findings(self):
        findings = [
            {
                "type": "SQL Injection",
                "severity": "high",
                "url": "http://a.com",
                "description": "SQLi found",
                "evidence": "payload",
                "remediation": "use parameterized queries",
            }
        ]
        result = findings_to_sarif(findings)
        assert result["version"] == "2.1.0"
        assert len(result["runs"]) == 1
