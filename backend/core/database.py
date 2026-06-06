import asyncio
import logging
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from supabase import create_client, Client
import redis.asyncio as aioredis
from backend.core.config import settings

logger = logging.getLogger("ELITE-DB")

class EliteDBManager:
    """
    The Single Source of Truth Manager for the Vulagent Scanner.
    Coordinates distributed state across Supabase (Persistence) and Redis (Hot Cache/Locking).
    """
    def __init__(self):
        self.supabase_url = settings.SUPABASE_URL
        self.supabase_key = settings.SUPABASE_KEY
        self.redis_url = settings.REDIS_URL
        
        self.supabase: Optional[Client] = None
        self.redis: Optional[aioredis.Redis] = None
        self._initialized = False

    async def initialize(self):
        """Lazy initialization of cloud/cache connections."""
        if self._initialized:
            return

        try:
            # 1. Supabase Initialization
            if self.supabase_url and self.supabase_key:
                self.supabase = create_client(self.supabase_url, self.supabase_key)
                logger.info("ELITE-DB: Supabase Connection Active ✓")
            
            # 2. Redis Initialization
            if self.redis_url:
                try:
                    temp_redis = aioredis.from_url(self.redis_url, decode_responses=True)
                    await temp_redis.ping()
                    self.redis = temp_redis
                    logger.info("ELITE-DB: Redis Distributed Cache Active ✓")
                except Exception as redis_e:
                    logger.warning(f"ELITE-DB: Redis unavailable, falling back to local caching. ({redis_e})")
                    self.redis = None
            
            self._initialized = True
        except Exception as e:
            logger.error(f"ELITE-DB Initialization Failed: {e}")
            # MED-04: Don't set _initialized=True on failure — allow retry

    @staticmethod
    async def _run_sync(fn, *args, _timeout: float = 30.0, **kwargs):
        """Run a blocking call (e.g. supabase-py's HTTPS .execute()) on a worker
        thread so it cannot stall the event loop. The Supabase client is
        synchronous; without this, every recon entity/toolcall upsert blocks
        the entire hive (Sigma/Beta/Gamma response times spiral, the
        recon-complete handoff misses its deadline). Architecture §29.13:
        execution must not block the orchestrator.

        HIGH-03: Wrapped with ``asyncio.wait_for`` so a stalled thread
        cannot hang the event loop indefinitely."""
        return await asyncio.wait_for(
            asyncio.to_thread(fn, *args, **kwargs),
            timeout=_timeout,
        )

    # --- 1. VULNERABILITY MANAGEMENT (Intelligence) ---

    async def report_vulnerability(self, scan_id: str, endpoint: str, vuln_type: str, severity: str, evidence: Dict[str, Any], validated_by: str) -> Optional[str]:
        """
        Reports a verified vulnerability with strict deduplication.
        Uses a hash-based hot-cache in Redis before performing the Supabase UPSERT.
        """
        if not self.supabase: return None
        
        # 1. Generate Deduplication Signature
        signature = f"vuln:{scan_id}:{endpoint}:{vuln_type}"
        
        # 2. Check Redis Hot-Cache (O(1))
        if self.redis:
            if await self.redis.get(signature):
                return "CACHED"

        # 3. Suppress duplicates in Supabase (O(log n)) using ON CONFLICT logic
        data = {
            "scan_id": scan_id,
            "endpoint": endpoint,
            "vuln_type": vuln_type,
            "severity": severity,
            "evidence": evidence,
            "validated_by": validated_by,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        try:
            # Perform upsert based on the unique constraint (scan_id, endpoint, vuln_type)
            result = await self._run_sync(
                lambda d=data: self.supabase.table("vulnerabilities")
                    .upsert(d, on_conflict="scan_id,endpoint,vuln_type").execute())

            if result.data:
                vuln_id = result.data[0]["id"]
                # Update Hot-Cache for 1 hour to prevent redundant writes
                if self.redis:
                    await self.redis.set(signature, vuln_id, ex=3600)
                return vuln_id
        except Exception as e:
            logger.error(f"Failed to report vulnerability to Supabase: {e}")
        
        return None

    # --- 2. DISTRIBUTED TASK MANAGEMENT (Coordination) ---

    async def acquire_task_lock(self, task_id: str, worker_id: str) -> bool:
        """
        Attempts to acquire a distributed lock for a task.
        Implementation: Redis SETNX (Atomic) + Supabase Status Update.
        """
        lock_key = f"lock:task:{task_id}"
        
        # 1. Atomic Redis Lock (expires in 10 minutes case worker crashes)
        if self.redis:
            locked = await self.redis.set(lock_key, worker_id, nx=True, ex=600)
            if not locked:
                return False

        if not self.supabase:
            # No persistent ledger — Redis-only lock is authoritative.
            return True

        # 2. Sync State to Supabase
        try:
            data = {
                "status": "RUNNING",
                "locked_by": worker_id,
                "lock_time": datetime.now(timezone.utc).isoformat()
            }
            result = await self._run_sync(
                lambda: self.supabase.table("distributed_tasks").update(data)
                    .eq("id", task_id).eq("status", "PENDING").execute())

            if not result.data:
                # Task was already claimed or moved state
                if self.redis: await self.redis.delete(lock_key)
                return False
            
            return True
        except Exception as e:
            logger.error(f"Supabase task lock failed: {e}")
            if self.redis: await self.redis.delete(lock_key)
            return False

    async def complete_task(self, task_id: str, status: str = "COMPLETED"):
        """Releases the lock and updates task status."""
        lock_key = f"lock:task:{task_id}"
        if self.redis:
            await self.redis.delete(lock_key)
        if not self.supabase:
            return
        try:
            await self._run_sync(
                lambda: self.supabase.table("distributed_tasks").update({
                    "status": status,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }).eq("id", task_id).execute())
        except Exception as e:
            logger.error(f"Failed to complete task {task_id}: {e}")

    # --- 3. BATCH OPERATIONS (Optimization) ---

    async def create_tasks_batch(self, tasks: List[Dict[str, Any]]):
        """Inserts multiple tasks in a single Supabase request."""
        if not self.supabase or not tasks: return
        try:
            await self._run_sync(
                lambda: self.supabase.table("distributed_tasks").insert(tasks).execute())
        except Exception as e:
            logger.error(f"Batch task creation failed: {e}")

    # --- 4. EXPLOIT & REMEDIATION ( Intelligence ) ---

    async def log_exploit_result(self, vuln_id: str, result: Dict[str, Any]):
        """Logs the final evidence of a successful exploit."""
        if not self.supabase: return
        try:
            await self._run_sync(
                lambda: self.supabase.table("exploit_results").insert({
                    "vuln_id": vuln_id,
                    "payload": result.get("payload", "N/A"),
                    "worker_id": result.get("worker_id", "local"),
                    "status": result.get("status", "EXPLOITED"),
                    "response_dump": result.get("response", ""),
                    "execution_time_ms": result.get("time_ms", 0)
                }).execute())
        except Exception as e:
            logger.error(f"Failed to log exploit result: {e}")

    # --- 5. QUERY HELPERS ---

    async def get_vulnerabilities(self, scan_id: str) -> List[Dict[str, Any]]:
        """Fetch all vulnerabilities for a given scan from Supabase."""
        if not self.supabase:
            return []
        try:
            result = await self._run_sync(
                lambda: self.supabase.table("vulnerabilities").select("*")
                    .eq("scan_id", scan_id).execute())
            return result.data or []
        except Exception as e:
            logger.error(f"Failed to fetch vulnerabilities for scan {scan_id}: {e}")
            return []

    async def store_scan_episode(self, scan_id: str, event_type: str, payload: Dict[str, Any]):
        if not self.supabase:
            return None
        try:
            result = await self._run_sync(
                lambda: self.supabase.table("scan_episodes").insert({
                    "scan_id": scan_id,
                    "event_type": event_type,
                    "payload": payload,
                }).execute())
            return result.data[0]["id"] if result.data else None
        except Exception as e:
            logger.debug(f"Failed to store scan episode: {e}")
            return None

    async def store_semantic_memory(
        self,
        *,
        memory_type: str,
        content: str,
        endpoint_pattern: str = "",
        vuln_type: str = "",
        metadata: Dict[str, Any] | None = None,
        embedding: List[float] | None = None,
        confidence: float = 0.0,
    ):
        if not self.supabase:
            return None
        try:
            result = await self._run_sync(
                lambda: self.supabase.table("semantic_memory").insert({
                    "memory_type": memory_type,
                    "endpoint_pattern": endpoint_pattern,
                    "vuln_type": vuln_type,
                    "content": content,
                    "metadata": metadata or {},
                    "embedding": embedding,
                    "confidence": confidence,
                }).execute())
            return result.data[0]["id"] if result.data else None
        except Exception as e:
            logger.debug(f"Failed to store semantic memory: {e}")
            return None

    async def create_recon_run(
        self,
        *,
        scan_id: str,
        target: str,
        mode: str,
        scope: Dict[str, Any],
        artifact_root: str,
        status: str = "running",
    ):
        if not self.supabase:
            return None
        try:
            result = await self._run_sync(
                lambda: self.supabase.table("recon_runs").upsert({
                    "scan_id": scan_id,
                    "target": target,
                    "mode": mode,
                    "scope": scope,
                    "artifact_root": artifact_root,
                    "status": status,
                    "started_at": datetime.now(timezone.utc).isoformat(),
                }, on_conflict="scan_id").execute())
            return result.data[0]["scan_id"] if result.data else scan_id
        except Exception as e:
            logger.debug(f"Failed to create recon run: {e}")
            return None

    async def finish_recon_run(self, *, scan_id: str, status: str = "completed"):
        if not self.supabase:
            return None
        try:
            await self._run_sync(
                lambda: self.supabase.table("recon_runs").update({
                    "status": status,
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                }).eq("scan_id", scan_id).execute())
            return scan_id
        except Exception as e:
            logger.debug(f"Failed to finish recon run: {e}")
            return None

    async def upsert_recon_entity(
        self,
        *,
        id: str,
        scan_id: str,
        kind: str,
        label: str,
        normalized: Dict[str, Any],
        sources: List[Dict[str, Any]],
        confidence: float = 0.0,
    ):
        if not self.supabase:
            return None
        try:
            result = await self._run_sync(
                lambda: self.supabase.table("recon_entities").upsert({
                    "id": id,
                    "scan_id": scan_id,
                    "kind": kind,
                    "label": label,
                    "normalized": normalized,
                    "sources": sources,
                    "confidence": confidence,
                    "last_seen": datetime.now(timezone.utc).isoformat(),
                }, on_conflict="id").execute())
            return result.data[0]["id"] if result.data else id
        except Exception as e:
            logger.debug(f"Failed to upsert recon entity: {e}")
            return None

    async def create_recon_artifact(
        self,
        *,
        id: str,
        scan_id: str,
        tool_name: str,
        artifact_type: str,
        path: str,
        sha256: str = "",
        bytes: int = 0,
        metadata: Dict[str, Any] | None = None,
    ):
        if not self.supabase:
            return None
        try:
            result = await self._run_sync(
                lambda: self.supabase.table("recon_artifacts").upsert({
                    "id": id,
                    "scan_id": scan_id,
                    "tool_name": tool_name,
                    "artifact_type": artifact_type,
                    "path": path,
                    "sha256": sha256,
                    "bytes": bytes,
                    "metadata": metadata or {},
                }, on_conflict="id").execute())
            return result.data[0]["id"] if result.data else id
        except Exception as e:
            logger.debug(f"Failed to create recon artifact: {e}")
            return None

    async def upsert_endpoint_score(
        self,
        *,
        id: str,
        scan_id: str,
        endpoint_id: str,
        score: int,
        reasons: List[str],
        omega_modules: List[str] | None = None,
    ):
        if not self.supabase:
            return None
        try:
            result = await self._run_sync(
                lambda: self.supabase.table("recon_endpoint_scores").upsert({
                    "id": id,
                    "scan_id": scan_id,
                    "endpoint_id": endpoint_id,
                    "score": score,
                    "reasons": reasons,
                    "omega_modules": omega_modules or [],
                }, on_conflict="id").execute())
            return result.data[0]["id"] if result.data else id
        except Exception as e:
            logger.debug(f"Failed to upsert endpoint score: {e}")
            return None

    async def create_toolcall(
        self,
        *,
        call_id: str,
        scan_id: str,
        tool_name: str,
        agent: str,
        args: Dict[str, Any],
        status: str = "running",
        error: str = "",
    ):
        if not self.supabase:
            return None
        try:
            result = await self._run_sync(
                lambda: self.supabase.table("toolcalls").insert({
                    "call_id": call_id,
                    "scan_id": scan_id,
                    "tool_name": tool_name,
                    "agent": agent,
                    "args": args,
                    "status": status,
                    "error": error,
                    "started_at": datetime.now(timezone.utc).isoformat(),
                }).execute())
            return result.data[0]["id"] if result.data else None
        except Exception as e:
            logger.debug(f"Failed to create toolcall: {e}")
            return None

    async def finish_toolcall(
        self,
        *,
        call_id: str,
        status: str,
        result: Any = None,
        error: str = "",
        duration_ms: int = 0,
        result_bytes: int = 0,
        result_sha256: str = "",
    ):
        if not self.supabase:
            return None
        try:
            payload = {
                "status": status,
                "result": result,
                "error": error,
                "duration_ms": duration_ms,
                "result_bytes": result_bytes,
                "result_sha256": result_sha256,
                "finished_at": datetime.now(timezone.utc).isoformat(),
            }
            await self._run_sync(
                lambda: self.supabase.table("toolcalls").update(payload)
                    .eq("call_id", call_id).execute())
        except Exception as e:
            logger.debug(f"Failed to finish toolcall: {e}")
            return None

    async def create_approval(
        self,
        *,
        approval_id: str,
        scan_id: str,
        tool_name: str,
        reason: str,
        payload: Dict[str, Any],
        status: str = "pending",
    ):
        if not self.supabase:
            return None
        try:
            result = await self._run_sync(
                lambda: self.supabase.table("approvals").insert({
                    "approval_id": approval_id,
                    "scan_id": scan_id,
                    "tool_name": tool_name,
                    "reason": reason,
                    "payload": payload,
                    "status": status,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }).execute())
            return result.data[0]["id"] if result.data else None
        except Exception as e:
            logger.debug(f"Failed to create approval: {e}")
            return None

    async def log_http_exchange(
        self,
        *,
        scan_id: str,
        request_id: str,
        method: str,
        url: str,
        request_headers: Dict[str, str],
        request_body: Any,
        status: int,
        response_headers: Dict[str, str],
        response_body: str,
        elapsed_ms: int,
    ):
        if not self.supabase:
            return None
        try:
            req = await self._run_sync(
                lambda: self.supabase.table("http_requests").insert({
                    "request_id": request_id,
                    "scan_id": scan_id,
                    "method": method,
                    "url": url,
                    "headers": request_headers,
                    "body": request_body,
                    "elapsed_ms": elapsed_ms,
                }).execute())
            db_request_id = req.data[0]["id"] if req.data else None
            await self._run_sync(
                lambda: self.supabase.table("http_responses").insert({
                    "request_db_id": db_request_id,
                    "request_id": request_id,
                    "scan_id": scan_id,
                    "status": status,
                    "headers": response_headers,
                    "body": response_body,
                    "body_preview": response_body[:4000],
                }).execute())
            return db_request_id
        except Exception as e:
            logger.debug(f"Failed to log HTTP exchange: {e}")
            return None

    # --- 6. LIFECYCLE ---

    async def close(self):
        """Close any connections held by the manager (Architecture §29.13).
        Safe to call multiple times; never raises. Drops the Supabase
        reference (the supabase-py client uses a synchronous httpx session
        that doesn't need explicit close) and gracefully closes Redis."""
        try:
            if self.redis is not None:
                try:
                    await self.redis.close()
                except Exception as e:  # pragma: no cover - best-effort cleanup
                    logger.debug(f"Redis close error: {e}")
                self.redis = None
        finally:
            self.supabase = None
            self._initialized = False

# Global Instance
db_manager = EliteDBManager()
