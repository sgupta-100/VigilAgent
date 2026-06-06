"""Tests for backend.core.tool_types — ToolType, require_barrier, enforce_state_change_barrier."""
import pytest
from backend.core.tool_types import (
    ToolType, BarrierException, get_tool_type, require_barrier,
    enforce_state_change_barrier, tools_by_type, is_barrier_tool,
)


class TestToolType:
    def test_enum_values(self):
        assert ToolType.RECON.value == "recon"
        assert ToolType.EXPLOIT.value == "exploit"
        assert ToolType.VALIDATE.value == "validate"


class TestGetToolType:
    def test_known_tools(self):
        assert get_tool_type("nmap") == ToolType.RECON
        assert get_tool_type("sqlmap") == ToolType.EXPLOIT
        assert get_tool_type("nuclei") == ToolType.VALIDATE

    def test_unknown_tool(self):
        result = get_tool_type("unknown_tool_xyz")
        assert isinstance(result, ToolType)


class TestRequireBarrier:
    def test_no_raise_for_non_barrier(self):
        require_barrier("nmap", reason="recon")

    def test_raises_for_barrier_tool(self):
        with pytest.raises(BarrierException):
            require_barrier("sqli", reason="attack", payload={"url": "http://x"})


class TestEnforceStateChangeBarrier:
    def test_approved_passes(self):
        enforce_state_change_barrier("POST", approved=True, url="http://a.com")

    def test_not_approved_raises(self):
        with pytest.raises(BarrierException):
            enforce_state_change_barrier("POST", approved=False, url="http://a.com")


class TestIsBarrierTool:
    def test_barrier_tool(self):
        assert is_barrier_tool("sqli") is True

    def test_non_barrier_tool(self):
        assert is_barrier_tool("nmap") is False


class TestToolsByType:
    def test_recon_tools(self):
        tools = tools_by_type(ToolType.RECON)
        assert isinstance(tools, list)
        assert "nmap" in tools

    def test_exploit_tools(self):
        tools = tools_by_type(ToolType.EXPLOIT)
        assert isinstance(tools, list)
