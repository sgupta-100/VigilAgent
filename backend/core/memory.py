import json
import logging
import math
import os
import re
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("DualStoreMemory")


def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    dot = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


class DualStoreMemory:
    """
    CAI-style memory split:
    - episodic: per-scan facts and tool outputs
    - semantic: cross-scan verified techniques and reusable patterns
    """

    def __init__(self, root: str | os.PathLike[str] = "brain"):
        self.root = Path(root)
        self.episodic_dir = self.root / "episodes"
        self.semantic_file = self.root / "semantic_patterns.json"
        self.notifications_file = self.root / "notifications.json"
        self.episodic_dir.mkdir(parents=True, exist_ok=True)
        self.root.mkdir(parents=True, exist_ok=True)
        self._ensure_json_list(self.semantic_file)
        self._ensure_json_list(self.notifications_file)

    def _ensure_json_list(self, path: Path) -> None:
        if not path.exists():
            path.write_text("[]", encoding="utf-8")

    def _read_list(self, path: Path) -> list[dict[str, Any]]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.debug("DualStoreMemory: failed to read %s (%s), returning empty list", path, exc)
            return []

    def _write_list(self, path: Path, rows: list[dict[str, Any]]) -> None:
        path.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    def _episode_file(self, scan_id: str) -> Path:
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", scan_id or "GLOBAL")
        return self.episodic_dir / f"{safe}.json"

    def remember_episode(self, scan_id: str, event: dict[str, Any]) -> None:
        path = self._episode_file(scan_id)
        self._ensure_json_list(path)
        rows = self._read_list(path)
        rows.append({"timestamp": time.time(), **event})
        self._write_list(path, rows[-1000:])

    def remember_semantic(self, record: dict[str, Any]) -> None:
        rows = self._read_list(self.semantic_file)
        rows.append({"timestamp": time.time(), **record})
        self._write_list(self.semantic_file, rows[-5000:])

    def remember_notification(self, scan_id: str, message: str, payload: dict[str, Any] | None = None) -> None:
        rows = self._read_list(self.notifications_file)
        rows.append({"timestamp": time.time(), "scan_id": scan_id, "message": message, "payload": payload or {}})
        self._write_list(self.notifications_file, rows[-500:])

    def pop_notifications(self, scan_id: str) -> list[dict[str, Any]]:
        rows = self._read_list(self.notifications_file)
        matched = [row for row in rows if row.get("scan_id") in {scan_id, "GLOBAL"}]
        remaining = [row for row in rows if row not in matched]
        self._write_list(self.notifications_file, remaining)
        return matched

    def recall_semantic(self, query_vector: list[float], top_k: int = 3, threshold: float = 0.3) -> list[dict[str, Any]]:
        rows = self._read_list(self.semantic_file)
        scored = []
        for row in rows:
            score = cosine_similarity(query_vector, row.get("vector", []))
            if score >= threshold:
                scored.append((score, row))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [{**row, "similarity": score} for score, row in scored[:top_k]]


memory_store = DualStoreMemory()
