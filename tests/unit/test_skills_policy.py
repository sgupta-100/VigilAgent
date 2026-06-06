"""Tests for backend.skills.policy — RiskClass, PromotionState, requires_approval, can_auto_execute."""
import pytest
from backend.skills.policy import RiskClass, PromotionState, requires_approval, is_disabled, can_auto_execute


class TestRiskClass:
    def test_values(self):
        assert RiskClass.SAFE.value == "safe"
        assert RiskClass.OFFENSIVE.value == "offensive"
        assert RiskClass.NETWORK.value == "network"


class TestPromotionState:
    def test_values(self):
        assert PromotionState.PROTOTYPE.value == "prototype"
        assert PromotionState.STAGED.value == "staged"
        assert PromotionState.PRODUCTION.value == "production"


class TestRequiresApproval:
    def test_safe_no_approval(self):
        assert requires_approval(RiskClass.SAFE) is False

    def test_offensive_needs_approval(self):
        assert requires_approval(RiskClass.OFFENSIVE) is True


class TestIsDisabled:
    def test_safe_not_disabled(self):
        assert is_disabled(RiskClass.SAFE) is False


class TestCanAutoExecute:
    def test_safe_prototype(self):
        assert can_auto_execute(RiskClass.SAFE, PromotionState.PROTOTYPE) is True

    def test_offensive_prototype(self):
        assert can_auto_execute(RiskClass.OFFENSIVE, PromotionState.PROTOTYPE) is False
