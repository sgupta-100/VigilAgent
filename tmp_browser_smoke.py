"""Short smoke test: bring up BrowserOrchestrator and report engine status.

Run as:
    python tmp_browser_smoke.py
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys

os.chdir(r"d:\Antigravity 2\penetration testing system")
sys.path.insert(0, os.getcwd())

# Verbose logging so we can see WHY each engine came up or didn't.
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(name)s | %(message)s",
)


async def main() -> int:
    from backend.core.browser_orchestrator import (
        BrowserOrchestrator, BrowserUnavailable,
    )

    orch = BrowserOrchestrator()
    print("[smoke] calling orch.initialize() ...")
    await orch.initialize()

    status = orch.get_engine_status()
    print("[smoke] engine status:")
    for engine, info in status.items():
        marker = "OK " if info.get("available") else "OFF"
        print(f"  - {marker} {engine}: {info}")

    # Verify graceful no-op when both engines miss (and the actual case here
    # is openclaw on, pinchtab off).
    print("[smoke] resource stats:", orch.get_resource_stats())

    # Quick navigate probe — only if at least one engine is up.
    if status["openclaw"]["available"] or status["pinchtab"]["available"]:
        try:
            print("[smoke] navigate(about:blank) ...")
            res = await orch.navigate("about:blank")
            print("[smoke] navigate result keys:", list(res.keys()) if isinstance(res, dict) else type(res).__name__)
        except BrowserUnavailable as exc:
            print(f"[smoke] BrowserUnavailable as expected: {exc}")
        except Exception as exc:
            print(f"[smoke] navigate raised: {type(exc).__name__}: {exc}")
    else:
        print("[smoke] both engines offline; skipping navigate")

    await orch.close()
    print("[smoke] done")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
