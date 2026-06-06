"""Tests for backend.core.remediation — FrameworkDetector, PatchGenerator."""
import pytest
from backend.core.remediation import FrameworkDetector, PatchGenerator


class TestFrameworkDetector:
    def test_detect_empty(self):
        result = FrameworkDetector.detect("")
        assert isinstance(result, str)

    def test_detect_python(self):
        result = FrameworkDetector.detect("import flask")
        assert isinstance(result, str)

    def test_detect_django(self):
        result = FrameworkDetector.detect("from django.conf import settings")
        assert isinstance(result, str)


class TestPatchGenerator:
    def test_create_diff(self):
        before = "def foo():\n    pass\n"
        after = "def foo():\n    return 42\n"
        result = PatchGenerator.create_diff(before, after)
        assert isinstance(result, str)
        assert "return 42" in result

    def test_no_changes(self):
        result = PatchGenerator.create_diff("same", "same")
        assert isinstance(result, str)
