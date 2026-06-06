"""Tests for backend.core.chain_analyzer — ChainAnalyzer."""
import pytest
from backend.core.chain_analyzer import ChainAnalyzer


class TestChainAnalyzer:
    def test_creation(self):
        ca = ChainAnalyzer()
        assert ca is not None

    def test_analyze_empty(self):
        ca = ChainAnalyzer()
        result = ca.analyze([])
        assert result == [] or isinstance(result, list)

    def test_analyze_single(self):
        ca = ChainAnalyzer()
        result = ca.analyze([{"type": "SQL_INJECTION", "url": "http://a.com"}])
        assert isinstance(result, list)
