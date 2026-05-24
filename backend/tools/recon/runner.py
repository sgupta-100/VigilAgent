"""
Alpha V6 Recon Command Runner — Enhanced with guardrails.

Adapted from PentAGI executor pattern: validates before execution,
persists results, and feeds tool outputs to vector store memory.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.core.database import db_manager
from backend.core.queue import ProcessRunner, command_lane
from backend.core.stdout_watchdog import watch_output
from backend.tools.recon.commands import ReconCommand
from backend.tools.recon.guardrails import validate_command, validate_output_path

logger = logging.getLogger("alpha.runner")

# PentAGI-style result size limit (16KB)
DEFAULT_RESULT_SIZE_LIMIT = 16 * 1024


@dataclass
class ReconCommandResult:
    tool_name: str
    phase: str
    status: str  # finished | failed | timeout | skipped | blocked
    exit_code: int
    output_path: str
    stderr: str = ""
    duration_ms: int = 0
    sha256: str = ""
    bytes: int = 0
    skipped_reason: str = ""
    entities_parsed: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class ReconCommandRunner:
    """Runs recon tools as bounded subprocesses with guardrail validation."""

    async def execute(self, command: ReconCommand, *, scan_id: str = "GLOBAL",
                      agent: str = "agent_alpha") -> ReconCommandResult:
        """Execute a validated recon command."""
        # 1. Guardrail validation (adapted from CAI patterns)
        guard = validate_command(command.argv)
        if not guard.allowed:
            logger.warning(f"[GUARDRAIL] Blocked {command.tool_name}: {guard.reason}")
            return ReconCommandResult(
                tool_name=command.tool_name, phase=command.phase,
                status="blocked", exit_code=-1,
                output_path=str(command.output_path),
                skipped_reason=f"guardrail:{guard.reason}")

        # 2. Output path validation
        if not validate_output_path(str(command.output_path)):
            return ReconCommandResult(
                tool_name=command.tool_name, phase=command.phase,
                status="blocked", exit_code=-1,
                output_path=str(command.output_path),
                skipped_reason="output_path_traversal")

        # 3. Check executable availability
        executable = command.argv[0]
        if shutil.which(executable) is None:
            return ReconCommandResult(
                tool_name=command.tool_name, phase=command.phase,
                status="skipped", exit_code=127,
                output_path=str(command.output_path),
                skipped_reason=f"executable_not_on_path:{executable}")

        # 4. Prepare output directory
        command.output_path.parent.mkdir(parents=True, exist_ok=True)
        call_id = f"recon_{command.tool_name}_{hashlib.sha1(str(command.argv).encode()).hexdigest()[:12]}"

        # 5. Register toolcall in database (PentAGI pattern)
        await db_manager.create_toolcall(
            call_id=call_id, scan_id=scan_id,
            tool_name=command.tool_name, agent=agent,
            args={"argv": list(command.argv), "stdin": bool(command.stdin),
                  "output_path": str(command.output_path),
                  "timeout": command.timeout_seconds},
            status="running")

        started = time.time()
        try:
            # 6. Execute through the global CommandLane and ProcessRunner.
            async with command_lane.slot():
                proc_result = await ProcessRunner.run_exec(
                    command.argv,
                    cwd=command.cwd,
                    stdin=command.stdin,
                    no_output_timeout_ms=min(command.timeout_seconds * 1000, 30_000),
                    max_runtime_ms=command.timeout_seconds * 1000,
                )
            if proc_result.timed_out:
                command_lane.total_timed_out += 1
                raise asyncio.TimeoutError()
            stdout = proc_result.stdout
            stderr = proc_result.stderr

            # 7. Process and store output
            watched = await watch_output(stdout, max_bytes=10_000_000)
            command.output_path.write_text(
                watched.content, encoding="utf-8", errors="replace"
            )

            sha256, size = _digest(command.output_path)
            exit_code = proc_result.exit_code or 0
            status = "finished" if exit_code == 0 else "failed"
            duration_ms = int((time.time() - started) * 1000)

            # 9. Truncate large stderr (PentAGI DefaultResultSizeLimit pattern)
            stderr_truncated = stderr[-DEFAULT_RESULT_SIZE_LIMIT:]

            result_data = {
                "output_path": str(command.output_path),
                "stderr": stderr_truncated,
                "truncated": watched.truncated,
                "exit_code": exit_code,
                "output_bytes": size,
            }

            await db_manager.finish_toolcall(
                call_id=call_id, status=status,
                result=result_data,
                error="" if status == "finished" else stderr_truncated,
                duration_ms=duration_ms,
                result_bytes=size, result_sha256=sha256)

            logger.info(f"[RUNNER] {command.tool_name} {status} in {duration_ms}ms ({size} bytes)")

            return ReconCommandResult(
                tool_name=command.tool_name, phase=command.phase,
                status=status, exit_code=exit_code,
                output_path=str(command.output_path),
                stderr=stderr_truncated,
                duration_ms=duration_ms, sha256=sha256, bytes=size,
                metadata={"parser_hint": command.parser_hint})

        except asyncio.TimeoutError:
            duration_ms = int((time.time() - started) * 1000)
            logger.warning(f"[RUNNER] {command.tool_name} timed out after {command.timeout_seconds}s")

            # Try to read partial output
            if command.output_path.exists():
                sha256, size = _digest(command.output_path)
            else:
                sha256, size = "", 0

            await db_manager.finish_toolcall(
                call_id=call_id, status="timeout",
                error=f"timed out after {command.timeout_seconds}s",
                duration_ms=duration_ms)

            return ReconCommandResult(
                command.tool_name, command.phase, "timeout", 124,
                str(command.output_path), duration_ms=duration_ms,
                sha256=sha256, bytes=size,
                metadata={"partial": size > 0})

        except Exception as exc:
            duration_ms = int((time.time() - started) * 1000)
            logger.error(f"[RUNNER] {command.tool_name} failed: {exc}")
            await db_manager.finish_toolcall(
                call_id=call_id, status="failed",
                error=str(exc), duration_ms=duration_ms)
            return ReconCommandResult(
                command.tool_name, command.phase, "failed", 1,
                str(command.output_path), stderr=str(exc),
                duration_ms=duration_ms)

    # Legacy compatibility alias
    async def run(self, command: ReconCommand, *, scan_id: str = "GLOBAL",
                  agent: str = "agent_alpha") -> ReconCommandResult:
        return await self.execute(command, scan_id=scan_id, agent=agent)


def _digest(path: Path) -> tuple[str, int]:
    if not path.exists():
        return "", 0
    content = path.read_bytes()
    return hashlib.sha256(content).hexdigest(), len(content)
