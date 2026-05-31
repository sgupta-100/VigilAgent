"""
PinchTabEngine: Fast browser operations using the PinchTab control plane.

When the PinchTab control plane is offline (the common case in many local
labs), this engine degrades silently:
  - ``initialize()`` returns ``False`` after a single boot-time INFO log.
  - ``is_available()`` returns ``False`` so the orchestrator can route around it.
  - All public methods short-circuit with empty / failure results, never
    raising and never spamming the log.

When the control plane IS reachable it provides:
  - Fast DOM scraping
  - Token extraction
  - Quick navigation
  - Simple injection testing
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

from backend.integrations.pinchtab_client import PinchTabClient, PinchTabUnavailable

logger = logging.getLogger(__name__)


class PinchTabEngine:
    """Fast browser operations using PinchTab (degrades silently when offline)."""

    def __init__(self) -> None:
        self.client = PinchTabClient()
        self.last_tab_id: str | None = None
        self.last_url: str | None = None
        self._available: bool = False

    async def initialize(self) -> bool:
        """Probe the control plane. Returns True iff PinchTab is reachable.

        Emits a single boot-time INFO log when the control plane is offline; the
        orchestrator reads ``self._available`` (or ``is_available()``) to route
        around the engine.
        """
        try:
            self._available = await self.client.is_available()
        except Exception as exc:  # defensive — should not happen
            logger.info(
                "[PinchTabEngine] availability probe failed: %s: %s",
                type(exc).__name__, str(exc)[:120],
            )
            self._available = False

        if self._available:
            logger.info("[PinchTabEngine] control plane online at %s", self.client.base_url)
        # When offline the client itself emits exactly one INFO log.
        return self._available

    def is_available(self) -> bool:
        """Synchronous accessor used by the orchestrator and intel modules."""
        return bool(self._available)

    # ── helpers ─────────────────────────────────────────────────────────────

    async def _ensure_available(self) -> bool:
        """Recheck availability lazily so the engine can recover if PinchTab
        comes online mid-scan, but never spams the network."""
        if self._available:
            return True
        # Use the cheap cached probe.
        self._available = await self.client.is_available()
        return self._available

    # ── public API ──────────────────────────────────────────────────────────

    async def navigate(self, url: str) -> Dict[str, Any]:
        """Fast navigation to URL."""
        if not await self._ensure_available():
            return {"tab_id": None, "url": url, "success": False, "error": "pinchtab_offline"}
        try:
            result = await self.client.navigate(url)
            self.last_tab_id = result.get("tabId") or result.get("id") or result.get("targetId")
            self.last_url = url
            return {"tab_id": self.last_tab_id, "url": url, "success": True}
        except PinchTabUnavailable as exc:
            self._available = False
            return {"tab_id": None, "url": url, "success": False, "error": str(exc)}
        except Exception as exc:
            logger.debug("[PinchTabEngine] navigate(%s) failed: %s", url, exc)
            return {"tab_id": None, "url": url, "success": False, "error": str(exc)}

    async def extract_endpoints_fast(self, url: str) -> List[str]:
        """Fast endpoint extraction using regex over page text."""
        if not await self._ensure_available():
            return []
        nav = await self.navigate(url)
        if not nav.get("success") or not self.last_tab_id:
            return []
        try:
            text = await self.client.text(self.last_tab_id)
            text_str = str(text)
            endpoints: set[str] = set()
            patterns = [
                r"['\"](/(?:api|v\d+)/[^'\"]+)['\"]",
                r"['\"](/(?:graphql|rest|rpc)[^'\"]*)['\"]",
                r"fetch\(['\"]([^'\"]+)['\"]",
                r"axios\.[a-z]+\(['\"]([^'\"]+)['\"]",
            ]
            for pattern in patterns:
                for match in re.findall(pattern, text_str, re.IGNORECASE):
                    if isinstance(match, tuple):
                        match = match[0] if match else ""
                    if match:
                        endpoints.add(match.strip("'\""))
            return list(endpoints)
        except PinchTabUnavailable:
            self._available = False
            return []
        except Exception as exc:
            logger.debug("[PinchTabEngine] extract_endpoints_fast failed: %s", exc)
            return []

    async def extract_tokens(self, url: str) -> List[str]:
        """Fast token extraction (JWT / Bearer / API keys)."""
        if not await self._ensure_available():
            return []
        nav = await self.navigate(url)
        if not nav.get("success") or not self.last_tab_id:
            return []
        try:
            text = await self.client.text(self.last_tab_id)
            text_str = str(text)
            tokens: set[str] = set()
            tokens.update(re.findall(
                r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", text_str))
            tokens.update(re.findall(
                r"Bearer\s+([A-Za-z0-9_-]{20,})", text_str, re.IGNORECASE))
            tokens.update(re.findall(
                r"['\"]?api[_-]?key['\"]?\s*[:=]\s*['\"]([^'\"]{20,})['\"]",
                text_str, re.IGNORECASE))
            return list(tokens)
        except PinchTabUnavailable:
            self._available = False
            return []
        except Exception as exc:
            logger.debug("[PinchTabEngine] extract_tokens failed: %s", exc)
            return []

    async def test_injection(self, url: str, payload: str,
                             method: str = "GET") -> Dict[str, Any]:
        """Fast injection test — checks if payload is reflected in response."""
        if not await self._ensure_available():
            return {"reflected": False, "error": "pinchtab_offline"}
        test_url = f"{url}{'&' if '?' in url else '?'}test={payload}"
        nav = await self.navigate(test_url)
        if not nav.get("success") or not self.last_tab_id:
            return {"reflected": False, "error": nav.get("error", "navigation_failed")}
        try:
            text = await self.client.text(self.last_tab_id)
            text_str = str(text)
            return {"reflected": payload in text_str, "payload": payload, "url": test_url}
        except PinchTabUnavailable:
            self._available = False
            return {"reflected": False, "error": "pinchtab_offline"}
        except Exception as exc:
            return {"reflected": False, "error": str(exc)}

    async def analyze_dom(self, url: str) -> Dict[str, Any]:
        """Analyze DOM structure (forms, inputs, buttons)."""
        if not await self._ensure_available():
            return {}
        nav = await self.navigate(url)
        if not nav.get("success") or not self.last_tab_id:
            return {}
        try:
            text = await self.client.text(self.last_tab_id)
            snapshot = await self.client.snapshot(self.last_tab_id)
            text_str = str(text)
            forms = [{"action": a} for a in re.findall(
                r'<form[^>]*action=["\']([^"\']+)["\']', text_str, re.IGNORECASE)]
            inputs = [{"name": n, "type": t} for n, t in re.findall(
                r'<input[^>]*name=["\']([^"\']+)["\'][^>]*type=["\']([^"\']+)["\']',
                text_str, re.IGNORECASE)]
            buttons = [{"text": b} for b in re.findall(
                r'<button[^>]*>([^<]+)</button>', text_str, re.IGNORECASE)]
            return {
                "forms": forms,
                "inputs": inputs,
                "buttons": buttons,
                "text": text_str[:1000],
                "snapshot": snapshot,
            }
        except PinchTabUnavailable:
            self._available = False
            return {}
        except Exception as exc:
            logger.debug("[PinchTabEngine] analyze_dom failed: %s", exc)
            return {}

    async def get_page_text(self) -> str:
        """Get page text content for the last opened tab."""
        if not self._available or not self.last_tab_id:
            return ""
        try:
            return str(await self.client.text(self.last_tab_id))
        except PinchTabUnavailable:
            self._available = False
            return ""
        except Exception as exc:
            logger.debug("[PinchTabEngine] get_page_text failed: %s", exc)
            return ""

    async def close(self) -> None:
        """Cleanup. PinchTab manages its own browser lifecycle, so this is
        primarily about clearing references."""
        self.last_tab_id = None
        self.last_url = None
