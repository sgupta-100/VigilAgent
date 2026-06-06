"""
Alpha Unified — Browser Recon Module (Architecture §5.1.1, §5.1)
================================================================================
Legacy Alpha browser-intelligence behaviors, merged INTO the Alpha V6 runtime
spine as a module (Architecture §5.1.1: "Move useful legacy Alpha behaviors into
Alpha V6 as modules"). This eliminates the second recon orchestration path that
previously lived in agents/alpha.py.

Provides browser-aware recon (Architecture §5.1.1 Alpha Unified responsibilities):
  - SPA detection (React/Vue/Angular/Svelte)
  - JavaScript route extraction
  - XHR/fetch network interception
  - WebSocket discovery
  - Security headers, forms, cookies
  - endpoint merge/dedupe → ParsedEntity for the entity engine

It drives Delta/Prism/OpenClaw/PinchTab via the shared BrowserOrchestrator and
normalizes everything into ParsedEntity records so the single entity engine,
scoring, and artifact store handle them (no duplicate storage/scoring).
"""
from __future__ import annotations

import logging
from typing import Any

from backend.parsers.recon.base import ParsedEntity

logger = logging.getLogger("alpha.browser_recon")

_SPA_FRAMEWORKS = {"react", "vue", "angular", "svelte"}

# Headers we want to inspect for security misconfiguration.
_SECURITY_HEADERS = (
    "content-security-policy",
    "strict-transport-security",
    "x-frame-options",
    "x-content-type-options",
    "referrer-policy",
    "permissions-policy",
)


