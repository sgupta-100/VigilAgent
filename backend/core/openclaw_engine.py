"""
OpenClawEngine: Deep browser automation using Playwright Chromium.

This engine intentionally does NOT import the ``openclaw`` PyPI package. The
distributed ``openclaw`` wrapper has a broken import against the installed
version of ``cmdop`` (it tries to import a ``TimeoutError`` symbol that no
longer exists), which made the whole engine fail to initialize on Windows.

Instead, we drive Playwright directly. The Playwright Chromium binary ships
with the project's existing ``playwright`` install, so initialization is
deterministic. The public API (``navigate``, ``extract_endpoints_deep``,
``execute_workflow``, ``test_xss_payload``, ``current_page``,
``current_context``, ...) matches what other agents (Prism, Chi, browser
orchestrator, alpha browser_recon) already consume.

Capabilities preserved:
- Multi-step workflows
- Stealth mode (human-like UA + flags + navigator.webdriver suppression)
- Deep JavaScript analysis
- Network interception (request log captured per page)
- Screenshot + DOM forensic capture
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.core.config import settings

logger = logging.getLogger(__name__)


# --- stealth helpers ---------------------------------------------------------

_STEALTH_LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-features=IsolateOrigins,site-per-process",
    "--disable-dev-shm-usage",
    "--no-sandbox",
    "--disable-gpu",
    "--disable-extensions",
    "--disable-background-networking",
    "--disable-default-apps",
]

_STEALTH_INIT_SCRIPT = """
// Remove the navigator.webdriver flag.
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
// Plausible plugins / languages.
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
// chrome runtime stub.
window.chrome = window.chrome || { runtime: {} };
// Permissions polyfill that doesn't expose automation.
const origQuery = window.navigator.permissions && window.navigator.permissions.query;
if (origQuery) {
  window.navigator.permissions.query = (p) => (
    p && p.name === 'notifications'
      ? Promise.resolve({ state: Notification.permission })
      : origQuery(p)
  );
}
"""


class OpenClawEngine:
    """Deep browser automation backed by Playwright Chromium."""

    def __init__(self) -> None:
        # Public attributes expected by other modules.
        self.client: Any = None  # filled by initialize() so callers can probe truthiness
        self.workflow_engine: Any = None
        self.active_contexts: Dict[str, Any] = {}
        self.current_page: Any = None
        self.current_context: Any = None

        # Last initialization failure reason (string) — surfaced to the
        # orchestrator so it can log an actionable error instead of a generic
        # "unavailable". Empty string means initialize() has not failed.
        self.last_init_error: str = ""

        # Private Playwright handles.
        self._playwright: Any = None
        self._browser: Any = None
        self._network_log: List[Dict[str, Any]] = []
        self._init_lock = asyncio.Lock()

    # ── lifecycle ────────────────────────────────────────────────────────────

    async def initialize(self) -> bool:
        """Launch headless Chromium. Returns True on success, False otherwise.

        Any exception is captured + stored in ``self.last_init_error`` and
        logged with type + message so the orchestrator can record exactly
        *why* OpenClaw is unavailable (and surface a fix-it hint when the
        Playwright browser binaries are missing).
        """
        async with self._init_lock:
            if self._browser is not None:
                return True
            try:
                from playwright.async_api import async_playwright
            except ImportError as exc:
                self.last_init_error = (
                    f"playwright_not_installed: {exc}. "
                    "Install with: pip install playwright"
                )
                logger.warning(
                    "[OpenClawEngine] Playwright Python package not installed: %s. "
                    "Run: pip install playwright",
                    exc,
                )
                return False
            except Exception as exc:  # pragma: no cover - import guard
                self.last_init_error = f"playwright_import_failed: {type(exc).__name__}: {exc}"
                logger.warning(
                    "[OpenClawEngine] Playwright import failed (%s: %s); engine disabled",
                    type(exc).__name__, exc,
                )
                return False

            try:
                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(
                    headless=getattr(settings, "OPENCLAW_HEADLESS", True),
                    args=_STEALTH_LAUNCH_ARGS,
                )
                # Smoke-test that we can actually create a browser context. A
                # successful ``launch()`` is not enough — on some systems the
                # browser process starts but the first ``new_context()`` then
                # fails (missing system libraries, sandbox, etc). Verifying
                # this here turns "OpenClaw unavailable" into an actionable
                # error instead of a deferred crash inside ``navigate()``.
                _probe_ctx = await self._browser.new_context()
                await _probe_ctx.close()

                self.client = self._browser  # signal availability to callers
                self.last_init_error = ""
                logger.info(
                    "[OpenClawEngine] Playwright Chromium launched headless=%s",
                    getattr(settings, "OPENCLAW_HEADLESS", True),
                )
                return True
            except Exception as exc:
                # Roll back partial state so subsequent retries can try fresh.
                try:
                    if self._playwright:
                        await self._playwright.stop()
                except Exception:
                    pass
                self._playwright = None
                self._browser = None
                self.client = None

                # Detect the common "browsers not installed" failure mode and
                # produce an actionable error string + warning log. Playwright
                # raises a generic Error whose message starts with
                # "Executable doesn't exist at ...".
                msg = str(exc)
                if "Executable doesn't exist" in msg or "playwright install" in msg:
                    self.last_init_error = (
                        "playwright_browsers_not_installed: "
                        "run `python -m playwright install chromium` "
                        f"({type(exc).__name__}: {msg[:200]})"
                    )
                    logger.warning(
                        "[OpenClawEngine] Chromium binary missing. "
                        "Run: python -m playwright install chromium  (full error: %s)",
                        msg[:300],
                    )
                else:
                    self.last_init_error = f"{type(exc).__name__}: {msg[:200]}"
                    logger.warning(
                        "[OpenClawEngine] Chromium launch failed (%s: %s); engine disabled",
                        type(exc).__name__, msg[:300],
                    )
                return False

    async def is_truly_available(self) -> bool:
        """Probe whether the engine can actually serve work right now.

        ``initialize()`` returning True only means the browser process started.
        This method additionally verifies a context can be created, so callers
        get a real liveness signal instead of finding out at navigate() time.
        """
        if not self._browser:
            return False
        try:
            ctx = await self._browser.new_context()
            await ctx.close()
            return True
        except Exception as exc:
            logger.info(
                "[OpenClawEngine] is_truly_available probe failed: %s: %s",
                type(exc).__name__, str(exc)[:200],
            )
            return False

    async def _ensure_context(self, *, stealth: bool = False) -> Any:
        """Create (or return existing) browser context + page."""
        if not self._browser:
            raise RuntimeError("OpenClawEngine not initialized")

        if self.current_context and self.current_page:
            return self.current_context

        viewport = {
            "width": int(getattr(settings, "OPENCLAW_VIEWPORT_WIDTH", 1440) or 1440),
            "height": int(getattr(settings, "OPENCLAW_VIEWPORT_HEIGHT", 900) or 900),
        }
        ctx_kwargs: Dict[str, Any] = {
            "viewport": viewport,
            "ignore_https_errors": True,
        }
        ua = getattr(settings, "OPENCLAW_USER_AGENT", "")
        if ua:
            ctx_kwargs["user_agent"] = ua

        context = await self._browser.new_context(**ctx_kwargs)
        if stealth or getattr(settings, "OPENCLAW_STEALTH_MODE", True):
            try:
                await context.add_init_script(_STEALTH_INIT_SCRIPT)
            except Exception as exc:
                logger.debug("[OpenClawEngine] Stealth init script failed: %s", exc)

        page = await context.new_page()
        self._network_log = []

        def _on_request(request):
            try:
                self._network_log.append({
                    "url": request.url,
                    "method": request.method,
                    "headers": dict(request.headers),
                    "resource_type": request.resource_type,
                    "post_data": request.post_data,
                })
            except Exception:
                pass

        page.on("request", _on_request)
        self.current_context = context
        self.current_page = page
        return context

    # ── core API used by orchestrator ────────────────────────────────────────

    async def navigate(self, url: str, *, stealth: bool = False,
                       wait_for: str = "networkidle") -> Dict[str, Any]:
        """Navigate to URL, returning a structured result with success flag.

        ``wait_for`` accepts the standard Playwright ``wait_until`` values
        (``networkidle``, ``load``, ``domcontentloaded``, ``commit``).
        """
        if not self._browser:
            raise RuntimeError("OpenClawEngine not initialized")

        await self._ensure_context(stealth=stealth)
        page = self.current_page
        try:
            try:
                resp = await page.goto(url, wait_until=wait_for, timeout=30000)
            except Exception:
                # Some sites never reach network idle; fall back to DOM ready.
                resp = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            status_code = resp.status if resp else 0
            return {
                "context": self.current_context,
                "page": page,
                "url": url,
                "status_code": status_code,
                "success": True,
            }
        except Exception as exc:
            logger.info("[OpenClawEngine] navigate(%s) failed: %s: %s",
                        url, type(exc).__name__, str(exc)[:200])
            return {
                "context": self.current_context,
                "page": page,
                "url": url,
                "success": False,
                "error": f"{type(exc).__name__}: {exc}",
            }

    async def extract_endpoints_deep(self, url: str) -> List[Dict[str, Any]]:
        """Deep endpoint extraction: DOM links, script-embedded URLs, framework
        routers, plus all network requests captured during the page load."""
        result = await self.navigate(url)
        if not result.get("success"):
            return []
        page = result["page"]

        try:
            # Wait briefly so SPAs can finish their initial XHR burst.
            await page.wait_for_timeout(800)
        except Exception:
            pass

        endpoints: List[Dict[str, Any]] = []
        seen: set[str] = set()

        # 1. From the request log captured during navigation.
        for req in list(self._network_log):
            u = req.get("url") or ""
            if u and u not in seen:
                seen.add(u)
                endpoints.append({
                    "url": u,
                    "method": req.get("method", "GET"),
                    "source": "network",
                    "headers": req.get("headers", {}),
                })

        # 2. Static link / script extraction via in-page evaluation.
        try:
            extracted = await page.evaluate(
                """() => {
                    const out = new Set();
                    document.querySelectorAll('a[href]').forEach(a => {
                        const h = a.getAttribute('href');
                        if (h) out.add(h);
                    });
                    document.querySelectorAll('form[action]').forEach(f => {
                        const h = f.getAttribute('action');
                        if (h) out.add(h);
                    });
                    document.querySelectorAll('script').forEach(s => {
                        const t = s.textContent || '';
                        const re = /["'](\\/[A-Za-z0-9_./?=&%-]+)["']/g;
                        let m; while ((m = re.exec(t)) !== null) { out.add(m[1]); }
                    });
                    if (window.__REACT_ROUTER__ && window.__REACT_ROUTER__.routes) {
                        window.__REACT_ROUTER__.routes.forEach(r => { if (r.path) out.add(r.path); });
                    }
                    if (window.$router && window.$router.options) {
                        (window.$router.options.routes || []).forEach(r => {
                            if (r.path) out.add(r.path);
                        });
                    }
                    return Array.from(out);
                }"""
            )
            for href in extracted or []:
                if href and href not in seen:
                    seen.add(href)
                    endpoints.append({"url": href, "method": "GET", "source": "dom"})
        except Exception as exc:
            logger.debug("[OpenClawEngine] DOM endpoint extraction failed: %s", exc)

        return endpoints

    async def execute_workflow(self, workflow: Dict[str, Any], scan_id: str) -> Dict[str, Any]:
        """Execute multi-step workflow.

        Workflow format:
        {
            "name": "Login and Exploit",
            "steps": [
                {"action": "navigate", "url": "https://example.com/login"},
                {"action": "fill", "selector": "#username", "value": "admin"},
                {"action": "fill", "selector": "#password", "value": "password"},
                {"action": "click", "selector": "#submit"},
                {"action": "wait", "condition": "networkidle"},
                {"action": "extract", "selector": ".secret-data"}
            ]
        }
        """
        if not self.current_page:
            await self._ensure_context()
        page = self.current_page
        results: List[Dict[str, Any]] = []

        for step in workflow.get("steps", []):
            action = step.get("action")
            try:
                if action == "navigate":
                    await page.goto(step["url"])
                    results.append({"step": action, "success": True})
                elif action == "fill":
                    await page.fill(step["selector"], step["value"])
                    results.append({"step": action, "selector": step["selector"], "success": True})
                elif action == "click":
                    await page.click(step["selector"])
                    results.append({"step": action, "selector": step["selector"], "success": True})
                elif action == "wait":
                    condition = step.get("condition", "networkidle")
                    if condition in ("networkidle", "load", "domcontentloaded"):
                        await page.wait_for_load_state(condition)
                    else:
                        await asyncio.sleep(step.get("duration", 1))
                    results.append({"step": action, "success": True})
                elif action == "extract":
                    el = await page.query_selector(step["selector"])
                    text = await el.text_content() if el else None
                    results.append({"step": action, "selector": step["selector"],
                                    "data": text, "success": True})
                else:
                    results.append({"step": action, "success": False,
                                    "error": f"unknown_action:{action}"})
            except Exception as exc:
                results.append({"step": action, "success": False, "error": str(exc)})
                if not step.get("continue_on_error", False):
                    break

        return {"workflow": workflow.get("name", "unnamed"), "results": results}

    async def test_xss_payload(self, url: str, payload: str) -> Dict[str, Any]:
        """Test XSS payload in real browser context."""
        result = await self.navigate(url)
        if not result.get("success"):
            return {"alert_triggered": False, "dom_modified": False, "exploited": False,
                    "payload": payload, "error": result.get("error", "navigation_failed")}
        page = result["page"]

        await page.evaluate("""() => {
            window.__alertFired = false;
            const orig = window.alert;
            window.alert = function() { window.__alertFired = true; return orig.apply(this, arguments); };
        }""")

        dom_before = await page.content()
        try:
            await page.evaluate(
                "(p) => { document.body.innerHTML += p; }",
                payload,
            )
        except Exception:
            # XSS payload may itself raise inside the JS context — that's fine.
            pass

        alert_fired = bool(await page.evaluate("window.__alertFired || false"))
        dom_after = await page.content()
        dom_modified = dom_before != dom_after and payload in dom_after

        return {
            "alert_triggered": alert_fired,
            "dom_modified": dom_modified,
            "console_errors": [],
            "exploited": alert_fired or dom_modified,
            "payload": payload,
        }

    async def detect_framework(self, url: str) -> Optional[str]:
        """Detect JavaScript framework on the page."""
        result = await self.navigate(url)
        if not result.get("success"):
            return None
        page = result["page"]
        try:
            return await page.evaluate("""() => {
                if (window.React || document.querySelector('[data-reactroot]')) return 'React';
                if (window.Vue || document.querySelector('[data-v-]')) return 'Vue';
                if (window.angular || document.querySelector('[ng-app]')) return 'Angular';
                if (window.Ember) return 'Ember';
                if (window.Backbone) return 'Backbone';
                return null;
            }""")
        except Exception as exc:
            logger.debug("[OpenClawEngine] framework detection failed: %s", exc)
            return None

    async def intercept_network(self, url: str) -> List[Dict[str, Any]]:
        """Navigate and return the captured network log for the page."""
        result = await self.navigate(url)
        if not result.get("success"):
            return []
        try:
            await result["page"].wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        return list(self._network_log)

    async def find_websockets(self, url: str) -> List[str]:
        """Find WebSocket URLs initiated by the page.

        Patches WebSocket on a fresh page so we capture connections from page
        load forward.
        """
        await self._ensure_context()
        page = self.current_page
        try:
            await page.add_init_script("""
                (() => {
                    if (!window.__wsCapturing) {
                        window.__capturedWS = [];
                        const Orig = window.WebSocket;
                        window.WebSocket = function(u, p) {
                            window.__capturedWS.push(u);
                            return new Orig(u, p);
                        };
                        window.__wsCapturing = true;
                    }
                })();
            """)
        except Exception:
            pass
        result = await self.navigate(url)
        if not result.get("success"):
            return []
        try:
            captured = await page.evaluate("window.__capturedWS || []")
            return list(captured or [])
        except Exception:
            return []

    async def extract_tokens(self, url: str) -> List[str]:
        """Extract auth tokens from page content + localStorage."""
        result = await self.navigate(url)
        if not result.get("success"):
            return []
        page = result["page"]

        content = await page.content()
        jwt_pattern = r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"
        tokens = set(re.findall(jwt_pattern, content))
        try:
            local_storage = await page.evaluate("() => Object.entries(localStorage)")
            for entry in local_storage or []:
                if not isinstance(entry, list) or len(entry) < 2:
                    continue
                key, value = entry[0], entry[1]
                if isinstance(key, str) and ("token" in key.lower() or "auth" in key.lower()):
                    tokens.add(str(value))
        except Exception:
            pass
        return list(tokens)

    async def capture_screenshot(self, scan_id: str, label: str) -> Optional[Path]:
        """Capture screenshot of the current page."""
        if not self.current_page:
            return None
        screenshot_dir = Path("reports/forensics")
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{scan_id}_{label}_{timestamp}.png"
        filepath = screenshot_dir / filename
        try:
            await self.current_page.screenshot(path=str(filepath), full_page=True)
            return filepath
        except Exception as exc:
            logger.debug("[OpenClawEngine] screenshot failed: %s", exc)
            return None

    async def capture_dom(self, scan_id: str, label: str) -> Optional[Path]:
        """Capture DOM snapshot of the current page."""
        if not self.current_page:
            return None
        dom_dir = Path("reports/forensics")
        dom_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{scan_id}_{label}_{timestamp}.html"
        filepath = dom_dir / filename
        try:
            content = await self.current_page.content()
            filepath.write_text(content, encoding="utf-8")
            return filepath
        except Exception as exc:
            logger.debug("[OpenClawEngine] capture_dom failed: %s", exc)
            return None

    async def get_network_log(self) -> List[Dict[str, Any]]:
        """Return captured network requests for the current page."""
        return list(self._network_log)

    async def get_page_text(self) -> str:
        """Return body text content of current page."""
        if not self.current_page:
            return ""
        try:
            return await self.current_page.text_content("body") or ""
        except Exception:
            return ""

    async def close(self) -> None:
        """Close all contexts and tear down Playwright cleanly."""
        # Close all tracked contexts.
        for ctx in list(self.active_contexts.values()):
            try:
                await ctx.close()
            except Exception as exc:
                logger.debug("[OpenClawEngine] active context close failed: %s", exc)
        self.active_contexts.clear()

        if self.current_context:
            try:
                await self.current_context.close()
            except Exception:
                pass
            self.current_context = None
            self.current_page = None

        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
            self._browser = None
            self.client = None

        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None
