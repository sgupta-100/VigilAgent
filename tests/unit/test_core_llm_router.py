"""Tests for backend.core.llm_router — LLM routing."""
import pytest


class TestLLMRouter:
    def test_import(self):
        from backend.core.llm_router import LLMRouter
        lr = LLMRouter()
        assert lr is not None
