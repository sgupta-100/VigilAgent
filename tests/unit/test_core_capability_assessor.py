"""Tests for backend.core.capability_assessor — CapabilityAssessor, PrerequisiteCheck."""
import pytest
from backend.core.capability_assessor import CapabilityAssessor, PrerequisiteCheck


class TestPrerequisiteCheck:
    def test_creation(self):
        pc = PrerequisiteCheck(name="docker", available=True)
        assert pc.name == "docker"
        assert pc.available is True


class TestCapabilityAssessor:
    def test_creation(self):
        ca = CapabilityAssessor()
        assert ca is not None

    def test_assess(self):
        ca = CapabilityAssessor()
        result = ca.assess()
        assert isinstance(result, list)
