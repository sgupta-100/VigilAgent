"""Tests for backend.ai modules — cortex, gemini, openrouter."""
import pytest


class TestAICortex:
    def test_import(self):
        from backend.ai.cortex import CortexEngine, BayesianWeightMatrix
        assert CortexEngine is not None
        assert BayesianWeightMatrix is not None


class TestAIGemini:
    def test_import(self):
        from backend.ai.gemini import GeminiClient
        assert GeminiClient is not None


class TestAIOpenRouter:
    def test_import(self):
        from backend.ai.openrouter import OpenRouterClient
        assert OpenRouterClient is not None
