"""Parser for ffuf JSON output."""
from __future__ import annotations
from pathlib import Path
from backend.parsers.recon.base import ParsedEntity, safe_json_file


def parse_ffuf_json(path: Path | str) -> list[ParsedEntity]:
    entities: list[ParsedEntity] = []
    data = safe_json_file(path)
    results = data.get("results", []) if isinstance(data, dict) else data if isinstance(data, list) else []
    seen: set[str] = set()
    for r in results:
        url = str(r.get("url", r.get("input", {}).get("FUZZ", "")))
        if not url or url in seen: continue
        seen.add(url)
        status = int(r.get("status", 0) or 0)
        length = int(r.get("length", 0) or 0)
        words = int(r.get("words", 0) or 0)
        lines = int(r.get("lines", 0) or 0)
        redir = str(r.get("redirectlocation", ""))
        ct = str(r.get("content-type", r.get("content_type", "")))
        duration = r.get("duration", 0)
        host = str(r.get("host", ""))
        fuzz_input = str(r.get("input", {}).get("FUZZ", "")) if isinstance(r.get("input"), dict) else ""
        entities.append(ParsedEntity(kind="discovered_path", label=url, confidence=0.85,
            properties={"status_code": status, "content_length": length, "words": words,
                         "lines": lines, "redirect": redir, "content_type": ct,
                         "duration_ns": duration, "host": host, "fuzz_input": fuzz_input},
            source_tool="ffuf", phase="directory_route_discovery"))
    return entities
