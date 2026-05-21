"""
Alpha V6 Test Suite — Parser Tests.

Tests parsers with tiny fixtures to validate normalization.
All function names match the actual parser registry exports.
"""
import json
import pytest
from pathlib import Path

from backend.parsers.recon.subfinder import parse_subfinder_jsonl
from backend.parsers.recon.amass import parse_amass_json
from backend.parsers.recon.httpx import parse_httpx_jsonl
from backend.parsers.recon.dnsx import parse_dnsx_jsonl
from backend.parsers.recon.nuclei import parse_nuclei_jsonl
from backend.parsers.recon.naabu import parse_naabu_jsonl
from backend.parsers.recon.nmap import parse_nmap_xml
from backend.parsers.recon.katana import parse_katana_jsonl
from backend.parsers.recon.ffuf import parse_ffuf_json
from backend.parsers.recon.url_parser import parse_url_lines


class TestSubfinderParser:
    """Subfinder JSONL parser."""

    def test_parse_jsonl(self, tmp_path):
        fixture = tmp_path / "subfinder.jsonl"
        fixture.write_text(
            '{"host":"api.example.com","source":"certspotter"}\n'
            '{"host":"staging.example.com","source":"crtsh"}\n'
            '{"host":"api.example.com","source":"virustotal"}\n',
            encoding="utf-8")
        entities = parse_subfinder_jsonl(str(fixture))
        assert len(entities) >= 2  # Dedupe should merge api.example.com
        labels = [e.label for e in entities]
        assert "api.example.com" in labels
        assert "staging.example.com" in labels
        assert all(e.kind == "subdomain" for e in entities)
        assert all(e.source_tool == "subfinder" for e in entities)

    def test_empty_file(self, tmp_path):
        fixture = tmp_path / "empty.txt"
        fixture.write_text("", encoding="utf-8")
        entities = parse_subfinder_jsonl(str(fixture))
        assert entities == []


class TestHttpxParser:
    """httpx JSONL parser."""

    def test_parse_jsonl(self, tmp_path):
        fixture = tmp_path / "httpx.jsonl"
        fixture.write_text(
            json.dumps({
                "url": "https://api.example.com",
                "status_code": 200,
                "title": "API Gateway",
                "webserver": "nginx",
                "content_length": 1234,
                "technologies": ["nginx", "Express"],
                "host": "93.184.216.34",
                "a": ["93.184.216.34"],
                "favicon_hash": "abc123",
            }) + "\n",
            encoding="utf-8")
        entities = parse_httpx_jsonl(str(fixture))
        assert len(entities) >= 1
        http_services = [e for e in entities if e.kind == "http_service"]
        assert len(http_services) == 1
        assert http_services[0].properties["status_code"] == 200
        assert http_services[0].properties["title"] == "API Gateway"


class TestDnsxParser:
    """dnsx JSONL parser."""

    def test_parse_dns_records(self, tmp_path):
        fixture = tmp_path / "dnsx.jsonl"
        fixture.write_text(
            json.dumps({
                "host": "example.com",
                "a": ["93.184.216.34"],
                "cname": ["cdn.example.com"],
                "mx": ["mail.example.com"],
            }) + "\n",
            encoding="utf-8")
        entities = parse_dnsx_jsonl(str(fixture))
        assert len(entities) >= 1
        kinds = {e.kind for e in entities}
        assert "dns_record" in kinds


class TestNucleiParser:
    """Nuclei JSONL parser."""

    def test_parse_finding(self, tmp_path):
        fixture = tmp_path / "nuclei.jsonl"
        fixture.write_text(
            json.dumps({
                "template-id": "cve-2021-44228",
                "info": {"name": "Log4Shell", "severity": "critical",
                         "description": "Remote code execution via Log4j",
                         "tags": ["cve", "rce"]},
                "matched-at": "https://api.example.com/login",
                "type": "http",
                "curl-command": "curl -H 'X-Api-Version: ${jndi:ldap://x}' ...",
                "extracted-results": ["jndi:ldap"],
            }) + "\n",
            encoding="utf-8")
        entities = parse_nuclei_jsonl(str(fixture))
        assert len(entities) >= 1
        vuln = [e for e in entities if e.kind == "vulnerability_candidate"]
        assert len(vuln) == 1
        assert vuln[0].properties["severity"] == "critical"
        assert vuln[0].properties["template_id"] == "cve-2021-44228"


class TestUrlParser:
    """URL line parser (gau/waybackurls)."""

    def test_parse_urls(self, tmp_path):
        fixture = tmp_path / "urls.txt"
        fixture.write_text(
            "https://example.com/api/v1/users?id=1\n"
            "https://example.com/admin/login\n"
            "https://example.com/static/main.js\n"
            "https://example.com/api/v1/users?id=2\n",
            encoding="utf-8")
        entities = parse_url_lines(str(fixture))
        assert len(entities) >= 3


class TestNaabuParser:
    """Naabu port scanner parser."""

    def test_parse_ports(self, tmp_path):
        fixture = tmp_path / "naabu.jsonl"
        fixture.write_text(
            json.dumps({"host": "93.184.216.34", "port": 80, "protocol": "tcp"}) + "\n"
            + json.dumps({"host": "93.184.216.34", "port": 443, "protocol": "tcp"}) + "\n"
            + json.dumps({"host": "93.184.216.34", "port": 8080, "protocol": "tcp"}) + "\n",
            encoding="utf-8")
        entities = parse_naabu_jsonl(str(fixture))
        assert len(entities) == 3
        assert all(e.kind == "open_port" for e in entities)


class TestKatanaParser:
    """Katana crawler parser."""

    def test_parse_crawled_urls(self, tmp_path):
        fixture = tmp_path / "katana.jsonl"
        fixture.write_text(
            json.dumps({"request": {"url": "https://example.com/login"},
                         "response": {"status_code": 200}}) + "\n"
            + json.dumps({"request": {"url": "https://example.com/api/users"},
                          "response": {"status_code": 403}}) + "\n",
            encoding="utf-8")
        entities = parse_katana_jsonl(str(fixture))
        assert len(entities) >= 2


class TestFfufParser:
    """ffuf brute-force results parser."""

    def test_parse_results(self, tmp_path):
        fixture = tmp_path / "ffuf.json"
        fixture.write_text(json.dumps({
            "results": [
                {"input": {"FUZZ": "admin"}, "url": "https://example.com/admin",
                 "status": 200, "length": 5000, "words": 100, "lines": 50},
                {"input": {"FUZZ": "backup"}, "url": "https://example.com/backup",
                 "status": 403, "length": 300, "words": 20, "lines": 5},
            ]
        }), encoding="utf-8")
        entities = parse_ffuf_json(str(fixture))
        assert len(entities) == 2
        assert all(e.kind == "discovered_path" for e in entities)
