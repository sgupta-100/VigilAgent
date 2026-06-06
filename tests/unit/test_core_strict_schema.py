"""Tests for backend.core.strict_schema — ensure_strict_json_schema, resolve_ref."""
import pytest
from backend.core.strict_schema import ensure_strict_json_schema, resolve_ref


class TestEnsureStrictJsonSchema:
    def test_adds_additional_properties_false(self):
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}}
        }
        result = ensure_strict_json_schema(schema)
        assert result.get("additionalProperties") is False

    def test_nested_objects(self):
        schema = {
            "type": "object",
            "properties": {
                "nested": {"type": "object", "properties": {"x": {"type": "integer"}}}
            }
        }
        result = ensure_strict_json_schema(schema)
        nested = result["properties"]["nested"]
        assert nested.get("additionalProperties") is False


class TestResolveRef:
    def test_simple_ref(self):
        root = {"definitions": {"Foo": {"type": "string"}}}
        result = resolve_ref(root=root, ref="#/definitions/Foo")
        assert result == {"type": "string"}

    def test_invalid_ref(self):
        root = {}
        result = resolve_ref(root=root, ref="#/nonexistent")
        assert result == {}
