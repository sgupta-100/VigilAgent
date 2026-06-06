"""Tests for backend.modules.tech.parsers — parse_nmap_xml, parse_nuclei_jsonl, parse_httpx_jsonl."""
import json
import tempfile
import os
import pytest
from backend.modules.tech.parsers import parse_nmap_xml, parse_nuclei_jsonl, parse_httpx_jsonl


class TestParseNmapXml:
    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.xml"
        f.write_text("")
        result = parse_nmap_xml(str(f))
        assert result == []

    def test_valid_xml(self, tmp_path):
        xml = '''<?xml version="1.0"?>
        <nmaprun>
          <host>
            <address addr="192.168.1.1"/>
            <ports>
              <port protocol="tcp" portid="80">
                <state state="open"/>
                <service name="http"/>
              </port>
            </ports>
          </host>
        </nmaprun>'''
        f = tmp_path / "test.xml"
        f.write_text(xml)
        result = parse_nmap_xml(str(f))
        assert isinstance(result, list)


class TestParseNucleiJsonl:
    def test_valid_jsonl(self, tmp_path):
        lines = [
            json.dumps({"template-id": "sqli", "severity": "high", "matched-at": "http://a.com"}),
            json.dumps({"template-id": "xss", "severity": "medium", "matched-at": "http://b.com"}),
        ]
        f = tmp_path / "nuclei.jsonl"
        f.write_text("\n".join(lines))
        result = parse_nuclei_jsonl(str(f))
        assert len(result) == 2

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.jsonl"
        f.write_text("")
        result = parse_nuclei_jsonl(str(f))
        assert result == []


class TestParseHttpxJsonl:
    def test_valid_jsonl(self, tmp_path):
        lines = [
            json.dumps({"url": "http://a.com", "status_code": 200, "title": "Home"}),
            json.dumps({"url": "http://b.com", "status_code": 404, "title": "Not Found"}),
        ]
        f = tmp_path / "httpx.jsonl"
        f.write_text("\n".join(lines))
        result = parse_httpx_jsonl(str(f))
        assert len(result) == 2
