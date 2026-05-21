"""Parser for LinkFinder output."""
from __future__ import annotations
import re
from pathlib import Path
from backend.parsers.recon.base import ParsedEntity, safe_lines


def parse_linkfinder_output(path: Path | str) -> list[ParsedEntity]:
    entities: list[ParsedEntity] = []
    seen: set[str] = set()
    for line in safe_lines(path):
        endpoint = line.strip()
        if not endpoint or endpoint in seen: continue
        seen.add(endpoint)
        is_full = endpoint.startswith(("http://", "https://"))
        is_relative = endpoint.startswith("/")
        is_api = bool(re.search(r'/api/|/rest/|/v[0-9]+/', endpoint, re.I))
        entities.append(ParsedEntity(kind="js_endpoint", label=endpoint, confidence=0.7,
            properties={"is_full_url": is_full, "is_relative": is_relative, "is_api": is_api},
            source_tool="linkfinder", phase="http_browser_intelligence"))
    return entities
