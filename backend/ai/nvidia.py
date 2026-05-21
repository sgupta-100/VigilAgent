import asyncio
import logging
import os
import time as _time
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

logger = logging.getLogger("NVIDIA")

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
NVIDIA_DUMMY_API_KEY = "api key"
NVIDIA_PAYLOAD_MODEL = "qwen/qwen2.5-coder-32b-instruct"
NVIDIA_VALIDATION_MODEL = "nvidia/llama-3.1-nemotron-nano-8b-v1"
NVIDIA_TIMEOUT = 120


class NvidiaClient:
    """Async OpenAI-compatible client for NVIDIA NIM hosted models."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        payload_api_key: Optional[str] = None,
        validation_api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        load_dotenv(override=True)

        self.base_url = (base_url or os.getenv("NVIDIA_BASE_URL", NVIDIA_BASE_URL)).rstrip("/")
        default_api_key = api_key or os.getenv("NVIDIA_API_KEY", NVIDIA_DUMMY_API_KEY)
        self._payload_api_key = payload_api_key or os.getenv("NVIDIA_PAYLOAD_API_KEY", default_api_key)
        self._validation_api_key = validation_api_key or os.getenv("NVIDIA_VALIDATION_API_KEY", default_api_key)
        self._client = None
        self._client_api_key = ""
        self._import_error = ""
        self._telemetry = {
            "calls": 0,
            "successes": 0,
            "errors": 0,
            "total_latency": 0.0,
        }

        if self.is_available:
            logger.info("NVIDIA: Client initialized -> base_url=%s", self.base_url)
        else:
            logger.warning("NVIDIA: Using dummy API key. Set NVIDIA_API_KEY to enable cloud inference.")

    @property
    def is_available(self) -> bool:
        return self._has_key(self._payload_api_key) or self._has_key(self._validation_api_key)

    @staticmethod
    def _has_key(api_key: str) -> bool:
        return bool(api_key and api_key.strip() and api_key != NVIDIA_DUMMY_API_KEY)

    async def _ensure_client(self, api_key: str):
        if self._client is not None and self._client_api_key == api_key:
            return
        if self._client is not None:
            await self.close()
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            self._import_error = str(exc)
            logger.warning("NVIDIA: openai package is not installed.")
            return

        self._client = AsyncOpenAI(
            base_url=self.base_url,
            api_key=api_key,
            timeout=NVIDIA_TIMEOUT,
        )
        self._client_api_key = api_key

    async def chat(
        self,
        *,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float,
        top_p: float,
        max_tokens: int,
        frequency_penalty: float = 0,
        presence_penalty: float = 0,
        stream: bool = True,
        scan_ctx=None,
        api_key: Optional[str] = None,
    ) -> str:
        request_api_key = api_key or self._payload_api_key
        if not self._has_key(request_api_key):
            return "[NVIDIA OFFLINE] NVIDIA_API_KEY is not configured."

        if scan_ctx and getattr(scan_ctx, "is_cancelled", False):
            raise asyncio.CancelledError()

        await self._ensure_client(request_api_key)
        if self._client is None:
            reason = self._import_error or "OpenAI client unavailable"
            return f"[NVIDIA ERROR] {reason}"

        self._telemetry["calls"] += 1
        call_start = _time.perf_counter()

        try:
            completion = await self._client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
                frequency_penalty=frequency_penalty,
                presence_penalty=presence_penalty,
                stream=stream,
            )

            if stream:
                chunks = []
                async for chunk in completion:
                    if scan_ctx and getattr(scan_ctx, "is_cancelled", False):
                        raise asyncio.CancelledError()
                    if chunk.choices and chunk.choices[0].delta.content is not None:
                        chunks.append(chunk.choices[0].delta.content)
                result = "".join(chunks).strip()
            else:
                result = completion.choices[0].message.content or ""
                result = result.strip()

            latency = _time.perf_counter() - call_start
            self._telemetry["successes"] += 1
            self._telemetry["total_latency"] += latency
            logger.info("NVIDIA: %s succeeded in %.2fs", model, latency)
            return result

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._telemetry["errors"] += 1
            logger.error("NVIDIA: %s failed: %s", model, exc)
            return f"[NVIDIA ERROR] {type(exc).__name__}: {exc}"

    async def generate_payloads(self, prompt: str, *, max_tokens: int = 1024, scan_ctx=None) -> str:
        return await self.chat(
            model=NVIDIA_PAYLOAD_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            top_p=0.7,
            max_tokens=min(max_tokens, 1024),
            stream=True,
            scan_ctx=scan_ctx,
            api_key=self._payload_api_key,
        )

    async def validate_candidate(self, prompt: str, *, max_tokens: int = 4096, scan_ctx=None) -> str:
        return await self.chat(
            model=NVIDIA_VALIDATION_MODEL,
            messages=[
                {"role": "system", "content": "detailed thinking off"},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            top_p=0.95,
            max_tokens=min(max_tokens, 4096),
            frequency_penalty=0,
            presence_penalty=0,
            stream=True,
            scan_ctx=scan_ctx,
            api_key=self._validation_api_key,
        )

    async def close(self):
        if self._client is None:
            return
        maybe_close = self._client.close()
        if asyncio.iscoroutine(maybe_close):
            await maybe_close
        self._client = None
        self._client_api_key = ""


nvidia_client = NvidiaClient()
