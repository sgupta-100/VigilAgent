from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.core.approval import approval_store
from backend.core.knowledge_graph import knowledge_graph
from backend.core.telemetry import telemetry
from backend.core.tool_executor import tool_executor
from backend.core.tool_registry import tool_registry

router = APIRouter(prefix="/runtime", tags=["runtime"])


class ToolRunRequest(BaseModel):
    tool_name: str
    args: dict = Field(default_factory=dict)
    scan_id: str = "GLOBAL"
    agent: str = "api"
    approval_id: str | None = None


@router.get("/tools")
async def list_tools():
    return {"tools": tool_registry.schemas()}


@router.post("/tools/run")
async def run_tool(payload: ToolRunRequest):
    result = await tool_executor.execute(
        payload.tool_name,
        payload.args,
        scan_id=payload.scan_id,
        agent=payload.agent,
        approval_id=payload.approval_id,
    )
    return result.__dict__


@router.get("/approvals")
async def list_approvals(scan_id: str | None = None):
    return {"approvals": [ticket.__dict__ for ticket in approval_store.pending(scan_id)]}


@router.post("/approvals/{approval_id}/approve")
async def approve(approval_id: str):
    try:
        return approval_store.approve(approval_id).__dict__
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown approval id")


@router.post("/approvals/{approval_id}/deny")
async def deny(approval_id: str):
    try:
        return approval_store.deny(approval_id).__dict__
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown approval id")


@router.get("/graph")
async def graph_stats():
    return knowledge_graph.stats()


@router.get("/telemetry")
async def recent_telemetry(limit: int = 100):
    return {"spans": telemetry.recent(limit)}
