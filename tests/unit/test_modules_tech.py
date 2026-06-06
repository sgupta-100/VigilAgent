"""Tests for backend.modules.tech modules — sqli, xss, lfi, command_injection, fuzzer, http_client, auth_bypass."""
import pytest


class TestTechModules:
    def test_sqli_import(self):
        from backend.modules.tech.sqli import SQLInjectionProbe
        assert SQLInjectionProbe is not None

    def test_xss_import(self):
        from backend.modules.tech.xss import XSSProbe
        assert XSSProbe is not None

    def test_lfi_import(self):
        from backend.modules.tech.lfi import FileInclusionProbe
        assert FileInclusionProbe is not None

    def test_command_injection_import(self):
        from backend.modules.tech.command_injection import CommandInjectionProbe
        assert CommandInjectionProbe is not None

    def test_fuzzer_import(self):
        from backend.modules.tech.fuzzer import APIFuzzer
        assert APIFuzzer is not None

    def test_http_client_import(self):
        from backend.modules.tech.http_client import HTTPRecord, BoundedHTTPHistory, ReplayHTTPClient
        assert HTTPRecord is not None

    def test_auth_bypass_import(self):
        from backend.modules.tech.auth_bypass import AuthBypassTester
        assert AuthBypassTester is not None
