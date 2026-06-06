"""Tests for backend.core.protocol — Vulnerability, ResultPacket serialization and edge cases."""
import pytest
from backend.core.protocol import (
    TaskPriority, AgentStatus, AgentID, ModuleConfig,
    TaskTarget, JobPacket, Vulnerability, ResultPacket,
)


class TestVulnerabilityEdgeCases:
    def test_empty_fields(self):
        v = Vulnerability(name="", severity="", description="", evidence="")
        assert v.name == ""

    def test_long_description(self):
        v = Vulnerability(name="XSS", severity="HIGH", description="x" * 5000, evidence="e")
        assert len(v.description) == 5000


class TestResultPacketEdgeCases:
    def test_empty_data(self):
        rp = ResultPacket(
            job_id="j1", source_agent=AgentID.ALPHA, status="SUCCESS",
            execution_time_ms=0, data={}
        )
        assert rp.data == {}

    def test_many_vulns(self):
        vulns = [Vulnerability(name=f"v{i}", severity="HIGH", description="d", evidence="e") for i in range(50)]
        rp = ResultPacket(
            job_id="j1", source_agent=AgentID.BETA, status="VULN_FOUND",
            execution_time_ms=100, data={}, vulnerabilities=vulns
        )
        assert len(rp.vulnerabilities) == 50

    def test_json_serializable(self):
        rp = ResultPacket(
            job_id="j1", source_agent=AgentID.ALPHA, status="SUCCESS",
            execution_time_ms=100.5, data={"key": "val"},
            vulnerabilities=[Vulnerability(name="XSS", severity="HIGH", description="d", evidence="e")]
        )
        # Should not raise
        d = rp.model_dump()
        assert d["job_id"] == "j1"
        assert isinstance(d["vulnerabilities"], list)


class TestJobPacketEdgeCases:
    def test_json_roundtrip(self):
        jp = JobPacket(
            target=TaskTarget(url="http://x.com"),
            config=ModuleConfig(module_id="m", agent_id=AgentID.ALPHA, params={"a": 1})
        )
        d = jp.model_dump()
        jp2 = JobPacket(**d)
        assert jp2.id == jp.id
        assert jp2.config.params == {"a": 1}
