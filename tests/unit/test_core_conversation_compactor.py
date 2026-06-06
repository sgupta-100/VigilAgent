"""Tests for backend.core.conversation_compactor — compact_messages."""
import pytest
from backend.core.conversation_compactor import compact_messages


class TestCompactMessages:
    def test_short_messages(self):
        messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ]
        result = compact_messages(messages, max_tokens=10000)
        assert isinstance(result, list)

    def test_empty_messages(self):
        result = compact_messages([], max_tokens=10000)
        assert result == []
