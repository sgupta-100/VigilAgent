import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Callable, Awaitable


MAX_TOOL_OUTPUT_BYTES = 16 * 1024


@dataclass
class WatchdogResult:
    content: str
    truncated: bool
    original_bytes: int
    sha256: str
    summary: str = ""


def _fallback_summary(text: str, limit: int) -> str:
    lines = text.splitlines()
    head = " ".join(line.strip() for line in lines[:8] if line.strip())
    status_codes = sorted(set(re.findall(r"\b[1-5][0-9]{2}\b", text)))[:12]
    urls = re.findall(r"https?://[^\s\"'<>]+|/[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+", text)
    parts = []
    if status_codes:
        parts.append(f"Observed HTTP/status-like codes: {', '.join(status_codes)}.")
    if urls:
        parts.append(f"Sample paths: {', '.join(urls[:8])}.")
    if head:
        parts.append(f"Leading content: {head[:600]}")
    parts.append(f"Original output exceeded {limit} bytes and was truncated before LLM ingestion.")
    return " ".join(parts)


async def watch_output(
    output: Any,
    *,
    max_bytes: int = MAX_TOOL_OUTPUT_BYTES,
    summarizer: Callable[[str], Awaitable[str]] | None = None,
) -> WatchdogResult:
    text = output if isinstance(output, str) else json.dumps(output, default=str)
    encoded = text.encode("utf-8", errors="replace")
    digest = hashlib.sha256(encoded).hexdigest()
    if len(encoded) <= max_bytes:
        return WatchdogResult(text, False, len(encoded), digest)

    head = encoded[: max_bytes // 2].decode("utf-8", errors="replace")
    tail = encoded[-max_bytes // 2 :].decode("utf-8", errors="replace")
    summary = ""
    if summarizer:
        try:
            summary = await summarizer(text)
        except Exception:
            summary = ""
    if not summary:
        summary = _fallback_summary(text, max_bytes)
    guarded = (
        "[OUTPUT_TRUNCATED_BY_WATCHDOG]\n"
        f"original_bytes={len(encoded)} sha256={digest}\n"
        f"summary={summary}\n\n"
        "[HEAD]\n"
        f"{head}\n\n"
        "[TAIL]\n"
        f"{tail}"
    )
    return WatchdogResult(guarded, True, len(encoded), digest, summary)

