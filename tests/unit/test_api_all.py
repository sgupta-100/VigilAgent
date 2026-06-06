"""Tests for backend.api modules — defense, socket_manager, endpoints."""
import pytest


class TestAPIDefense:
    def test_import(self):
        from backend.api.defense import analyze_threat
        assert callable(analyze_threat)


class TestSocketManager:
    def test_import(self):
        from backend.api.socket_manager import SocketManager
        assert SocketManager is not None

    def test_get_display_limit(self):
        from backend.api.socket_manager import get_display_limit
        limit = get_display_limit(100)
        assert isinstance(limit, int)
        assert limit > 0


class TestAPIEndpoints:
    def test_ai_import(self):
        from backend.api.endpoints.ai import generate_mutations
        assert callable(generate_mutations)

    def test_attack_import(self):
        from backend.api.endpoints.attack import fire_attack
        assert callable(fire_attack)

    def test_code_analysis_import(self):
        from backend.api.endpoints.code_analysis import analyze_code
        assert callable(analyze_code)

    def test_data_import(self):
        from backend.api.endpoints.data import list_items
        assert callable(list_items)

    def test_runtime_import(self):
        from backend.api.endpoints.runtime import list_tools
        assert callable(list_tools)

    def test_skills_import(self):
        from backend.api.endpoints.skills import list_skills
        assert callable(list_skills)

    def test_bridge_import(self):
        from backend.api.endpoints.bridge import bridge_session
        assert callable(bridge_session)
