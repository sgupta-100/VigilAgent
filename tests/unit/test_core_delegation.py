"""Tests for backend.core.delegation_manager — DelegationManager, ChildSpec, sanitize_tools."""
import pytest
from backend.core.delegation_manager import (
    DelegationManager, ChildSpec, ChildResult, sanitize_tools, normalize_specialty,
    make_delegation_manager,
)


class TestSanitizeTools:
    def test_none_input(self):
        assert sanitize_tools(None) == []

    def test_empty_list(self):
        assert sanitize_tools([]) == []

    def test_filters_empty_strings(self):
        result = sanitize_tools(["nmap", "", "nuclei", None])
        assert "nmap" in result
        assert "nuclei" in result
        assert "" not in result
        assert None not in result


class TestNormalizeSpecialty:
    def test_known_specialty(self):
        result = normalize_specialty("recon")
        assert result == "recon"

    def test_unknown_specialty(self):
        result = normalize_specialty("unknown_xyz")
        assert isinstance(result, str)

    def test_none_specialty(self):
        result = normalize_specialty(None)
        assert isinstance(result, str)


class TestChildSpec:
    def test_creation(self):
        spec = ChildSpec(agent_class="AlphaAgent", tools=["nmap"])
        assert spec.agent_class == "AlphaAgent"


class TestChildResult:
    def test_creation(self):
        result = ChildResult(child_id="c1", status="success", data={})
        assert result.child_id == "c1"
        assert result.status == "success"


class TestDelegationManager:
    def test_creation(self):
        dm = DelegationManager()
        assert dm is not None

    def test_make_delegation_manager(self):
        dm = make_delegation_manager()
        assert isinstance(dm, DelegationManager)
