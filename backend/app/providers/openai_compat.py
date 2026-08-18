"""通用 OpenAI 兼容 provider。

适用于任何 OpenAI 兼容的 LLM / 图像 / 视频网关(自部署 / 第三方)。
"""
from __future__ import annotations

import httpx

from app.providers.base import (
    GenerationResult,
    ImageProvider,
    LLMProvider,
    ProviderError,
    UserProviderConfig,
    VideoProvider,
)


class OpenAICompatLLMProvider(LLMProvider):
    name = "openai_compat"

    def __init__(self, *, api_key: str | None = None, base_url: str | None = None, **kwargs):
        self.api_key = api_key
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")

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
        key = (config.api_key if config and config.api_key else self.api_key or "")
        base = (config.base_url if config and config.base_url else self.base_url).rstrip("/")
        if not key:
            raise ProviderError(self.name, "Missing API key")

        used_model = model or (config.model if config and config.model else "gpt-4o-mini")
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        body = {"model": used_model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
        if response_format:
            body["response_format"] = response_format

        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                f"{base}/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=body,
            )
            if r.status_code >= 400:
                raise ProviderError(self.name, f"HTTP {r.status_code}: {r.text[:300]}")
            data = r.json()

        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return GenerationResult(
            success=True,
            text=text,
            metadata={"model": used_model, "usage": usage},
            cost_credits=max(1, usage.get("total_tokens", 0) // 1000),
        )


class OpenAICompatImageProvider(ImageProvider):
    name = "openai_compat"

    def __init__(self, *, api_key: str | None = None, base_url: str | None = None, **kwargs):
        self.api_key = api_key
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")

    async def generate_image(
        self,
        *,
        prompt: str,
        model: str | None = None,
        config: UserProviderConfig | None = None,
        size: str = "1024x1024",
        reference_images: list[str] | None = None,
    ) -> GenerationResult:
        key = (config.api_key if config and config.api_key else self.api_key or "")
        base = (config.base_url if config and config.base_url else self.base_url).rstrip("/")
        if not key:
            raise ProviderError(self.name, "Missing API key")

        used_model = model or (config.model if config and config.model else "gpt-image-1")
        body = {"model": used_model, "prompt": prompt, "size": size, "n": 1}
        if reference_images:
            body["reference_images"] = reference_images

        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                f"{base}/images/generations",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=body,
            )
            if r.status_code >= 400:
                raise ProviderError(self.name, f"HTTP {r.status_code}: {r.text[:300]}")
            data = r.json()

        url = (data.get("data") or [{}])[0].get("url")
        if not url:
            raise ProviderError(self.name, f"No image URL: {data}")
        return GenerationResult(
            success=True, output_url=url,
            metadata={"model": used_model, "size": size},
            cost_credits=10,
        )


class OpenAICompatVideoProvider(VideoProvider):
    """Placeholder: most OpenAI compat gateways don't expose video yet.

    Uses image endpoint as a fallback (returns a 'video' that's actually an image).
    Real impl: extend when provider supports / /v1/videos/generations.
    """
    name = "openai_compat"

    def __init__(self, *, api_key: str | None = None, base_url: str | None = None, **kwargs):
        self.api_key = api_key
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")

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
        raise ProviderError(
            self.name,
            "OpenAI compatible video not implemented in v2.0 — use toapis or yijia.",
        )