"""Tests for backend.core.feature_flags — FeatureFlags."""
import os
import pytest
from unittest.mock import patch
from backend.core.feature_flags import FeatureFlags, get_feature_flags


class TestFeatureFlags:
    def test_default_flags(self):
        ff = FeatureFlags()
        # Should have some default flags
        assert isinstance(ff._flags, dict)

    def test_is_enabled(self):
        ff = FeatureFlags()
        # Test with a known flag
        result = ff.is_enabled("nonexistent_flag", default=False)
        assert result is False

    def test_is_enabled_default_true(self):
        ff = FeatureFlags()
        result = ff.is_enabled("nonexistent_flag", default=True)
        assert result is True

    def test_enable_disable(self):
        ff = FeatureFlags()
        ff.enable("test_flag")
        assert ff.is_enabled("test_flag") is True
        ff.disable("test_flag")
        assert ff.is_enabled("test_flag") is False

    def test_toggle(self):
        ff = FeatureFlags()
        initial = ff.is_enabled("toggle_flag", default=False)
        ff.toggle("toggle_flag")
        assert ff.is_enabled("toggle_flag") != initial


class TestGlobalFeatureFlags:
    def test_get_feature_flags(self):
        ff = get_feature_flags()
        assert isinstance(ff, FeatureFlags)
