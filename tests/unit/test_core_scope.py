"""Tests for backend.core.scope — ScopePolicy, ScopeViolation, from_target, allows."""
import pytest
from datetime import datetime, timezone, timedelta
from backend.core.scope import (
    ScopePolicy, ScopeViolation, _parse_iso, _is_private_like,
)


class TestParseIso:
    def test_valid_iso(self):
        dt = _parse_iso("2026-01-15T10:00:00+00:00")
        assert dt is not None
        assert dt.year == 2026

    def test_z_suffix(self):
        dt = _parse_iso("2026-01-15T10:00:00Z")
        assert dt is not None
        assert dt.tzinfo is not None

    def test_none_returns_none(self):
        assert _parse_iso(None) is None

    def test_empty_returns_none(self):
        assert _parse_iso("") is None

    def test_invalid_returns_none(self):
        assert _parse_iso("not-a-date") is None

    def test_naive_gets_utc(self):
        dt = _parse_iso("2026-01-15T10:00:00")
        assert dt is not None
        assert dt.tzinfo == timezone.utc


class TestIsPrivateLike:
    def test_localhost(self):
        assert _is_private_like("localhost") is True

    def test_loopback(self):
        assert _is_private_like("127.0.0.1") is True

    def test_private_range(self):
        assert _is_private_like("192.168.1.1") is True
        assert _is_private_like("10.0.0.1") is True

    def test_public(self):
        assert _is_private_like("example.com") is False
        assert _is_private_like("8.8.8.8") is False

    def test_link_local(self):
        assert _is_private_like("169.254.1.1") is True


class TestScopePolicy:
    def test_from_target(self):
        sp = ScopePolicy.from_target("http://example.com:8080/test")
        assert "example.com" in sp.allowed_hosts
        # Default is now "none" (passive mode) unless ALPHA_EXPLICIT_AUTHORIZATION=true
        assert sp.authorization in ("none", "explicit")

    def test_from_target_no_url(self):
        sp = ScopePolicy.from_target()
        assert sp.allowed_hosts == set()
        assert sp.authorization in ("none", "explicit")

    def test_from_target_with_extra_hosts(self):
        sp = ScopePolicy.from_target("http://a.com", extra_hosts=["b.com", "c.com"])
        assert "a.com" in sp.allowed_hosts
        assert "b.com" in sp.allowed_hosts
        assert "c.com" in sp.allowed_hosts

    def test_default_no_scope(self):
        sp = ScopePolicy()
        assert sp.allowed_hosts == set()
        assert sp.authorization == "none"

    def test_is_authorized_none(self):
        sp = ScopePolicy(authorization="none")
        assert sp.is_authorized() is False

    def test_is_authorized_explicit(self):
        sp = ScopePolicy(authorization="explicit")
        assert sp.is_authorized() is True

    def test_is_authorized_outside_window(self):
        sp = ScopePolicy(
            authorization="explicit",
            window_start=datetime.now(timezone.utc) + timedelta(hours=1)
        )
        assert sp.is_authorized() is False

    def test_is_authorized_within_window(self):
        sp = ScopePolicy(
            authorization="explicit",
            window_start=datetime.now(timezone.utc) - timedelta(hours=1),
            window_end=datetime.now(timezone.utc) + timedelta(hours=1)
        )
        assert sp.is_authorized() is True

    def test_within_window_no_bounds(self):
        sp = ScopePolicy()
        assert sp.within_window() is True


class TestScopePolicyAllows:
    def test_allowed_host(self):
        sp = ScopePolicy(allowed_hosts={"example.com"})
        assert sp.allows("http://example.com/test") is True

    def test_denied_host(self):
        sp = ScopePolicy(allowed_hosts={"example.com"}, denied_hosts={"evil.com"})
        assert sp.allows("http://evil.com") is False

    def test_denied_glob(self):
        sp = ScopePolicy(
            allowed_hosts={"example.com"},
            denied_url_globs=["*/admin/*"]
        )
        assert sp.allows("http://example.com/admin/secret") is False

    def test_wildcard_host(self):
        sp = ScopePolicy(allowed_hosts={"*.example.com"})
        assert sp.allows("http://sub.example.com/test") is True

    def test_cidr_match(self):
        sp = ScopePolicy(allowed_cidrs=["192.168.0.0/16"])
        assert sp.allows("http://192.168.1.100/test") is True

    def test_cidr_no_match(self):
        sp = ScopePolicy(allowed_cidrs=["192.168.0.0/16"])
        assert sp.allows("http://10.0.0.1/test") is False

    def test_empty_host(self):
        sp = ScopePolicy(allowed_hosts={"example.com"})
        assert sp.allows("http:///test") is False

    def test_port_restriction(self):
        sp = ScopePolicy(allowed_hosts={"example.com"}, allowed_ports={80, 443})
        assert sp.allows("http://example.com:8080/test") is False
        assert sp.allows("http://example.com:80/test") is True

    def test_url_glob_match(self):
        sp = ScopePolicy(allowed_url_globs=["http://example.com/api/*"])
        assert sp.allows("http://example.com/api/users") is True
        assert sp.allows("http://example.com/other") is False

    def test_no_allowlist_denies_all(self):
        sp = ScopePolicy()
        assert sp.allows("http://random.com") is False


class TestAssertAllowed:
    def test_allows_safe(self):
        sp = ScopePolicy(allowed_hosts={"example.com"})
        sp.assert_allowed("http://example.com/test", action="request")

    def test_denies_out_of_scope(self):
        sp = ScopePolicy(allowed_hosts={"example.com"})
        with pytest.raises(ScopeViolation):
            sp.assert_allowed("http://evil.com/test")

    def test_denies_active_without_auth(self):
        sp = ScopePolicy(allowed_hosts={"example.com"}, authorization="none")
        with pytest.raises(ScopeViolation):
            sp.assert_allowed("http://example.com/test", action="exploit")

    def test_allows_active_with_auth(self):
        sp = ScopePolicy(allowed_hosts={"example.com"}, authorization="explicit")
        sp.assert_allowed("http://example.com/test", action="exploit")


class TestScopeExtensionCapture:
    def test_empty_allowlist(self):
        sp = ScopePolicy()
        assert sp.allows_extension_capture("session") is False

    def test_in_allowlist(self):
        sp = ScopePolicy(extension_capture_allowlist={"session", "traffic"})
        assert sp.allows_extension_capture("session") is True
        assert sp.allows_extension_capture("unknown") is False


class TestToDict:
    def test_to_dict(self):
        sp = ScopePolicy(allowed_hosts={"a.com"}, authorization="explicit")
        d = sp.to_dict()
        assert d["authorization"] == "explicit"
        assert "a.com" in d["allowed_hosts"]
        assert d["authorized_now"] is True
