"""Tests for backend.core.approval — ApprovalTicket, ApprovalStore."""
import pytest
import time
from backend.core.approval import ApprovalTicket, ApprovalStore


class TestApprovalTicket:
    def test_creation(self):
        t = ApprovalTicket(tool_name="nmap", reason="recon", target_url="http://a.com")
        assert t.tool_name == "nmap"
        assert t.status == "pending"

    def test_approve(self):
        t = ApprovalTicket(tool_name="nmap", reason="recon", target_url="http://a.com")
        t.approve()
        assert t.status == "approved"

    def test_deny(self):
        t = ApprovalTicket(tool_name="nmap", reason="recon", target_url="http://a.com")
        t.deny(reason="too aggressive")
        assert t.status == "denied"
        assert t.deny_reason == "too aggressive"


class TestApprovalStore:
    def test_submit_and_get(self):
        store = ApprovalStore()
        t = ApprovalTicket(tool_name="nmap", reason="recon", target_url="http://a.com")
        store.submit(t)
        retrieved = store.get(t.id)
        assert retrieved is t

    def test_list_pending(self):
        store = ApprovalStore()
        t1 = ApprovalTicket(tool_name="nmap", reason="r1", target_url="http://a.com")
        t2 = ApprovalTicket(tool_name="nuclei", reason="r2", target_url="http://b.com")
        store.submit(t1)
        store.submit(t2)
        t1.approve()
        pending = store.list_pending()
        assert len(pending) == 1
        assert pending[0].tool_name == "nuclei"

    def test_approve_ticket(self):
        store = ApprovalStore()
        t = ApprovalTicket(tool_name="nmap", reason="recon", target_url="http://a.com")
        store.submit(t)
        store.approve(t.id)
        assert t.status == "approved"

    def test_deny_ticket(self):
        store = ApprovalStore()
        t = ApprovalTicket(tool_name="nmap", reason="recon", target_url="http://a.com")
        store.submit(t)
        store.deny(t.id, reason="denied")
        assert t.status == "denied"

    def test_get_nonexistent(self):
        store = ApprovalStore()
        assert store.get("nonexistent") is None
