from __future__ import annotations

import inspect
import json
import time
import uuid
from dataclasses import dataclass
from typing import Any

from backend.core.approval import approval_store
from backend.core.database import db_manager
from backend.core.guard_layer import PromptInjectionBlocked, guard_layer
from backend.core.memory import memory_store
from backend.core.stdout_watchdog import watch_output
from backend.core.telemetry import telemetry
from backend.core.tool_registry import ToolDefinition, tool_registry
from backend.core.tool_types import BarrierException
from backend.core.queue import command_lane
from backend.core.content_boundary import content_boundary
import logging

logger = logging.getLogger(__name__)


@dataclass
class ToolExecutionResult:
    call_id: str
    tool_name: str
    status: str
    result: Any = None
    error: str = ""
    duration_ms: int = 0
    truncated: bool = False
    approval_id: str = ""


class ToolExecutor:
    def __init__(self, registry=tool_registry) -> None:
        self.registry = registry

    async def execute(
        self,
        tool_name: str,
        args: dict[str, Any] | None = None,
        *,
        scan_id: str = "GLOBAL",
        agent: str = "system",
        approval_id: str | None = None,
        call_id: str | None = None,
    ) -> ToolExecutionResult:
        args = args or {}
        call_id = call_id or f"call_{uuid.uuid4().hex[:16]}"
        started = time.time()
        definition = self.registry.get(tool_name)

        with telemetry.span("tool.execute", kind="tool", scan_id=scan_id, tool_name=tool_name, agent=agent, call_id=call_id):
            try:
                guard_layer.assert_safe_text(json.dumps(args, default=str))
            except PromptInjectionBlocked as exc:
                await db_manager.create_toolcall(
                    call_id=call_id, scan_id=scan_id, tool_name=tool_name,
                    agent=agent, args=args, status="blocked", error=str(exc),
                )
                return ToolExecutionResult(call_id, tool_name, "blocked", error=str(exc))

            await db_manager.create_toolcall(
                call_id=call_id, scan_id=scan_id, tool_name=tool_name,
                agent=agent, args=args, status="running",
            )

            if (definition.requires_approval or definition.mutates_state) and not approval_store.is_approved(approval_id):
                reason = f"Tool '{tool_name}' requires approval before execution."
                ticket = approval_store.request(scan_id=scan_id, tool_name=tool_name, reason=reason, payload=args)
                await db_manager.create_approval(
                    approval_id=ticket.id, scan_id=scan_id, tool_name=tool_name,
                    reason=reason, payload=args, status="pending",
                )
                await db_manager.finish_toolcall(call_id=call_id, status="approval_required", result={"approval_id": ticket.id})
                return ToolExecutionResult(call_id, tool_name, "approval_required", approval_id=ticket.id)

            try:
                async with command_lane.slot():
                    raw_result = await self._call(definition, args, scan_id=scan_id, agent=agent)
                    
                watched = await watch_output(raw_result) if definition.summarize_result else await watch_output(raw_result, max_bytes=10**9)
                guard_layer.assert_safe_text(watched.content, output=True)
                
                result: Any = watched.content
                if definition.store_result:
                    result = content_boundary.wrap_scan_output(tool_name, str(result))
                    
                duration_ms = int((time.time() - started) * 1000)
                logger.info(f"CommandLane telemetry: {command_lane.telemetry}")
                duration_ms = int((time.time() - started) * 1000)
                await db_manager.finish_toolcall(
                    call_id=call_id, status="finished", result=result, duration_ms=duration_ms,
                    result_bytes=watched.original_bytes, result_sha256=watched.sha256,
                )
                if definition.store_result:
                    memory_store.remember_semantic({
                        "memory_type": "tool_result",
                        "tool_name": tool_name,
                        "scan_id": scan_id,
                        "content": str(result)[:8000],
                        "vector": [],
                    })
                return ToolExecutionResult(call_id, tool_name, "finished", result=result, duration_ms=duration_ms, truncated=watched.truncated)
            except BarrierException as exc:
                duration_ms = int((time.time() - started) * 1000)
                await db_manager.finish_toolcall(call_id=call_id, status="approval_required", result=exc.payload, duration_ms=duration_ms)
                return ToolExecutionResult(call_id, tool_name, "approval_required", error=exc.reason, duration_ms=duration_ms, approval_id=exc.payload.get("approval_id", ""))
            except Exception as exc:
                duration_ms = int((time.time() - started) * 1000)
                await db_manager.finish_toolcall(call_id=call_id, status="failed", error=str(exc), duration_ms=duration_ms)
                return ToolExecutionResult(call_id, tool_name, "failed", error=str(exc), duration_ms=duration_ms)

    async def _call(self, definition: ToolDefinition, args: dict[str, Any], *, scan_id: str, agent: str) -> Any:
        if definition.handler is None:
            raise RuntimeError(f"Tool '{definition.name}' has no handler")
        kwargs = dict(args)
        sig = inspect.signature(definition.handler)
        if "scan_id" in sig.parameters and "scan_id" not in kwargs:
            kwargs["scan_id"] = scan_id
        if "agent" in sig.parameters and "agent" not in kwargs:
            kwargs["agent"] = agent
        result = definition.handler(**kwargs)
        if inspect.isawaitable(result):
            return await result
        return result


tool_executor = ToolExecutor()
