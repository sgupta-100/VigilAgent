"""
BrowserOrchestrator: Unified browser automation interface.

This module provides a single API that intelligently routes between:
- OpenClaw: Deep automation, multi-step workflows, stealth mode
- PinchTab: Fast DOM scraping, token extraction, lightweight operations

All agents use this unified interface for browser capabilities.
Includes context isolation for security.
"""

from enum import Enum
from typing import Optional, Dict, Any, List, Union
import asyncio
from pathlib import Path
import logging
import uuid

from backend.core.config import settings

logger = logging.getLogger(__name__)


class BrowserEngine(Enum):
    """Browser engine selection"""
    OPENCLAW = "openclaw"      # Deep automation, workflows, stealth
    PINCHTAB = "pinchtab"      # Fast scraping, token extraction
    AUTO = "auto"              # Intelligent selection


class BrowserUnavailable(RuntimeError):
    """Raised when both OpenClaw and PinchTab engines are offline.

    Callers should catch this and fall back to a non-browser code path or
    surface it to the user — silently returning empty results is the bug we are
    explicitly avoiding.
    """


class BrowserOrchestrator:
    """
    Unified browser interface that routes between OpenClaw and PinchTab.
    Provides a single API for all agents to use browser capabilities.
    Includes context isolation for security between scans.
    
    Usage:
        browser = BrowserOrchestrator()
        await browser.initialize()
        
        # Auto-select engine
        await browser.navigate("https://example.com")
        
        # Force specific engine
        await browser.navigate("https://example.com", engine=BrowserEngine.OPENCLAW)
    """
    
    def __init__(self):
        self.openclaw = None
        self.pinchtab = None
        self.session_manager = None
        self.forensics = None
        self._initialized = False
        
        # Context isolation tracking
        self._active_contexts: Dict[str, Dict[str, Any]] = {}
        self._context_lock = asyncio.Lock()
        self._max_contexts = 10  # Maximum concurrent isolated contexts
        
        # Resource management
        self._context_pool: List[str] = []  # Pool of reusable context IDs
        self._pool_lock = asyncio.Lock()
        self._max_pool_size = 5  # Maximum contexts to keep in pool
        
        # Memory monitoring
        self._memory_threshold_mb = 500  # Alert threshold in MB
        self._last_memory_check = 0
        self._memory_check_interval = 60  # Check every 60 seconds
        
        # Lazy initialization flags
        self._openclaw_initialized = False
        self._pinchtab_initialized = False

        # Last init failure reason / remediation hint per engine. Populated
        # by the _lazy_init_* paths so health_check() and get_engine_status()
        # can surface a concrete cause to operators.
        self._openclaw_last_reason: str = ""
        self._openclaw_last_hint: str = ""
        self._pinchtab_last_reason: str = ""
        self._pinchtab_last_hint: str = ""
        
    async def initialize(self, lazy: bool = False):
        """
        Initialize both browser engines.
        
        Args:
            lazy: If True, engines are initialized on first use (lazy loading)
        """
        if self._initialized:
            return
            
        logger.info("[BrowserOrchestrator] Initializing hybrid browser stack...")
        
        if lazy:
            # Lazy initialization - engines will be initialized on first use
            logger.info("[BrowserOrchestrator] Lazy initialization mode enabled")
        else:
            # Eager initialization - initialize both engines now
            await self._lazy_init_openclaw()
            await self._lazy_init_pinchtab()
        
        # Always initialize session manager and forensics
        from backend.core.hybrid_session_manager import HybridSessionManager
        self.session_manager = HybridSessionManager()
        
        from backend.core.forensic_collector import ForensicCollector
        self.forensics = ForensicCollector()
        
        self._initialized = True
        logger.info("[BrowserOrchestrator] Hybrid browser stack ready")
    
    async def create_isolated_context(self, scan_id: str, context_name: Optional[str] = None) -> str:
        """
        Create an isolated browser context for a scan.
        
        Args:
            scan_id: Scan identifier
            context_name: Optional custom context name
            
        Returns:
            Context ID for the isolated context
        """
        async with self._context_lock:
            # Check context limit
            if len(self._active_contexts) >= self._max_contexts:
                logger.warning(f"[BrowserOrchestrator] Context limit reached ({self._max_contexts}), cleaning up old contexts")
                await self._cleanup_idle_contexts()
            
            # Generate unique context ID
            context_id = context_name or f"{scan_id}_{uuid.uuid4().hex[:8]}"
            
            # Create isolated context
            context_data = {
                "scan_id": scan_id,
                "context_id": context_id,
                "created_at": asyncio.get_event_loop().time(),
                "last_activity": asyncio.get_event_loop().time(),
                "engine": None,
                "context_handle": None
            }
            
            self._active_contexts[context_id] = context_data
            
            logger.info(f"[BrowserOrchestrator] Created isolated context: {context_id} for scan: {scan_id}")
            
            return context_id
    
    async def get_context(self, context_id: str) -> Optional[Dict[str, Any]]:
        """Get context data by ID."""
        async with self._context_lock:
            context = self._active_contexts.get(context_id)
            if context:
                # Update last activity
                context["last_activity"] = asyncio.get_event_loop().time()
            return context
    
    async def close_context(self, context_id: str):
        """Close and cleanup an isolated context."""
        async with self._context_lock:
            context = self._active_contexts.get(context_id)
            
            if not context:
                return
            
            # Close browser context if exists
            if context.get("context_handle"):
                try:
                    # Close the actual browser context
                    # This would call the appropriate engine's close method
                    pass
                except Exception as e:
                    logger.error(f"[BrowserOrchestrator] Failed to close context {context_id}: {e}")
            
            # Remove from tracking
            del self._active_contexts[context_id]
            
            logger.info(f"[BrowserOrchestrator] Closed isolated context: {context_id}")
    
    async def _cleanup_idle_contexts(self, max_idle_seconds: int = 300):
        """Cleanup contexts that have been idle for too long."""
        current_time = asyncio.get_event_loop().time()
        idle_contexts = []
        
        for context_id, context in self._active_contexts.items():
            idle_time = current_time - context["last_activity"]
            if idle_time > max_idle_seconds:
                idle_contexts.append(context_id)
        
        for context_id in idle_contexts:
            await self.close_context(context_id)
        
        logger.info(f"[BrowserOrchestrator] Cleaned up {len(idle_contexts)} idle contexts")
    
    def get_active_context_count(self) -> int:
        """Get number of active contexts."""
        return len(self._active_contexts)
    
    def get_context_stats(self) -> Dict[str, Any]:
        """Get statistics about active contexts."""
        current_time = asyncio.get_event_loop().time()
        
        stats = {
            "total_contexts": len(self._active_contexts),
            "max_contexts": self._max_contexts,
            "contexts_by_scan": {},
            "idle_contexts": 0
        }
        
        for context_id, context in self._active_contexts.items():
            scan_id = context["scan_id"]
            stats["contexts_by_scan"][scan_id] = stats["contexts_by_scan"].get(scan_id, 0) + 1
            
            idle_time = current_time - context["last_activity"]
            if idle_time > 60:  # Idle for more than 1 minute
                stats["idle_contexts"] += 1
        
        return stats
        
    async def navigate(self, url: str, engine: BrowserEngine = BrowserEngine.AUTO,
                      stealth: bool = False, wait_for: str = "networkidle",
                      scan_id: Optional[str] = None, context_id: Optional[str] = None):
        """
        Navigate to URL using best engine for the task with context isolation.
        
        Args:
            url: Target URL
            engine: Browser engine to use (AUTO, OPENCLAW, PINCHTAB)
            stealth: Enable stealth mode (human-like behavior)
            wait_for: Wait condition (networkidle, load, domcontentloaded)
            scan_id: Scan ID for session management
            context_id: Optional isolated context ID
            
        Returns:
            Navigation result with context/page references
            
        AUTO mode logic:
        - Use PinchTab for: Simple DOM scraping, token extraction, fast recon
        - Use OpenClaw for: Complex workflows, stealth mode, multi-step attacks

        Raises ``BrowserUnavailable`` when no engine can serve the request, so
        callers don't get silent empty results.
        """
        await self._ensure_initialized()
        
        # Create isolated context if scan_id provided but no context_id
        if scan_id and not context_id:
            context_id = await self.create_isolated_context(scan_id)

        # Lazy-init engines BEFORE selecting one (otherwise both look None).
        await self._lazy_init_openclaw()
        await self._lazy_init_pinchtab()

        selected_engine = self._select_engine(engine, stealth, url)

        logger.info(
            "[BrowserOrchestrator] Navigating to %s via %s (context: %s)",
            url, selected_engine.value, context_id,
        )

        # Build candidate order, preferring the selected engine but always
        # falling back to whichever engine is actually available.
        if selected_engine == BrowserEngine.PINCHTAB:
            candidates = [BrowserEngine.PINCHTAB, BrowserEngine.OPENCLAW]
        else:
            candidates = [BrowserEngine.OPENCLAW, BrowserEngine.PINCHTAB]

        last_error: Optional[str] = None
        for candidate in candidates:
            try:
                if candidate == BrowserEngine.PINCHTAB:
                    if self.pinchtab is None or not getattr(self.pinchtab, "is_available", lambda: False)():
                        continue
                    result = await self.pinchtab.navigate(url)
                    if result.get("success"):
                        return result
                    last_error = result.get("error") or "PinchTab navigation failed"
                else:  # OPENCLAW
                    if self.openclaw is None:
                        continue
                    return await self.openclaw.navigate(url, stealth=stealth, wait_for=wait_for)
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                logger.warning(
                    "[BrowserOrchestrator] %s navigation failed: %s",
                    candidate.value, last_error,
                )

        raise BrowserUnavailable(
            f"No browser engine could navigate to {url}: "
            f"{last_error or 'OpenClaw and PinchTab both offline'}"
        )
                
    async def extract_endpoints(self, url: str, deep: bool = False, scan_id: Optional[str] = None):
        """
        Extract API endpoints from page.

        Args:
            url: Target URL
            deep: Use deep analysis (OpenClaw) vs fast extraction (PinchTab)
            scan_id: Scan ID for tracking

        Returns:
            List of discovered endpoints. Each endpoint is a dict with at
            least ``url``; deep mode also includes ``method`` and ``source``.
        """
        await self._ensure_initialized()
        await self._lazy_init_openclaw()
        await self._lazy_init_pinchtab()

        if deep and self.openclaw:
            try:
                logger.info("[BrowserOrchestrator] Deep endpoint extraction on %s", url)
                eps = await self.openclaw.extract_endpoints_deep(url)
                # OpenClawEngine.extract_endpoints_deep returns list[dict].
                if eps and isinstance(eps[0], str):
                    eps = [{"url": u, "method": "GET", "source": "openclaw"} for u in eps]
                return eps or []
            except Exception as exc:
                logger.warning(
                    "[BrowserOrchestrator] Deep extraction failed, trying fast mode: %s", exc,
                )

        if self.pinchtab and self.pinchtab.is_available():
            logger.info("[BrowserOrchestrator] Fast endpoint extraction on %s", url)
            urls = await self.pinchtab.extract_endpoints_fast(url)
            return [{"url": u, "method": "GET", "source": "pinchtab"} for u in (urls or [])]

        return []
            
    async def execute_workflow(self, workflow: Dict, scan_id: str):
        """
        Execute multi-step workflow (OpenClaw only).
        
        Args:
            workflow: Workflow definition with steps
            scan_id: Scan ID for tracking
            
        Returns:
            Workflow execution results
        """
        await self._ensure_initialized()
        
        if not self.openclaw:
            raise RuntimeError("OpenClaw required for workflow execution")
            
        logger.info(f"[BrowserOrchestrator] Executing workflow: {workflow.get('name', 'unnamed')}")
        return await self.openclaw.execute_workflow(workflow, scan_id)
        
    async def extract_tokens(self, url: str, scan_id: Optional[str] = None):
        """
        Extract auth tokens (PinchTab optimized).
        
        Args:
            url: Target URL
            scan_id: Scan ID for tracking
            
        Returns:
            List of extracted tokens (JWT, Bearer, etc.)
        """
        await self._ensure_initialized()
        await self._lazy_init_openclaw()
        await self._lazy_init_pinchtab()

        if self._pinchtab_ready():
            logger.info(f"[BrowserOrchestrator] Extracting tokens from {url}")
            return await self.pinchtab.extract_tokens(url)
        elif self.openclaw:
            return await self.openclaw.extract_tokens(url)
        else:
            return []
            
    async def test_payload(self, url: str, payload: str, method: str = "GET",
                          scan_id: Optional[str] = None):
        """
        Test payload in browser context.
        Auto-selects engine based on payload type.
        
        Args:
            url: Target URL
            payload: Attack payload to test
            method: HTTP method
            scan_id: Scan ID for tracking
            
        Returns:
            Test results with exploitation indicators
        """
        await self._ensure_initialized()
        await self._lazy_init_openclaw()
        await self._lazy_init_pinchtab()

        # XSS payloads need real browser execution
        if any(x in payload.lower() for x in ["<script", "onerror", "onclick", "onload", "alert"]):
            if self.openclaw:
                logger.info("[BrowserOrchestrator] Testing XSS payload in OpenClaw")
                return await self.openclaw.test_xss_payload(url, payload)
                
        # Simple injection can use fast mode
        if self._pinchtab_ready():
            logger.info("[BrowserOrchestrator] Testing injection in PinchTab")
            return await self.pinchtab.test_injection(url, payload, method)
        elif self.openclaw:
            return await self.openclaw.test_xss_payload(url, payload)
        else:
            return {"tested": False, "error": "No engines available"}
            
    async def detect_framework(self, url: str):
        """Detect JavaScript framework (React/Vue/Angular)"""
        await self._ensure_initialized()
        
        await self._lazy_init_openclaw()
        if self.openclaw:
            try:
                return await self.openclaw.detect_framework(url)
            except Exception as exc:
                logger.warning("[BrowserOrchestrator] Framework detection failed: %s", exc)
        return None
        
    async def intercept_network(self, url: str):
        """Intercept network requests (XHR/Fetch)"""
        await self._ensure_initialized()
        await self._lazy_init_openclaw()

        if self.openclaw:
            return await self.openclaw.intercept_network(url)
        return []
        
    async def find_websockets(self, url: str):
        """Find WebSocket connections"""
        await self._ensure_initialized()
        await self._lazy_init_openclaw()

        if self.openclaw:
            return await self.openclaw.find_websockets(url)
        return []
        
    async def capture_screenshot(self, scan_id: str, label: str = "screenshot"):
        """Capture screenshot for forensic evidence"""
        await self._ensure_initialized()
        await self._lazy_init_openclaw()

        if self.openclaw:
            return await self.openclaw.capture_screenshot(scan_id, label)
        return None
        
    async def capture_dom(self, scan_id: str, label: str = "dom"):
        """Capture DOM snapshot"""
        await self._ensure_initialized()
        await self._lazy_init_openclaw()

        if self.openclaw:
            return await self.openclaw.capture_dom(scan_id, label)
        return None
        
    async def get_network_log(self):
        """Get network request log"""
        await self._ensure_initialized()
        await self._lazy_init_openclaw()

        if self.openclaw:
            return await self.openclaw.get_network_log()
        return []
        
    async def analyze_dom(self, url: str):
        """Analyze DOM structure (forms, inputs, etc.)"""
        await self._ensure_initialized()
        await self._lazy_init_pinchtab()

        if self._pinchtab_ready():
            return await self.pinchtab.analyze_dom(url)
        return {}
        
    async def get_page_text(self):
        """Get page text content"""
        await self._ensure_initialized()
        await self._lazy_init_openclaw()
        await self._lazy_init_pinchtab()

        if self._pinchtab_ready():
            return await self.pinchtab.get_page_text()
        elif self.openclaw:
            return await self.openclaw.get_page_text()
        return ""
        
    def _pinchtab_ready(self) -> bool:
        """True iff the PinchTab engine is initialized AND its control plane is reachable."""
        if self.pinchtab is None:
            return False
        try:
            return bool(self.pinchtab.is_available())
        except Exception as exc:
            logger.debug("[BrowserOrchestrator] PinchTab ready check failed: %s", exc)
            return False

    def _select_engine(self, requested: BrowserEngine, stealth: bool, url: str) -> BrowserEngine:
        """
        Intelligent engine selection based on requirements.
        
        Selection logic:
        - If specific engine requested, use it (if available)
        - If stealth mode, prefer OpenClaw
        - If auth/login URL, prefer OpenClaw (needs session handling)
        - Otherwise, prefer PinchTab for speed
        """
        pinch_ready = self._pinchtab_ready()
        # Honor explicit request
        if requested != BrowserEngine.AUTO:
            if requested == BrowserEngine.OPENCLAW and self.openclaw:
                return BrowserEngine.OPENCLAW
            elif requested == BrowserEngine.PINCHTAB and pinch_ready:
                return BrowserEngine.PINCHTAB
                
        # Auto-selection logic
        if stealth:
            return BrowserEngine.OPENCLAW if self.openclaw else BrowserEngine.PINCHTAB
            
        # Auth/login pages need OpenClaw for session management
        if any(keyword in url.lower() for keyword in ["login", "auth", "signin", "oauth"]):
            return BrowserEngine.OPENCLAW if self.openclaw else BrowserEngine.PINCHTAB
            
        # Check user preference
        prefer_speed = getattr(settings, "BROWSER_PREFER_SPEED", False)
        if prefer_speed and pinch_ready:
            return BrowserEngine.PINCHTAB
            
        # Default: prefer OpenClaw for depth, fallback to PinchTab
        if self.openclaw:
            return BrowserEngine.OPENCLAW
        elif pinch_ready:
            return BrowserEngine.PINCHTAB
        else:
            return BrowserEngine.OPENCLAW  # Will fail gracefully via BrowserUnavailable
            
    async def _ensure_initialized(self):
        """Ensure orchestrator is initialized"""
        if not self._initialized:
            await self.initialize()
            
    # ============ RESOURCE MANAGEMENT (Phase 4) ============
    
    async def get_pooled_context(self, scan_id: str) -> str:
        """
        Get a context from the pool or create a new one.
        Implements context pooling for better resource utilization.
        """
        async with self._pool_lock:
            # Try to get from pool first
            if self._context_pool:
                context_id = self._context_pool.pop(0)
                logger.info(f"[BrowserOrchestrator] Reusing pooled context: {context_id}")
                
                # Update context metadata
                async with self._context_lock:
                    if context_id in self._active_contexts:
                        self._active_contexts[context_id]["scan_id"] = scan_id
                        self._active_contexts[context_id]["last_activity"] = asyncio.get_event_loop().time()
                
                return context_id
        
        # No pooled context available, create new one
        return await self.create_isolated_context(scan_id)
    
    async def return_context_to_pool(self, context_id: str):
        """
        Return a context to the pool for reuse instead of closing it.
        Reduces overhead of creating/destroying contexts.
        """
        async with self._pool_lock:
            # Only pool if under max size
            if len(self._context_pool) < self._max_pool_size:
                # Clean the context before pooling
                # (would clear cookies, storage, etc. in production)
                self._context_pool.append(context_id)
                logger.info(f"[BrowserOrchestrator] Context {context_id} returned to pool")
                return True
        
        # Pool is full, close the context
        await self.close_context(context_id)
        return False
    
    async def monitor_memory(self) -> Dict[str, Any]:
        """
        Monitor memory usage of browser processes.
        Returns memory statistics and triggers cleanup if needed.
        """
        import time
        current_time = time.time()
        
        # Rate limit memory checks
        if current_time - self._last_memory_check < self._memory_check_interval:
            return {"skipped": True, "reason": "rate_limited"}
        
        self._last_memory_check = current_time
        
        try:
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            
            stats = {
                "memory_mb": round(memory_mb, 2),
                "threshold_mb": self._memory_threshold_mb,
                "threshold_exceeded": memory_mb > self._memory_threshold_mb,
                "active_contexts": len(self._active_contexts),
                "pooled_contexts": len(self._context_pool)
            }
            
            # Trigger cleanup if threshold exceeded
            if stats["threshold_exceeded"]:
                logger.warning(
                    f"[BrowserOrchestrator] Memory threshold exceeded: "
                    f"{memory_mb:.1f}MB > {self._memory_threshold_mb}MB"
                )
                
                # Cleanup idle contexts
                await self._cleanup_idle_contexts(max_idle_seconds=180)  # 3 minutes
                
                # Clear context pool
                async with self._pool_lock:
                    pool_size = len(self._context_pool)
                    self._context_pool.clear()
                    logger.info(f"[BrowserOrchestrator] Cleared {pool_size} pooled contexts")
                
                stats["cleanup_triggered"] = True
            
            return stats
            
        except Exception as e:
            logger.error(f"[BrowserOrchestrator] Memory monitoring failed: {e}")
            return {"error": str(e)}
    
    async def _lazy_init_openclaw(self):
        """Lazy initialization of OpenClaw engine.

        Degrades gracefully:
          * Logs ONE warning per engine at startup — never a generic
            "unavailable", always the concrete reason + a remediation hint.
          * If Playwright is installed but the Chromium binary is missing,
            attempts ``python -m playwright install chromium`` ONLY when
            ``ALPHA_AUTO_INSTALL_BROWSERS=true``; otherwise skips with a
            clear log (no auto-download surprises in production).
        """
        if self._openclaw_initialized or self.openclaw:
            return

        if not getattr(settings, "OPENCLAW_ENABLED", True):
            self._openclaw_initialized = True
            return

        try:
            from backend.core.openclaw_engine import OpenClawEngine
            engine = OpenClawEngine()
            ok = await engine.initialize()

            # If init failed because Chromium isn't downloaded, optionally
            # install it once and retry. This is the single most common
            # cause of "OpenClaw unavailable" on a fresh checkout.
            if not ok and "playwright_browsers_not_installed" in (
                    getattr(engine, "last_init_error", "") or ""):
                if self._auto_install_browsers_enabled():
                    logger.info(
                        "[BrowserOrchestrator] Chromium binary missing — "
                        "ALPHA_AUTO_INSTALL_BROWSERS=true, running "
                        "`python -m playwright install chromium`"
                    )
                    if await self._install_playwright_chromium():
                        # Retry once with the freshly downloaded binary.
                        ok = await engine.initialize()
                else:
                    logger.warning(
                        "[BrowserOrchestrator] Chromium binary missing. "
                        "Set ALPHA_AUTO_INSTALL_BROWSERS=true to auto-install, "
                        "or run: python -m playwright install chromium"
                    )

            self._openclaw_initialized = True
            if ok:
                self.openclaw = engine
                logger.info("[BrowserOrchestrator] OpenClaw engine ready")
            else:
                self.openclaw = None
                reason = getattr(engine, "last_init_error", "") or "unknown"
                # Single concrete WARNING + remediation hint (never the
                # generic "unavailable"). The hint depends on the failure
                # category so users see exactly what to do next.
                hint = self._remediation_hint_openclaw(reason)
                logger.warning(
                    "[BrowserOrchestrator] OpenClaw engine offline: %s | hint: %s",
                    reason, hint,
                )
                # Stash the last reason for health_check() / get_engine_status().
                self._openclaw_last_reason = reason
                self._openclaw_last_hint = hint
        except Exception as exc:
            self.openclaw = None
            self._openclaw_initialized = True
            self._openclaw_last_reason = f"{type(exc).__name__}: {exc}"
            self._openclaw_last_hint = (
                "Re-run with ALPHA_DEBUG=1 to see the full traceback")
            logger.warning(
                "[BrowserOrchestrator] OpenClaw lazy-init crashed (%s: %s)",
                type(exc).__name__, str(exc)[:200],
                exc_info=True,
            )

    @staticmethod
    def _auto_install_browsers_enabled() -> bool:
        """Single source of truth for the auto-install opt-in flag."""
        import os
        return os.getenv("ALPHA_AUTO_INSTALL_BROWSERS", "").lower() == "true"

    @staticmethod
    async def _install_playwright_chromium() -> bool:
        """Run ``python -m playwright install chromium`` in a subprocess.

        Returns True on a clean exit. Failures are logged at WARNING and the
        caller continues without OpenClaw.
        """
        import sys
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "playwright", "install", "chromium",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode == 0:
                logger.info(
                    "[BrowserOrchestrator] playwright install chromium succeeded"
                )
                return True
            logger.warning(
                "[BrowserOrchestrator] playwright install chromium exited "
                "with code %s: %s",
                proc.returncode,
                (stderr.decode(errors="replace") or
                 stdout.decode(errors="replace"))[:300],
            )
            return False
        except Exception as exc:
            logger.warning(
                "[BrowserOrchestrator] playwright install chromium failed (%s: %s)",
                type(exc).__name__, str(exc)[:200],
            )
            return False

    @staticmethod
    def _remediation_hint_openclaw(reason: str) -> str:
        """Map an OpenClaw init failure reason to a one-line fix-it hint."""
        r = (reason or "").lower()
        if "playwright_not_installed" in r or "playwright_import_failed" in r:
            return "pip install playwright"
        if "playwright_browsers_not_installed" in r or "executable doesn't exist" in r:
            return ("python -m playwright install chromium "
                    "(or set ALPHA_AUTO_INSTALL_BROWSERS=true)")
        return ("Set OPENCLAW_ENABLED=false to silence, "
                "or check the playwright Chromium install")

    async def _lazy_init_pinchtab(self):
        """Lazy initialization of PinchTab engine.

        Like ``_lazy_init_openclaw`` this emits a single warning at startup
        when the engine is genuinely offline, with a concrete reason
        (control plane unreachable) and a one-line remediation hint
        (``ALPHA_ENABLE_PINCHTAB=false`` to silence). Recon + HTTP probe
        keep working — PinchTab is purely additive.
        """
        if self._pinchtab_initialized or self.pinchtab:
            return

        if not getattr(settings, "PINCHTAB_ENABLED",
                       getattr(settings, "ALPHA_ENABLE_PINCHTAB", True)):
            self._pinchtab_initialized = True
            return

        try:
            from backend.core.pinchtab_engine import PinchTabEngine
            engine = PinchTabEngine()
            ok = await engine.initialize()
            self._pinchtab_initialized = True
            if ok:
                self.pinchtab = engine
                logger.info("[BrowserOrchestrator] PinchTab engine ready")
            else:
                # Engine offline — almost always because the local PinchTab
                # control plane (default http://127.0.0.1:9867) isn't running.
                self.pinchtab = None
                base_url = getattr(
                    getattr(engine, "client", None), "base_url",
                    getattr(settings, "PINCHTAB_BASE_URL", "http://127.0.0.1:9867"),
                )
                reason = f"pinchtab_daemon_unreachable at {base_url}"
                hint = (
                    f"PinchTab base URL {base_url} unreachable; "
                    "set ALPHA_ENABLE_PINCHTAB=false to silence"
                )
                # WARNING (once) per the user's requirement: surface the
                # real reason + remediation. OpenClaw / Playwright fallback
                # still serves browser work.
                logger.warning(
                    "[BrowserOrchestrator] PinchTab engine offline: %s | hint: %s",
                    reason, hint,
                )
                self._pinchtab_last_reason = reason
                self._pinchtab_last_hint = hint
        except Exception as exc:
            self.pinchtab = None
            self._pinchtab_initialized = True
            self._pinchtab_last_reason = f"{type(exc).__name__}: {exc}"
            self._pinchtab_last_hint = (
                "Inspect backend.integrations.pinchtab_client; "
                "set ALPHA_ENABLE_PINCHTAB=false to silence")
            logger.warning(
                "[BrowserOrchestrator] PinchTab lazy-init crashed (%s: %s)",
                type(exc).__name__, str(exc)[:200],
                exc_info=True,
            )
    
    def get_resource_stats(self) -> Dict[str, Any]:
        """Get comprehensive resource usage statistics."""
        return {
            "active_contexts": len(self._active_contexts),
            "pooled_contexts": len(self._context_pool),
            "max_contexts": self._max_contexts,
            "max_pool_size": self._max_pool_size,
            "openclaw_initialized": self._openclaw_initialized,
            "pinchtab_initialized": self._pinchtab_initialized,
            "memory_threshold_mb": self._memory_threshold_mb
        }

    def is_ready(self) -> bool:
        """Return True iff at least one browser engine can serve requests.

        Used by callers (Alpha BrowserReconModule, AgentDelta, AgentChi) that
        want a quick yes/no before attempting browser-aware operations. The
        Playwright fallback inside OpenClawEngine counts: if Chromium launched,
        we're ready even when the PinchTab daemon is offline.
        """
        if not self._initialized and not (self._openclaw_initialized or self._pinchtab_initialized):
            return False
        if self.openclaw is not None:
            return True
        return self.pinchtab is not None and self._pinchtab_ready()

    def get_engine_status(self) -> Dict[str, Any]:
        """Return the current availability state of each engine.

        Useful for diagnostics / smoke tests so you can see at a glance which
        engine came up and, when one didn't, the precise reason. Does not
        perform any I/O; it reflects the state observed during init.
        """
        openclaw_status: Dict[str, Any] = {
            "available": self.openclaw is not None,
            "initialized": self._openclaw_initialized,
        }
        if self.openclaw is None and self._openclaw_initialized:
            # If we tried and failed, the engine instance was discarded; we
            # can't pull last_init_error from it. The reason is already in
            # the log. Indicate "see log" so callers don't think it's a bug.
            openclaw_status["reason"] = "see warning log"
        elif self.openclaw is not None:
            err = getattr(self.openclaw, "last_init_error", "") or ""
            if err:
                openclaw_status["last_init_error"] = err

        pinchtab_status: Dict[str, Any] = {
            "available": self.pinchtab is not None and self._pinchtab_ready(),
            "initialized": self._pinchtab_initialized,
        }
        if self.pinchtab is None and self._pinchtab_initialized:
            pinchtab_status["reason"] = "pinchtab_daemon_not_running"

        return {"openclaw": openclaw_status, "pinchtab": pinchtab_status}

    async def health_check(self) -> Dict[str, Any]:
        """Boot-time browser stack health probe.

        Triggers lazy init for both engines (so any "unavailable" warnings
        and remediation hints surface during startup, not on the first
        scan), then returns a structured snapshot::

            {
              "openclaw": "ok" | "unavailable" | "degraded",
              "pinchtab": "ok" | "unavailable",
              "reasons": {
                "openclaw": "<concrete reason if not ok>",
                "pinchtab": "<concrete reason if not ok>",
                "openclaw_hint": "<remediation hint>",
                "pinchtab_hint": "<remediation hint>",
              }
            }

        The swarm does NOT require either engine to be available — recon
        and HTTP probe still produce results when both are offline. This
        method is purely diagnostic.
        """
        # Force lazy init if it hasn't happened yet — that's where the
        # "single warning per engine" actually fires.
        if not self._openclaw_initialized:
            await self._lazy_init_openclaw()
        if not self._pinchtab_initialized:
            await self._lazy_init_pinchtab()

        # OpenClaw: "ok" if fully launched + probe-able; "degraded" if it
        # launched but its is_truly_available probe fails (rare); else
        # "unavailable".
        openclaw_state = "unavailable"
        if self.openclaw is not None:
            try:
                probe = await self.openclaw.is_truly_available()
                openclaw_state = "ok" if probe else "degraded"
            except Exception as exc:
                logger.debug("[BrowserOrchestrator] OpenClaw health probe failed: %s", exc)
                openclaw_state = "degraded"

        pinchtab_state = "ok" if (
            self.pinchtab is not None and self._pinchtab_ready()) else "unavailable"

        reasons: Dict[str, str] = {}
        if openclaw_state != "ok":
            if self._openclaw_last_reason:
                reasons["openclaw"] = self._openclaw_last_reason
            if self._openclaw_last_hint:
                reasons["openclaw_hint"] = self._openclaw_last_hint
        if pinchtab_state != "ok":
            if self._pinchtab_last_reason:
                reasons["pinchtab"] = self._pinchtab_last_reason
            if self._pinchtab_last_hint:
                reasons["pinchtab_hint"] = self._pinchtab_last_hint

        return {
            "openclaw": openclaw_state,
            "pinchtab": pinchtab_state,
            "reasons": reasons,
        }
    
    async def cleanup_all_resources(self):
        """Comprehensive cleanup of all browser resources."""
        logger.info("[BrowserOrchestrator] Starting comprehensive resource cleanup...")
        
        # Close all active contexts
        async with self._context_lock:
            context_ids = list(self._active_contexts.keys())
        
        for context_id in context_ids:
            try:
                await self.close_context(context_id)
            except Exception as e:
                logger.error(f"[BrowserOrchestrator] Failed to close context {context_id}: {e}")
        
        # Clear context pool
        async with self._pool_lock:
            pool_size = len(self._context_pool)
            self._context_pool.clear()
            logger.info(f"[BrowserOrchestrator] Cleared {pool_size} pooled contexts")
        
        logger.info("[BrowserOrchestrator] Resource cleanup complete")
    
    async def close(self):
        """Cleanup and close all browser engines and contexts"""
        logger.info("[BrowserOrchestrator] Closing browser engines...")
        
        # Comprehensive cleanup
        await self.cleanup_all_resources()
        
        if self.openclaw:
            await self.openclaw.close()
            
        if self.pinchtab:
            await self.pinchtab.close()
            
        self._initialized = False
        logger.info("[BrowserOrchestrator] Closed")


# Global instance for easy access
_browser_orchestrator = None


def get_browser_orchestrator() -> BrowserOrchestrator:
    """Get global BrowserOrchestrator instance"""
    global _browser_orchestrator
    if _browser_orchestrator is None:
        _browser_orchestrator = BrowserOrchestrator()
    return _browser_orchestrator
