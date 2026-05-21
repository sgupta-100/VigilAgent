"""Parser for gowitness JSON output."""
from __future__ import annotations
from pathlib import Path
from backend.parsers.recon.base import ParsedEntity, safe_json_file


def parse_gowitness_json(path: Path | str) -> list[ParsedEntity]:
    entities: list[ParsedEntity] = []
    data = safe_json_file(path)
    results = data if isinstance(data, list) else data.get("results", []) if isinstance(data, dict) else []
    for r in results:
        url = str(r.get("url", r.get("final_url", "")))
        if not url: continue
        screenshot = str(r.get("filename", r.get("screenshot", "")))
        title = str(r.get("title", ""))
        status = int(r.get("response_code", r.get("status_code", 0)) or 0)
        entities.append(ParsedEntity(kind="visual_artifact", label=url, confidence=0.9,
            properties={"screenshot_file": screenshot, "title": title, "status_code": status},
            source_tool="gowitness", phase="visual_documentation"))
    return entities
