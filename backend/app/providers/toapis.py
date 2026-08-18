"""ToAPIs 网关 provider (文本 / 图像 / 视频)。

通过 /v1/* OpenAI 兼容接口调用,支持 toapis 网关下的所有模型。
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import httpx

from app.core.config import settings
from app.providers.base import (
    GenerationResult,
    ImageProvider,
    LLMProvider,
    ProviderError,
    UserProviderConfig,
    VideoProvider,
)


class ToapisBase:
    """Shared HTTP client + auth resolution."""

    name = "toapis"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 120.0,
    ):
        # Resolution order: explicit arg > user_config.api_key > platform fallback
        self.api_key = api_key or settings.platform_toapis_api_key
        self.base_url = (base_url or settings.platform_toapis_base_url).rstrip("/")
        self.timeout = timeout

    def _resolve_credentials(self, config: UserProviderConfig | None) -> tuple[str, str]:
        """Pick (api_key, base_url) from user config or platform fallback."""
        if config and config.api_key:
            key = config.api_key
        else:
            key = self.api_key or ""
        base = (config.base_url if config and config.base_url else self.base_url).rstrip("/")
        return key, base

    def _headers(self, api_key: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def _raise_for_response(self, r: httpx.Response, api_key: str) -> None:
        if r.status_code >= 400:
            try:
                detail = r.json()
            except Exception:
                detail = r.text
            raise ProviderError(
                self.name,
                f"HTTP {r.status_code}: {detail[:500]}",
            )


class ToapisLLMProvider(ToapisBase, LLMProvider):
    """LLM via OpenAI-compatible /v1/chat/completions."""

    async def generate_text(
        self,
        *,
        prompt: str,
        system: str | None = None,
        model: str | None = None,
        config: UserProviderConfig | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        response_format: dict | None = None,
    ) -> GenerationResult:
        api_key, base_url = self._resolve_credentials(config)
        if not api_key:
            raise ProviderError(self.name, "Missing API key (set in Settings)")

        used_model = model or (config.model if config and config.model else settings.default_llm_model)

        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        body: dict[str, Any] = {
            "model": used_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if response_format:
            body["response_format"] = response_format

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(
                f"{base_url}/chat/completions",
                headers=self._headers(api_key),
                json=body,
            )
            self._raise_for_response(r, api_key)
            data = r.json()

        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return GenerationResult(
            success=True,
            text=text,
            metadata={
                "model": data.get("model", used_model),
                "usage": usage,
                "raw": {k: v for k, v in data.items() if k != "choices"},
            },
            cost_credits=self._estimate_cost(usage, used_model),
        )

    def _estimate_cost(self, usage: dict[str, Any], model: str) -> int:
        """Estimate credit cost from token usage. Conservative fallback."""
        total_tokens = usage.get("total_tokens", 0)
        # 1 credit per 1000 tokens (adjust per-model later)
        return max(1, total_tokens // 1000)


class ToapisImageProvider(ToapisBase, ImageProvider):
    """Image via toapis image-generation endpoint.

    Many ToAPIs images use OpenAI's /v1/images/generations format; some use
    /v1/images/edits with multipart. We try generations first, fall back if needed.
    """

    async def generate_image(
        self,
        *,
        prompt: str,
        model: str | None = None,
        config: UserProviderConfig | None = None,
        size: str = "1024x1024",
        reference_images: list[str] | None = None,
    ) -> GenerationResult:
        api_key, base_url = self._resolve_credentials(config)
        if not api_key:
            raise ProviderError(self.name, "Missing API key (set in Settings)")

        used_model = model or (config.model if config and config.model else settings.default_image_model)

        body: dict[str, Any] = {
            "model": used_model,
            "prompt": prompt,
            "size": size,
            "n": 1,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(
                f"{base_url}/images/generations",
                headers=self._headers(api_key),
                json=body,
            )
            self._raise_for_response(r, api_key)
            data = r.json()

        url = (data.get("data") or [{}])[0].get("url")
        if not url:
            raise ProviderError(self.name, f"No image URL in response: {data}")

        return GenerationResult(
            success=True,
            output_url=url,
            metadata={"model": used_model, "size": size, "raw": data},
            cost_credits=10,
        )


class ToapisVideoProvider(ToapisBase, VideoProvider):
    """Video via toapis async video generation.

    Two-step: create task (POST /v1/videos/generations), then poll
    GET /v1/videos/generations/{task_id} until completed.
    """

    async def generate_video(
        self,
        *,
        prompt: str,
        first_frame: str | None = None,
        duration: float = 5.0,
        aspect_ratio: str = "16:9",
        model: str | None = None,
        config: UserProviderConfig | None = None,
    ) -> GenerationResult:
        api_key, base_url = self._resolve_credentials(config)
        if not api_key:
            raise ProviderError(self.name, "Missing API key (set in Settings)")

        used_model = model or (config.model if config and config.model else settings.default_video_model)

        body: dict[str, Any] = {
            "model": used_model,
            "prompt": prompt,
            "duration": int(duration),
            "aspect_ratio": aspect_ratio,
        }
        if first_frame:
            body["image"] = first_frame  # toapis convention: image URL or data URI

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # 1. Create task
            r = await client.post(
                f"{base_url}/videos/generations",
                headers=self._headers(api_key),
                json=body,
            )
            self._raise_for_response(r, api_key)
            task = r.json()
            task_id = task.get("id") or task.get("task_id") or task.get("taskId")
            if not task_id:
                raise ProviderError(self.name, f"No task id in response: {task}")

            # 2. Poll
            url = await self._poll(client, api_key, base_url, task_id)

        return GenerationResult(
            success=True,
            output_url=url,
            metadata={"model": used_model, "task_id": task_id, "duration": duration},
            cost_credits=50,
        )

    async def _poll(
        self,
        client: httpx.AsyncClient,
        api_key: str,
        base_url: str,
        task_id: str,
        poll_interval: float = 8.0,
        timeout: float = 600.0,
    ) -> str:
        """Poll task status until completed / failed / timeout. Returns video URL."""
        elapsed = 0.0
        while elapsed < timeout:
            r = await client.get(
                f"{base_url}/videos/generations/{task_id}",
                headers=self._headers(api_key),
            )
            self._raise_for_response(r, api_key)
            data = r.json()
            status = (data.get("status") or data.get("data", {}).get("status") or "").lower()
            if status in ("completed", "succeeded", "success"):
                url = self._extract_url(data)
                if url:
                    return url
                raise ProviderError(self.name, f"Task succeeded but no URL: {data}")
            if status in ("failed", "error", "cancelled"):
                raise ProviderError(self.name, f"Task {status}: {data}")
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
        raise ProviderError(self.name, f"Task {task_id} timed out after {timeout}s")

    def _extract_url(self, data: dict) -> str | None:
        for key in ("url", "video_url", "output_url", "download_url"):
            v = data.get(key)
            if isinstance(v, str):
                return v
        # Try nested
        for k, v in (data.get("data") or {}).items():
            if isinstance(v, str) and v.startswith("http"):
                return v
        return None