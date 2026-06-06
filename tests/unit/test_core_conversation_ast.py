"""Tests for backend.core.conversation_ast — BodyPair, ChainSection, ConversationAST, message_size."""
import pytest
from backend.core.conversation_ast import BodyPair, ChainSection, ConversationAST, message_size


class TestMessageSize:
    def test_simple_message(self):
        msg = {"role": "user", "content": "hello"}
        size = message_size(msg)
        assert size > 0

    def test_empty_message(self):
        msg = {}
        size = message_size(msg)
        assert size >= 0


class TestBodyPair:
    def test_creation(self):
        bp = BodyPair(body="test body", size=10)
        assert bp.body == "test body"
        assert bp.size == 10


class TestChainSection:
    def test_creation(self):
        cs = ChainSection(section_id="s1", pairs=[])
        assert cs.section_id == "s1"


class TestConversationAST:
    def test_creation(self):
        ast = ConversationAST()
        assert ast is not None

    def test_from_messages(self):
        messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ]
        ast = ConversationAST.from_messages(messages)
        assert ast is not None
