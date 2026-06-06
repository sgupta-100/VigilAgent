"""Tests for backend.core.memory_manager — MemoryManager."""
import pytest
from backend.core.memory_manager import MemoryManager


class TestMemoryManager:
    def test_creation(self):
        mm = MemoryManager()
        assert mm is not None
        assert isinstance(mm.providers(), list)

    def test_register_provider(self):
        mm = MemoryManager()
        provider = type('MockProvider', (), {'name': 'test_provider'})()
        mm.register(provider)
        assert "test_provider" in mm.providers()
