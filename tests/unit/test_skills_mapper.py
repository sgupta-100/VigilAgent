"""Tests for backend.skills.mapper — tool and agent mapping."""
import pytest
from backend.skills.mapper import agents_for_domain, map_required_tools


class TestAgentsForDomain:
    def test_recon_domain(self):
        result = agents_for_domain("recon")
        assert isinstance(result, list)
        assert "alpha" in result

    def test_attack_domain(self):
        result = agents_for_domain("attack")
        assert isinstance(result, list)


class TestMapRequiredTools:
    def test_recon_text(self):
        result = map_required_tools("port scanning and service enumeration")
        assert isinstance(result, list)
        assert len(result) > 0

    def test_web_text(self):
        result = map_required_tools("SQL injection testing on web forms")
        assert isinstance(result, list)
