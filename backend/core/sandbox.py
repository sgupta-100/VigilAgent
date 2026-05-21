import asyncio
import os
import shlex
import uuid
from dataclasses import dataclass
from pathlib import Path

from backend.core.guard_layer import guard_layer
from backend.core.stdout_watchdog import watch_output


@dataclass
class SandboxResult:
    exit_code: int
    stdout: str
    stderr: str
    command: str
    container_id: str | None = None
    truncated: bool = False


class DockerSandbox:
    def __init__(
        self,
        image: str | None = None,
        workspace_root: str | os.PathLike[str] = "scan_states/sandboxes",
        memory: str = "512m",
        cpus: str = "1.0",
        network: str = "none",
    ):
        self.image = image or os.getenv("VULAGENT_SANDBOX_IMAGE", "python:3.12-slim")
        self.workspace_root = Path(workspace_root)
        self.memory = memory
        self.cpus = cpus
        self.network = network

    def workspace_for(self, engagement_id: str) -> Path:
        root = (self.workspace_root / engagement_id).resolve()
        root.mkdir(parents=True, exist_ok=True)
        return root

    async def run(self, command: str, *, engagement_id: str = "GLOBAL", timeout: int = 120) -> SandboxResult:
        guard_layer.assert_safe_text(command, output=True)
        workspace = self.workspace_for(engagement_id)
        container_name = f"vulagent-{engagement_id.lower()}-{uuid.uuid4().hex[:8]}"
        docker_cmd = [
            "docker", "run", "--rm", "--name", container_name,
            "--network", self.network,
            "--memory", self.memory,
            "--cpus", self.cpus,
            "-v", f"{workspace}:/workspace",
            "-w", "/workspace",
            self.image,
            "sh", "-lc", command,
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *docker_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            stdout = stdout_b.decode("utf-8", errors="replace")
            stderr = stderr_b.decode("utf-8", errors="replace")
            watched = await watch_output(stdout)
            return SandboxResult(proc.returncode or 0, watched.content, stderr, command, container_name, watched.truncated)
        except FileNotFoundError:
            return SandboxResult(127, "", "Docker executable not found; sandbox execution unavailable.", command)
        except asyncio.TimeoutError:
            return SandboxResult(124, "", f"Sandbox command timed out after {timeout}s.", command, container_name)


def quote_command(parts: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in parts)
