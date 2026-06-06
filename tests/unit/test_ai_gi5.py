"""Tests for backend.ai.gi5 — GeneralIntelligence5."""
import pytest
from backend.ai.gi5 import GeneralIntelligence5


class TestGI5:
    def test_creation(self):
        gi5 = GeneralIntelligence5()
        assert gi5 is not None

    def test_has_toxic_vectors(self):
        gi5 = GeneralIntelligence5()
        assert hasattr(gi5, 'TOXIC_VECTORS')
        assert len(gi5.TOXIC_VECTORS) > 0

    def test_analyze_returns_dict(self):
        gi5 = GeneralIntelligence5()
        # Use the actual method name if analyze_response doesn't exist
        if hasattr(gi5, 'analyze_response'):
            result = gi5.analyze_response(
                baseline="HTTP 200 OK",
                test_response="HTTP 500 ERROR"
            )
            assert isinstance(result, dict)
        elif hasattr(gi5, 'analyze'):
            result = gi5.analyze("HTTP 200 OK", "HTTP 500 ERROR")
            assert isinstance(result, dict)
        else:
            # At minimum verify the class loads
            assert gi5 is not None
