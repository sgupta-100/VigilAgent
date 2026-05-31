"""Single-tool stdin test: httprobe and hakrawler."""
import asyncio, os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("VIGILAGENT_RECON_CONTAINER", "reverent_banach")

async def go():
    from backend.core.terminal_engine import terminal_engine
    raw = ROOT / "data" / "scans" / "STDIN-TEST" / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    out = raw / "httprobe.txt"
    res = await terminal_engine.run(
        ["httprobe", "-c", "5", "-p", "http:80", "-p", "http:8080"],
        scan_id="STDIN-TEST",
        agent="harness",
        output_path=out,
        timeout_seconds=30,
        stdin="localhost\nhost.docker.internal\n",
        parser_hint="lines",
    )
    print(f"httprobe status={res.status} exit={res.exit_code} bytes={res.output_bytes} backend={res.backend}")
    print(f"  stdout={res.stdout[:300]!r}")
    print(f"  stderr={res.stderr_tail[:300]!r}")
    print(f"  file_exists={out.exists()} file_size={out.stat().st_size if out.exists() else 0}")

    out2 = raw / "hakrawler.txt"
    res = await terminal_engine.run(
        ["hakrawler", "-d", "2", "-subs", "-insecure"],
        scan_id="STDIN-TEST",
        agent="harness",
        output_path=out2,
        timeout_seconds=30,
        stdin="http://localhost:8080\nhttp://host.docker.internal:8080\n",
        parser_hint="lines",
    )
    print(f"hakrawler status={res.status} exit={res.exit_code} bytes={res.output_bytes} backend={res.backend}")
    print(f"  stdout={res.stdout[:300]!r}")
    print(f"  stderr={res.stderr_tail[:300]!r}")

if __name__ == "__main__":
    asyncio.run(go())
