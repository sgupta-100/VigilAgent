"""Tests for backend.core.mimic — MimicSession."""
import pytest
from backend.core.mimic import MimicSession


class TestMimicSession:
    def test_import(self):
        assert MimicSession is not None
