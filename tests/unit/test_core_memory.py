"""Tests for backend.core.memory — DualStoreMemory, cosine_similarity."""
import pytest
from backend.core.memory import DualStoreMemory, cosine_similarity


class TestCosineSimilarity:
    def test_identical_vectors(self):
        assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0

    def test_orthogonal_vectors(self):
        assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0

    def test_empty_vectors(self):
        assert cosine_similarity([], []) == 0.0

    def test_different_lengths(self):
        assert cosine_similarity([1.0], [1.0, 2.0]) == 0.0

    def test_opposite_vectors(self):
        result = cosine_similarity([1.0, 0.0], [-1.0, 0.0])
        assert result == -1.0


class TestDualStoreMemory:
    def test_creation(self):
        dm = DualStoreMemory()
        assert dm is not None
