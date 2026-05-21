from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, TypeAlias

import aiohttp

from backend.core.config import settings

JSONDict: TypeAlias = dict[str, Any]
PinchTabPayload: TypeAlias = JSONDict | list[Any] | str | bytes


class PinchTabClient:
    def __init__(self, base_url: str | None = None, timeout: int = 30):
        self.base_url = (base_url or getattr(settings, "PINCHTAB_BASE_URL", "http://127.0.0.1:9867")).rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=timeout)

    async def health(self) -> JSONDict:
        return await self._request_json("GET", "/health")

    async def create_profile(self, name: str, description: str = "") -> JSONDict:
        return await self._request_json("POST", "/profiles", json={"name": name, "description": description})

    async def start_instance(self, profile_id: str | None = None, *, mode: str = "headless") -> JSONDict:
        payload: JSONDict = {"mode": mode}
        if profile_id:
            payload["profileId"] = profile_id
        return await self._request_json("POST", "/instances/start", json=payload)

    async def stop_instance(self, instance_id: str) -> JSONDict:
        return await self._request_json("POST", f"/instances/{instance_id}/stop")

    async def navigate(self, url: str, *, tab_id: str | None = None, wait_for: str = "networkidle") -> JSONDict:
        payload: JSONDict = {"url": url, "waitFor": wait_for, "blockMedia": True}
        if tab_id:
            payload["tabId"] = tab_id
        return await self._request_json("POST", "/navigate", json=payload)

    async def snapshot(self, tab_id: str, *, max_tokens: int = 1200) -> PinchTabPayload:
        return await self._request("GET", f"/tabs/{tab_id}/snapshot?interactive=true&compact=true&maxTokens={max_tokens}")

    async def text(self, tab_id: str, *, max_chars: int = 20000) -> PinchTabPayload:
        return await self._request("GET", f"/tabs/{tab_id}/text?format=text&maxChars={max_chars}")

    async def network(self, tab_id: str, *, limit: int = 200) -> JSONDict:
        return await self._request_json("GET", f"/tabs/{tab_id}/network?limit={limit}")

    async def network_detail(self, tab_id: str, request_id: str, *, body: bool = False) -> JSONDict:
        include_body = "true" if body else "false"
        return await self._request_json("GET", f"/tabs/{tab_id}/network/{request_id}?body={include_body}")

    async def console(self, tab_id: str, *, limit: int = 100) -> JSONDict:
        return await self._request_json("GET", f"/console?tabId={tab_id}&limit={limit}")

    async def errors(self, tab_id: str, *, limit: int = 100) -> JSONDict:
        return await self._request_json("GET", f"/errors?tabId={tab_id}&limit={limit}")

    async def cookies(self, tab_id: str) -> JSONDict:
        return await self._request_json("GET", f"/tabs/{tab_id}/cookies")

    async def wait_for_load(self, tab_id: str, *, timeout_ms: int = 30000) -> JSONDict:
        return await self._request_json("POST", f"/tabs/{tab_id}/wait", json={"load": "networkidle", "timeout": timeout_ms})

    async def action(
        self,
        tab_id: str,
        kind: str,
        *,
        selector: str | None = None,
        text: str | None = None,
        value: str | None = None,
        wait_nav: bool = False,
    ) -> JSONDict:
        payload: JSONDict = {"kind": kind, "tabId": tab_id}
        if selector:
            payload["selector"] = selector
        if text is not None:
            payload["text"] = text
        if value is not None:
            payload["value"] = value
        if wait_nav:
            payload["waitNav"] = True
        return await self._request_json("POST", f"/tabs/{tab_id}/action", json=payload)

    async def screenshot(self, tab_id: str, output_path: str | Path) -> str:
        result = await self._request("GET", f"/tabs/{tab_id}/screenshot?format=png")
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(result, dict):
            data = result.get("data") or result.get("base64") or result.get("content")
            if data:
                path.write_bytes(base64.b64decode(str(data).split(",", 1)[-1]))
            else:
                path.write_text(str(result), encoding="utf-8")
        elif isinstance(result, bytes):
            path.write_bytes(result)
        else:
            path.write_text(str(result), encoding="utf-8")
        return str(path)

    async def close_tab(self, tab_id: str) -> JSONDict:
        return await self._request_json("POST", f"/tabs/{tab_id}/close")

    async def _request_json(self, method: str, path: str, **kwargs: Any) -> JSONDict:
        result = await self._request(method, path, **kwargs)
        if isinstance(result, dict):
            return result
        return {"raw": result}

    async def _request(self, method: str, path: str, **kwargs: Any) -> PinchTabPayload:
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.request(method, f"{self.base_url}{path}", **kwargs) as resp:
                content_type = resp.headers.get("content-type", "")
                if "application/json" in content_type:
                    return await resp.json()
                if content_type.startswith("image/") or content_type == "application/octet-stream":
                    return await resp.read()
                return await resp.text()
