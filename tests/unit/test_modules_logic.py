"""Tests for backend.modules.logic modules — skipper, doppelganger, escalator, tycoon, chronomancer."""
import pytest


class TestLogicModules:
    def test_skipper_import(self):
        from backend.modules.logic.skipper import TheSkipper
        assert TheSkipper is not None

    def test_doppelganger_import(self):
        from backend.modules.logic.doppelganger import Doppelganger
        assert Doppelganger is not None

    def test_escalator_import(self):
        from backend.modules.logic.escalator import TheEscalator
        assert TheEscalator is not None

    def test_tycoon_import(self):
        from backend.modules.logic.tycoon import TheTycoon
        assert TheTycoon is not None

    def test_chronomancer_import(self):
        from backend.modules.logic.chronomancer import Chronomancer
        assert Chronomancer is not None
