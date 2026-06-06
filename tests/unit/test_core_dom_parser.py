"""Tests for backend.core.dom_parser — DomParser, InteractiveElement, SemanticSnapshot."""
import pytest
from backend.core.dom_parser import DomParser, InteractiveElement, SemanticSnapshot


class TestDomParser:
    def test_init(self):
        dp = DomParser()
        assert dp is not None

    def test_parse_simple_html(self):
        dp = DomParser()
        snap = dp.parse("<html><body><button>Click</button><a href='/link'>Link</a></body></html>")
        assert isinstance(snap, SemanticSnapshot)
        assert len(snap.elements) >= 2

    def test_parse_empty(self):
        dp = DomParser()
        snap = dp.parse("")
        assert isinstance(snap, SemanticSnapshot)

    def test_parse_with_forms(self):
        dp = DomParser()
        html = '<form action="/submit"><input name="user" type="text"><button type="submit">OK</button></form>'
        snap = dp.parse(html)
        assert len(snap.elements) >= 1


class TestSemanticSnapshot:
    def test_has_elements(self):
        snap = SemanticSnapshot(elements=[])
        assert snap.elements == []


class TestInteractiveElement:
    def test_creation(self):
        el = InteractiveElement(tag="button", text="Click", attributes={})
        assert el.tag == "button"
        assert el.text == "Click"
