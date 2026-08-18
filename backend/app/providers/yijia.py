"""易加 AI 网关 provider (图像 / 视频)。

复用 ToAPIs 同款 HTTP 调用,但 base_url 不同。
"""
from __future__ import annotations

import httpx

from app.core.config import settings
from app.providers.base import (
    GenerationResult,
    ImageProvider,
    ProviderError,
    UserProviderConfig,
    VideoProvider,
)
from app.providers.toapis import ToapisBase


class YijiaBase(ToapisBase):
    name = "yijia"

    def __init__(self, *, api_key: str | None = None, base_url: str | None = None, **kwargs):
        super().__init__(
            api_key=api_key or settings.platform_yijia_api_key,
            base_url=base_url or settings.platform_yijia_base_url,
            **kwargs,
        )


class YijiaImageProvider(YijiaBase, ImageProvider):
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

        body = {
            "model": used_model,
            "prompt": prompt,
            "size": size,
            "n": 1,
        }
        if reference_images:
            body["reference_images"] = reference_images

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
            raise ProviderError(self.name, f"No image URL: {data}")

        return GenerationResult(
            success=True,
            output_url=url,
            metadata={"model": used_model, "size": size, "raw": data},
            cost_credits=10,
        )


class YijiaVideoProvider(YijiaBase, VideoProvider):
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
        # For v2, yijia reuses toapis async polling. Future: implement separately.
        from app.providers.toapis import ToapisVideoProvider

        # Reuse toapis logic with yijia base url
        toapis = ToapisVideoProvider(
            api_key=self.api_key,
            base_url=self.base_url,
        )
        # Set credentials resolution to use yijia
        result = await toapis.generate_video(
            prompt=prompt,
            first_frame=first_frame,
            duration=duration,
            aspect_ratio=aspect_ratio,
            model=model,
            config=config,
        )
        # Override provider label
        result.metadata["provider"] = self.name
        return result