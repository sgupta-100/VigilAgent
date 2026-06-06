"""Tests for backend.core.config — feature_flags, self_awareness_config."""
import os
import pytest
from unittest.mock import patch


class TestFeatureFlagsImport:
    def test_import(self):
        from backend.core.feature_flags import FeatureFlags, get_feature_flags
        ff = get_feature_flags()
        assert ff is not None

    def test_enable_disable(self):
        from backend.core.feature_flags import FeatureFlags
        ff = FeatureFlags()
        ff.enable("test_feature")
        assert ff.is_enabled("test_feature") is True
        ff.disable("test_feature")
        assert ff.is_enabled("test_feature") is False


class TestSelfAwarenessConfig:
    def test_import(self):
        from backend.core.self_awareness_config import SelfAwarenessConfig, get_self_awareness_config
        cfg = get_self_awareness_config()
        assert cfg is not None

    def test_has_settings(self):
        from backend.core.self_awareness_config import get_self_awareness_config
        cfg = get_self_awareness_config()
        assert hasattr(cfg, 'enabled')