class BrowserReconModule:
    """Browser-aware recon, normalized into ParsedEntity records."""

    def __init__(self, browser, scan_id: str, *, agent_name: str = "agent_alpha"):
        # ``browser`` is the shared BrowserOrchestrator (OpenClaw + PinchTab).
        self.browser = browser
        self.scan_id = scan_id
        self.agent_name = agent_name

    async def recon(self, url: str) -> list[ParsedEntity]:
        """Run browser recon for ``url``; return normalized entities.

        Safe-degrades: if no browser engine is available, returns []. Always
        runs forms+cookies extraction even for non-SPA targets so simple apps
        like DVWA still produce a meaningful entity set.
        """
        entities: list[ParsedEntity] = []
        if self.browser is None:
            return entities

        # 1) Navigate + framework detection.
        is_spa = False
        nav_ok = False
        try:
            result = await self.browser.navigate(url, stealth=False, wait_for="networkidle")
            nav_ok = bool(result.get("success"))
        except Exception as exc:
            logger.info("[BrowserRecon] navigate(%s) failed: %s: %s",
                         url, type(exc).__name__, str(exc)[:200])

        if nav_ok:
            try:
                framework = await self.browser.detect_framework(url)
                is_spa = str(framework or "").lower() in _SPA_FRAMEWORKS
            except Exception as exc:
                logger.debug("[BrowserRecon] framework detection failed: %s", exc)
                is_spa = False

        # 2) Endpoints (DOM links, network requests captured by Playwright,
        #    framework routers).
        endpoints = await self._extract_endpoints(url)
        network = await self._intercept_network(url)
        js_routes = await self._extract_js_routes(url)
        websockets = await self._find_websockets(url)

        merged = self._merge(endpoints, network, js_routes, websockets)
        for ep in merged:
            kind = "browser_endpoint"
            src = ep.get("source", "browser")
            if ep.get("method") == "WS" or src == "websocket_monitor":
                kind = "websocket"
            elif "router" in src:
                kind = "javascript_route"
            entities.append(ParsedEntity(
                kind=kind,
                label=str(ep.get("url", "")),
                confidence=0.7,
                source_tool=src,
                phase="http_browser_intelligence",
                properties={"method": ep.get("method", "GET"), "source": src,
                            "spa": is_spa, "headers": ep.get("headers", {}),
                            "scan_id": self.scan_id},
            ))

        # 3) Forms, cookies, security headers — direct probes into the live
        #    OpenClaw page. These work for both SPA and classic apps and
        #    guarantee at least a few entities for any reachable URL.
        if nav_ok:
            entities.extend(await self._extract_forms(url))
            entities.extend(await self._extract_cookies(url))
            entities.extend(await self._extract_security_headers(url))

        logger.info("[BrowserRecon] %s: %d browser entities (spa=%s, nav_ok=%s)",
                     url, len(entities), is_spa, nav_ok)
        return entities

    # ── Browser primitives (delegated to the shared orchestrator) ─────────────

    async def _extract_endpoints(self, url: str) -> list[dict[str, Any]]:
        try:
            eps = await self.browser.extract_endpoints(url, deep=True)
            return [{"url": e.get("url"), "method": e.get("method", "GET"),
                     "source": e.get("source", "browser")} for e in (eps or [])
                    if isinstance(e, dict) and e.get("url")]
        except Exception as exc:
            logger.debug("[BrowserRecon] _extract_endpoints failed: %s", exc)
            return []

    async def _intercept_network(self, url: str) -> list[dict[str, Any]]:
        try:
            evts = await self.browser.intercept_network(url)
            out: list[dict[str, Any]] = []
            for e in (evts or []):
                if not isinstance(e, dict):
                    continue
                u = e.get("url")
                if not u:
                    continue
                out.append({
                    "url": u,
                    "method": e.get("method", "GET"),
                    "source": "network_intercept",
                    "headers": e.get("headers", {}),
                })
            return out
        except Exception as exc:
            logger.debug("[BrowserRecon] _intercept_network failed: %s", exc)
            return []

    async def _find_websockets(self, url: str) -> list[dict[str, Any]]:
        try:
            ws_urls = await self.browser.find_websockets(url)
            return [{"url": w, "method": "WS", "source": "websocket_monitor"}
                    for w in (ws_urls or []) if w]
        except Exception as exc:
            logger.debug("[BrowserRecon] _find_websockets failed: %s", exc)
            return []

    async def _extract_js_routes(self, url: str) -> list[dict[str, Any]]:
        try:
            framework = await self.browser.detect_framework(url)
            page = getattr(getattr(self.browser, "openclaw", None), "current_page", None)
            if page is None:
                return []
            fw = str(framework or "").lower()
            if fw == "react":
                js = """() => { const r=[]; if(window.__REACT_ROUTER__&&window.__REACT_ROUTER__.routes){window.__REACT_ROUTER__.routes.forEach(x=>{if(x.path)r.push({url:x.path,method:'GET',source:'react_router'})})} document.querySelectorAll('[data-route]').forEach(e=>{const p=e.getAttribute('data-route'); if(p)r.push({url:p,method:'GET',source:'react_dom'})}); return r; }"""
            elif fw == "vue":
                js = """() => { const r=[]; if(window.$router&&window.$router.options){(window.$router.options.routes||[]).forEach(x=>{if(x.path)r.push({url:x.path,method:'GET',source:'vue_router'})})} return r; }"""
            elif fw == "angular":
                js = """() => { const r=[]; if(window.ng&&window.ng.probe){(window.ng.probe.getAllRoutes?.()||[]).forEach(x=>{if(x.path)r.push({url:x.path,method:'GET',source:'angular_router'})})} return r; }"""
            else:
                return []
            routes = await page.evaluate(js)
            return [r for r in (routes or []) if isinstance(r, dict) and r.get("url")]
        except Exception as exc:
            logger.debug("[BrowserRecon] JS route extraction failed: %s", exc)
            return []

    async def _extract_forms(self, url: str) -> list[ParsedEntity]:
        """Pull <form> action/method/inputs from the current page."""
        page = getattr(getattr(self.browser, "openclaw", None), "current_page", None)
        if page is None:
            return []
        try:
            forms = await page.eval_on_selector_all(
                "form",
                """elements => elements.map(f => ({
                    action: f.getAttribute('action') || '',
                    method: (f.getAttribute('method') || 'GET').toUpperCase(),
                    inputs: Array.from(f.querySelectorAll('input,select,textarea'))
                        .map(i => ({
                            name: i.getAttribute('name') || '',
                            type: i.getAttribute('type') || i.tagName.toLowerCase(),
                            id: i.id || ''
                        }))
                }))""",
            )
        except Exception as exc:
            logger.debug("[BrowserRecon] form extraction failed: %s", exc)
            return []

        entities: list[ParsedEntity] = []
        for form in forms or []:
            if not isinstance(form, dict):
                continue
            action = form.get("action", "") or url
            entities.append(ParsedEntity(
                kind="form",
                label=action or url,
                confidence=0.85,
                source_tool="openclaw",
                phase="http_browser_intelligence",
                properties={
                    "action": action,
                    "method": form.get("method", "GET"),
                    "inputs": form.get("inputs", []),
                    "source_url": url,
                    "scan_id": self.scan_id,
                },
            ))
        return entities

    async def _extract_cookies(self, url: str) -> list[ParsedEntity]:
        """Pull cookies set on the current browser context."""
        ctx = getattr(getattr(self.browser, "openclaw", None), "current_context", None)
        if ctx is None:
            return []
        try:
            cookies = await ctx.cookies()
        except Exception as exc:
            logger.debug("[BrowserRecon] cookie extraction failed: %s", exc)
            return []

        entities: list[ParsedEntity] = []
        for c in cookies or []:
            if not isinstance(c, dict):
                continue
            name = c.get("name", "")
            httponly = bool(c.get("httpOnly", False))
            secure = bool(c.get("secure", False))
            samesite = str(c.get("sameSite", ""))
            kind = "cookie"
            confidence = 0.7
            # Insecure cookies get flagged as candidates so the finding pipeline
            # can pick them up.
            if not httponly or not secure:
                kind = "insecure_cookie"
                confidence = 0.8
            entities.append(ParsedEntity(
                kind=kind,
                label=f"{name}@{c.get('domain', '')}",
                confidence=confidence,
                source_tool="openclaw_cookies",
                phase="http_browser_intelligence",
                properties={
                    "name": name,
                    "domain": c.get("domain", ""),
                    "path": c.get("path", "/"),
                    "httpOnly": httponly,
                    "secure": secure,
                    "sameSite": samesite,
                    "source_url": url,
                    "scan_id": self.scan_id,
                },
            ))
        return entities

    async def _extract_security_headers(self, url: str) -> list[ParsedEntity]:
        """Inspect response headers captured during navigation."""
        try:
            log = await self.browser.get_network_log()
        except Exception as exc:
            logger.debug("[BrowserRecon] network log retrieval failed: %s", exc)
            return []
        if not log:
            return []

        # The OpenClaw engine only logs request side; for headers we read the
        # latest main-frame document via JS. The page exposes
        # Response.headers via the document.* APIs only indirectly, so we use
        # a fetch HEAD for the same URL inside the page context.
        page = getattr(getattr(self.browser, "openclaw", None), "current_page", None)
        if page is None:
            return []
        try:
            headers = await page.evaluate(
                """async (u) => {
                    try {
                        const r = await fetch(u, { method: 'HEAD', credentials: 'include' });
                        const out = {};
                        r.headers.forEach((v, k) => { out[k.toLowerCase()] = v; });
                        return out;
                    } catch (e) {
                        return {};
                    }
                }""",
                url,
            )
        except Exception as exc:
            logger.debug("[BrowserRecon] security header probe failed: %s", exc)
            return []

        if not isinstance(headers, dict) or not headers:
            return []

        entities: list[ParsedEntity] = []
        present = {h: headers[h] for h in _SECURITY_HEADERS if h in headers}
        missing = [h for h in _SECURITY_HEADERS if h not in headers]

        if present or missing:
            entities.append(ParsedEntity(
                kind="security_headers",
                label=url,
                confidence=0.8,
                source_tool="openclaw",
                phase="http_browser_intelligence",
                properties={
                    "url": url,
                    "present": present,
                    "missing": missing,
                    "all_headers": headers,
                    "scan_id": self.scan_id,
                },
            ))
        return entities

    @staticmethod
    def _merge(*lists) -> list[dict[str, Any]]:
        seen: set[str] = set()
        merged: list[dict[str, Any]] = []
        for lst in lists:
            for ep in lst:
                u = ep.get("url", "")
                if u and u not in seen:
                    seen.add(u)
                    merged.append(ep)
        return merged
