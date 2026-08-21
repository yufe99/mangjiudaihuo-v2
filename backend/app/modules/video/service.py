"""Video generation service — step ③ (per shot).

For each storyboard:
1. Generate a keyframe image (Image Provider, with character anchor as reference)
2. Use the keyframe as first-frame for Video Provider
3. Save keyframe image URL + video path to Storyboard row
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.log import get_logger
from app.modules.character.models import Character
from app.modules.project.models import Episode, Project
from app.modules.settings.models import UserSettings
from app.modules.storyboard.models import Storyboard
from app.providers.base import (
    ImageProvider,
    ProviderRegistry,
    UserProviderConfig,
    VideoProvider,
)

logger = get_logger(__name__)


def _resolve_configs(settings_row: UserSettings | None) -> dict:
    cfg = settings_row.get_provider_config("geeknow") if settings_row else {}
    common = dict(api_key=cfg.get("api_key") or None, base_url=cfg.get("base_url") or None)
    return {
        "user_config": UserProviderConfig(
            provider_name="geeknow",
            api_key=common["api_key"],
            base_url=common["base_url"],
            model=cfg.get("model") or None,
        ),
        "video_model": (cfg.get("model") or None) or settings.default_video_model,
    }


def _build_shot_prompt(
    *,
    shot_prompt: str,
    episode_outline: str,
    characters,  # list[str] OR list[dict]
    char_anchors: dict[str, str],
    style: str,
    aspect: str = "16:9",
) -> str:
    """Build a rich prompt combining shot description + character visuals.

    The video provider will use this with the keyframe as first-frame.
    """
    parts = [shot_prompt.strip()]
    if episode_outline:
        parts.append(f"情节背景:{episode_outline}")
    if characters:
        # Accept both list[str] and list[dict]
        names = []
        for c in characters:
            if isinstance(c, str):
                names.append(c)
            elif isinstance(c, dict) and c.get("name"):
                names.append(c["name"])
        if names:
            parts.append(f"出场角色:{','.join(names)}")
    if style:
        parts.append(f"视觉风格:{style}")
    if aspect == "9:16":
        parts.append("竖屏构图,人物居中,9:16 比例")
    else:
        parts.append("横屏电影感构图,16:9 比例,光影有层次")
    return "。".join([p for p in parts if p])


class VideoService:
    """Generate keyframe + video per storyboard."""

    @staticmethod
    async def generate_for_storyboard(
        db: AsyncSession,
        sb: Storyboard,
        episode: Episode,
        project: Project,
        aspect_ratio: str = "16:9",
    ) -> dict:
        """Generate one keyframe image + one video for one shot."""
        if not sb.prompt:
            return {"status": "failed", "error": "storyboard 没有 prompt"}

        # Resolve providers
        user_settings = (
            await db.execute(
                select(UserSettings).where(UserSettings.user_id == project.owner_id)
            )
        ).scalar_one_or_none()
        # Treat missing settings as empty; user can configure later
        configs = _resolve_configs(user_settings)
        user_config = configs["user_config"]

        try:
            image_provider: ImageProvider = ProviderRegistry.get_image("geeknow_image")
        except Exception:
            image_provider = ProviderRegistry.get_image("local_preview")

        try:
            video_provider: VideoProvider = ProviderRegistry.get_video("fdai")
        except Exception:
            video_provider = ProviderRegistry.get_video("local_preview")
        # 临时:本地 preview 兜底优先,因为 fdai video 当前 key group 不支持,直接走兜底
        video_provider = ProviderRegistry.get_video("local_preview")

        # Pull character anchors (for reference_images)
        shot = next(
            (s for s in (episode.storyboard_json or {}).get("shots", []) if s.get("index") == sb.index),
            None,
        )
        if shot is None:
            shot = {"characters": [], "prompt": sb.prompt}

        character_anchors: dict[str, str] = {}
        char_rows = (
            await db.execute(select(Character).where(Character.project_id == project.id))
        ).scalars().all()
        for char_row in char_rows:
            if char_row.anchor_image_url:
                character_anchors[char_row.name] = char_row.anchor_image_url

        # Normalize characters: accept both string list (local_preview) and dict list (real LLM)
        char_names: list[str] = []
        for c in (shot.get("characters") or []):
            if isinstance(c, str):
                char_names.append(c)
            elif isinstance(c, dict):
                if c.get("name"):
                    char_names.append(c["name"])

        # ===== Step 1: keyframe image =====
        keyframe_prompt = _build_shot_prompt(
            shot_prompt=sb.prompt,
            episode_outline=episode.outline,
            characters=char_names,
            char_anchors=character_anchors,
            style=project.style,
            aspect=aspect_ratio,
        )
        size = "1280x720" if aspect_ratio == "16:9" else "720x1280"

        sb.status = "image_generating"
        await db.commit()

        reference_images = [character_anchors[c] for c in char_names if c in character_anchors]

        try:
            image_result = await image_provider.generate_image(
                prompt=keyframe_prompt,
                model=user_config.model,
                config=user_config,
                size=size,
                reference_images=reference_images if reference_images else None,
            )
            if not image_result.success:
                raise ValueError(image_result.error or "image gen failed")
        except Exception as e:
            logger.warning(
                "keyframe_image_fallback",
                extra={"storyboard_id": sb.id, "error": str(e), "fallback": "local_preview"},
            )
            fallback = ProviderRegistry.get_image("local_preview")
            image_result = await fallback.generate_image(
                prompt=keyframe_prompt,
                size=size,
            )

        sb.keyframe_image_url = image_result.output_url or ""
        sb.status = "video_generating"
        await db.commit()

        # ===== Step 2: video =====
        video_prompt = keyframe_prompt  # reuse same prompt for video gen
        duration = float(getattr(sb, "duration_seconds", 5) or 5)

        try:
            video_result = await video_provider.generate_video(
                prompt=video_prompt,
                first_frame=sb.keyframe_image_url,
                duration=duration,
                aspect_ratio=aspect_ratio,
                model=configs["video_model"],
                config=user_config,
            )
            if not video_result.success:
                raise ValueError(video_result.error or "video gen failed")
        except Exception as e:
            logger.warning(
                "video_fallback",
                extra={"storyboard_id": sb.id, "error": str(e), "fallback": "local_preview"},
            )
            fallback = ProviderRegistry.get_video("local_preview")
            video_result = await fallback.generate_video(
                prompt=video_prompt,
                duration=duration,
                aspect_ratio=aspect_ratio,
            )

        # Store video path (local or URL)
        video_path = ""
        if video_result.output_path:
            video_path = str(video_result.output_path)
        elif video_result.output_url:
            video_path = video_result.output_url
        sb.video_path = video_path
        sb.status = "done"
        await db.commit()

        return {
            "status": "done",
            "storyboard_id": sb.id,
            "keyframe_image_url": sb.keyframe_image_url,
            "video_path": sb.video_path,
        }

    @staticmethod
    async def generate_for_episode(
        db: AsyncSession,
        episode: Episode,
        project: Project,
        aspect_ratio: str = "16:9",
    ) -> dict:
        """Generate video for all storyboards in an episode."""
        storyboards = (
            await db.execute(
                select(Storyboard)
                .where(Storyboard.episode_id == episode.id)
                .order_by(Storyboard.index)
            )
        ).scalars().all()

        if not storyboards:
            return {"error": "Episode has no storyboards; generate ③ storyboard first"}

        results = []
        # Sequential to avoid rate-limit; could be parallel with semaphore
        for sb in storyboards:
            r = await VideoService.generate_for_storyboard(db, sb, episode, project, aspect_ratio)
            r["index"] = sb.index
            results.append(r)

        # Update episode status
        if all(r.get("status") == "done" for r in results):
            episode.video_status = "done"
        elif any(r.get("status") == "done" for r in results):
            episode.video_status = "partial"
        else:
            episode.video_status = "failed"
        project.video_status = "in_progress"
        await db.commit()

        return {"episode_id": episode.id, "results": results}