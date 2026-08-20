"""Geeknow Image Provider — 用 /v1/images/generations 端点。

geeknow.top 的图像生成走 OpenAI DALL-E 兼容的 images/generations 端点,
不是 chat/completions。
"""
from __future__ import annotations

import httpx

from app.core.config import settings
from app.providers.base import GenerationResult, ImageProvider, ProviderError, UserProviderConfig


class GeeknowImageProvider(ImageProvider):
    name = "geeknow_image"

    def __init__(self, **kwargs):
        self.api_key = kwargs.get("api_key") or settings.platform_geeknow_api_key
        self.base_url = (
            kwargs.get("base_url") or settings.platform_geeknow_base_url
        ).rstrip("/")

    async def generate_image(
        self,
        *,
        prompt: str,
        model: str | None = None,
        config: UserProviderConfig | None = None,
        size: str = "1024x1024",
        reference_images: list[str] | None = None,
    ) -> GenerationResult:
        """Generate image via /v1/images/generations endpoint."""
        key = (config.api_key if config and config.api_key else self.api_key or "")
        base = (config.base_url if config and config.base_url else self.base_url).rstrip("/")
        if not key:
            raise ProviderError(self.name, "Missing API key")

        used_model = model or (config.model if config and config.model else None) or "gpt-image-2"

        # Convert size like "16:9" → "1792x1024"; "1:1" → "1024x1024"
        w, h = self._parse_size(size)

        body = {
            "model": used_model,
            "prompt": prompt,
            "n": 1,
            "size": f"{w}x{h}",
            "response_format": "url",
        }

        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                f"{base}/images/generations",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=body,
            )
            if r.status_code >= 400:
                raise ProviderError(self.name, f"HTTP {r.status_code}: {r.text[:300]}")
            data = r.json()

        # Response: {"data": [{"url": "..."}]} or {"data": [{"b64_json": "..."}]}
        items = data.get("data", [])
        if not items:
            return GenerationResult(success=False, error="Empty response")

        first = items[0]
        url = first.get("url") or ""
        b64 = first.get("b64_json") or ""

        if not url and b64:
            # 把 b64 当作 url 字段(临时,前端需要能展示)
            url = f"data:image/png;base64,{b64[:200]}..."  # 截断显示

        return GenerationResult(
            success=bool(url),
            output_url=url,
            metadata={"model": used_model, "size": f"{w}x{h}"},
            cost_credits=10,
        )

    @staticmethod
    def _parse_size(size: str) -> tuple[int, int]:
        """Convert aspect ratio or WxH string to (width, height)."""
        if "x" in size:
            try:
                w, h = size.lower().split("x")
                return int(w), int(h)
            except Exception:
                return 1024, 1024
        # Aspect ratio mapping
        mapping = {
            "16:9": (1792, 1024),
            "9:16": (1024, 1792),
            "1:1": (1024, 1024),
            "4:3": (1536, 1152),
        }
        return mapping.get(size, (1024, 1024))