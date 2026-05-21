"""Parser for Cloudlist line output."""
from __future__ import annotations
from pathlib import Path
from backend.parsers.recon.base import ParsedEntity, safe_lines, is_ip_address


def parse_cloudlist_lines(path: Path | str) -> list[ParsedEntity]:
    entities: list[ParsedEntity] = []
    seen: set[str] = set()
    for line in safe_lines(path):
        asset = line.strip()
        if not asset or asset in seen: continue
        seen.add(asset)
        kind = "ip" if is_ip_address(asset) else "cloud_asset"
        entities.append(ParsedEntity(kind=kind, label=asset, confidence=0.8,
            properties={"source": "cloudlist"}, source_tool="cloudlist",
            phase="passive_intelligence"))
    return entities
