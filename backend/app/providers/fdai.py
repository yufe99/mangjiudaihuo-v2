"""fdai.xyz provider - 异步任务式视频/图像生成。

API 文档: https://1ge19hv5f1.apifox.cn/

异步任务流:
1. POST /v1/videos → task_id + pending
2. 轮询 GET /v1/videos/{task_id} 直到 status="completed"
3. 从 response 拿 video URL

base_url: https://apinocf.fdai.xyz (强制要求)
"""
from __future__ import annotations

import asyncio
import time

import httpx

from app.core.config import settings
from app.providers.base import (
    GenerationResult,
    ImageProvider,
    ProviderError,
    UserProviderConfig,
    VideoProvider,
)


class FdaiVideoProvider(VideoProvider):
    name = "fdai"

    def __init__(self, **kwargs):
        self.api_key = kwargs.get("api_key") or settings.platform_fdai_api_key
        self.base_url = (
            kwargs.get("base_url") or settings.platform_fdai_base_url
        ).rstrip("/")
        if self.base_url.endswith("/v1"):
            self.api_base = self.base_url
        else:
            self.api_base = self.base_url.rstrip("/") + "/v1"

    async def generate_video(
        self,
        *,
        prompt: str,
        first_frame: str | None = None,
        duration: float = 15.0,
        aspect_ratio: str = "16:9",
        model: str | None = None,
        config: UserProviderConfig | None = None,
    ) -> GenerationResult:
        """Submit video task and poll until complete."""
        key = (config.api_key if config and config.api_key else self.api_key or "")
        if not key:
            return GenerationResult(success=False, error="Missing fdai API key")

        used_model = model or (config.model if config and config.model else None) or settings.default_video_model

        # fdai duration 是整数(4-15 秒),最小化用整数
        duration_int = max(4, min(15, int(duration)))

        body = {
            "model": used_model,
            "prompt": prompt,
            "duration": duration_int,
            "aspect_ratio": aspect_ratio,
        }
        if first_frame:
            body["images"] = [first_frame]

        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

        # 1) Submit
        async with httpx.AsyncClient(timeout=60) as client:
            try:
                r = await client.post(
                    f"{self.api_base}/videos",
                    headers=headers,
                    json=body,
                )
            except Exception as e:
                return GenerationResult(success=False, error=f"Submit failed: {e}")

            if r.status_code >= 400:
                err_text = r.text[:300]
                raise ProviderError(self.name, f"HTTP {r.status_code}: {err_text}")

            data = r.json()
            task_id = data.get("task_id") or data.get("id")
            if not task_id:
                return GenerationResult(
                    success=False, error=f"No task_id in response: {data}"
                )

            # 2) Poll until completed (max 5 min)
            max_wait = 300
            start = time.time()
            while time.time() - start < max_wait:
                await asyncio.sleep(8)
                try:
                    r2 = await client.get(
                        f"{self.api_base}/videos/{task_id}",
                        headers=headers,
                    )
                except Exception as e:
                    # 网络中断时继续轮询
                    continue

                if r2.status_code >= 400:
                    if r2.status_code == 404:
                        # task 不存在 — 终止
                        return GenerationResult(
                            success=False, error=f"Task {task_id} not found (404)"
                        )
                    continue

                v = r2.json()
                status = v.get("status", "").lower()
                if status in ("completed", "succeeded", "success", "done"):
                    # 拿视频 URL — 不同字段名兼容
                    url = (
                        v.get("video_url")
                        or v.get("url")
                        or v.get("output_url")
                        or (v.get("output", {}) or {}).get("url")
                        or (v.get("data", [{}])[0] if v.get("data") else {}).get("url")
                    )
                    if not url:
                        return GenerationResult(
                            success=False,
                            error=f"Completed but no URL in: {json.dumps(v)[:200]}",
                            metadata={"task_id": task_id, "raw": v},
                        )
                    return GenerationResult(
                        success=True,
                        output_url=url,
                        metadata={
                            "task_id": task_id,
                            "model": used_model,
                            "duration": duration_int,
                        },
                        cost_credits=20,
                    )
                elif status in ("failed", "error", "cancelled"):
                    err = v.get("error") or v.get("message") or "task failed"
                    return GenerationResult(
                        success=False,
                        error=f"Task failed: {err}",
                        metadata={"task_id": task_id, "raw": v},
                    )

            return GenerationResult(
                success=False,
                error=f"Task {task_id} timed out after {max_wait}s",
                metadata={"task_id": task_id},
            )


class FdaiImageProvider(ImageProvider):
    name = "fdai_image"

    def __init__(self, **kwargs):
        self.api_key = kwargs.get("api_key") or settings.platform_fdai_api_key
        self.base_url = (
            kwargs.get("base_url") or settings.platform_fdai_base_url
        ).rstrip("/")
        if self.base_url.endswith("/v1"):
            self.api_base = self.base_url
        else:
            self.api_base = self.base_url.rstrip("/") + "/v1"

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
        if not key:
            return GenerationResult(success=False, error="Missing fdai API key")

        used_model = model or (config.model if config and config.model else None) or settings.default_image_model

        # fdai size 直接用 "9:16" / "1024x1024"
        body = {
            "model": used_model,
            "prompt": prompt,
            "size": size,
        }
        if reference_images:
            body["image"] = reference_images

        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                f"{self.api_base}/images/generations",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            if r.status_code >= 400:
                raise ProviderError(self.name, f"HTTP {r.status_code}: {r.text[:300]}")
            data = r.json()

        items = data.get("data", [])
        if not items:
            return GenerationResult(success=False, error="Empty response")

        first = items[0]
        url = first.get("url") or first.get("b64_json") or ""
        return GenerationResult(
            success=bool(url),
            output_url=url,
            metadata={"model": used_model},
            cost_credits=5,
        )