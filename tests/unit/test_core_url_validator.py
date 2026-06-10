"""Tests for backend.core.url_validator — URLValidator, SSRF protection, allowlists."""
import pytest
from backend.core.url_validator import URLValidator, validate_url, validate_url_or_raise, url_validator


class TestURLValidatorInit:
    def test_has_allowed_hosts(self):
        v = URLValidator()
        assert "localhost" in v.allowed_hosts
        assert "example.com" in v.allowed_hosts

    def test_has_blocked_patterns(self):
        v = URLValidator()
        assert len(v.blocked_patterns) > 0

    def test_allowed_schemes(self):
        v = URLValidator()
        assert "http" in v.allowed_schemes
        assert "https" in v.allowed_schemes


class TestAddRemoveHost:
    def test_add_host(self):
        v = URLValidator()
        v.add_allowed_host("newhost.com")
        assert "newhost.com" in v.allowed_hosts

    def test_remove_host(self):
        v = URLValidator()
        v.remove_allowed_host("localhost")
        assert "localhost" not in v.allowed_hosts


class TestValidate:
    def test_valid_url(self):
        valid, reason = validate_url("http://localhost:8080/test")
        assert valid is True

    def test_example_com(self):
        valid, _ = validate_url("http://example.com/test")
        assert valid is True

    def test_blocked_aws_metadata(self):
        valid, _ = validate_url("http://169.254.169.254/latest/meta-data/")
        assert valid is False

    def test_blocked_gcp_metadata(self):
        valid, _ = validate_url("http://metadata.google.internal/computeMetadata/v1/")
        assert valid is False

    def test_blocked_file_protocol(self):
        valid, _ = validate_url("file:///etc/passwd")
        assert valid is False

    def test_blocked_ftp(self):
        valid, _ = validate_url("ftp://example.com/file")
        assert valid is False

    def test_blocked_gopher(self):
        valid, _ = validate_url("gopher://example.com/")
        assert valid is False

    def test_blocked_ldap(self):
        valid, _ = validate_url("ldap://example.com/")
        assert valid is False

    def test_injection_chars(self):
        valid, _ = validate_url("http://example.com/<script>")
        assert valid is False

    def test_newline_injection(self):
        valid, _ = validate_url("http://example.com/test\ninjected")
        assert valid is False

    def test_private_ip_allowed(self):
        valid, _ = validate_url("http://192.168.1.1/test", allow_private=True)
        assert valid is True

    def test_private_ip_blocked(self):
        valid, _ = validate_url("http://10.0.0.1/test", allow_private=False)
        assert valid is False

    def test_test_domain(self):
        valid, _ = validate_url("http://app.test/test")
        assert valid is True

    def test_unknown_host_rejected(self):
        valid, _ = validate_url("http://unknown-public-host.com/test")
        assert valid is False

    def test_host_docker_internal_rejected_by_default(self):
        """host.docker.internal is no longer in default allowlist for security.
        It must be explicitly added via add_allowed_host() if needed."""
        valid, _ = validate_url("http://host.docker.internal/test")
        assert valid is False
        
        # Can be explicitly allowed
        url_validator.add_allowed_host("host.docker.internal")
        valid, _ = validate_url("http://host.docker.internal/test")
        assert valid is True


class TestValidateOrRaise:
    def test_valid_no_exception(self):
        result = validate_url_or_raise("http://localhost:8080/test")
        assert result is True

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            validate_url_or_raise("file:///etc/passwd")


class TestGlobalValidator:
    def test_singleton(self):
        assert isinstance(url_validator, URLValidator)
