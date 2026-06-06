"""Tests for backend.modules.evidence — differential evidence, baseline comparison."""
import pytest
from backend.modules.evidence import (
    DiffEvidence, differential, first_baseline, confirm_against_baseline,
    logic_confirm, classify_response_evidence, looks_like_class, url_matches_class,
)


class TestDiffEvidence:
    def test_creation(self):
        de = DiffEvidence(baseline_status=200, test_status=500, diff_score=0.8)
        assert de.baseline_status == 200
        assert de.test_status == 500
        assert de.diff_score == 0.8


class TestDifferential:
    def test_identical(self):
        result = differential("same", "same")
        assert result.diff_score < 0.1

    def test_different(self):
        result = differential("HTTP 200 OK", "HTTP 500 Server Error")
        assert result.diff_score > 0.3


class TestClassifyResponseEvidence:
    def test_empty(self):
        result = classify_response_evidence("")
        assert isinstance(result, set)

    def test_error_indicators(self):
        result = classify_response_evidence("SQL syntax error near line 1")
        assert isinstance(result, set)


class TestLooksLikeClass:
    def test_match(self):
        assert looks_like_class("<div class='test'>", declared_class="test") is True

    def test_no_match(self):
        assert looks_like_class("<div class='other'>", declared_class="test") is False


class TestUrlMatchesClass:
    def test_match(self):
        assert url_matches_class("http://example.com/test", declared_class="test") is True

    def test_no_match(self):
        assert url_matches_class("http://example.com/other", declared_class="test") is False


class TestLogicConfirm:
    def test_positive_markers(self):
        result = logic_confirm(
            "Welcome Admin Dashboard",
            positive_markers=["admin", "dashboard"],
            negative_markers=[]
        )
        assert isinstance(result, dict)


class TestFirstBaseline:
    def test_empty(self):
        result = first_baseline([])
        assert result is None

    def test_with_data(self):
        interactions = [("resp1", "body1")]
        result = first_baseline(interactions)
        assert result is not None
