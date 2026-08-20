"""One-click run-all pipeline for 带货.

用户调 POST /api/v1/projects/{id}/run-all,后端依次跑:
① 剧本 → ② 角色锚点 → ③ 分镜 → ③ 视频 → 配音 → ④ 合成

返回每个 episode 的状态 + 最终 MP4 路径。
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.log import get_logger
from app.modules.character.service import CharacterService
from app.modules.composite.service import CompositeService
from app.modules.project.models import Episode, Project
from app.modules.script.service import ScriptService
from app.modules.settings.models import UserSettings
from app.modules.storyboard.service import StoryboardService
from app.modules.video.service import VideoService

logger = get_logger(__name__)


class RunAllService:
    """One-click full pipeline."""

    @staticmethod
    async def run_full_pipeline(
        db: AsyncSession,
        project: Project,
        aspect_ratio: str = "9:16",
    ) -> dict:
        """Run all 4 steps sequentially, return per-episode + overall status."""
        if not project.topic:
            return {"error": "项目没有主题(topic),无法生成"}

        # ① Script
        script_result = await ScriptService.generate_for_project(
            db, project, user_id=project.owner_id, provider_name="toapis"
        )
        if not script_result.get("success"):
            return {"error": f"①剧本失败:{script_result.get('error')}", "used_provider": script_result.get("used_provider")}

        # ② Characters
        try:
            char_results = await CharacterService.generate_anchors(db, project)
            # Continue even if assets fail; we only need characters for video
            logger.info("run_all_characters", extra={"char_count": len(char_results.get("characters", []))})
        except Exception as e:
            logger.warning("run_all_characters_failed", extra={"error": str(e)})
            char_results = {"characters": [], "assets": []}

        # ③ Per episode: storyboard + video
        episodes = (
            await db.execute(
                select(Episode).where(Episode.project_id == project.id).order_by(Episode.index)
            )
        ).scalars().all()

        episode_results = []
        for ep in episodes:
            sb_result = {"status": "pending"}
            video_result = {"status": "pending"}
            try:
                sb_result = await StoryboardService.generate_for_episode(db, ep, project)
                if "error" not in sb_result:
                    video_result = await VideoService.generate_for_episode(
                        db, ep, project, aspect_ratio=aspect_ratio
                    )
            except Exception as e:
                logger.error("run_all_episode_failed", extra={"ep": ep.index, "error": str(e)})
                sb_result = {"error": str(e)}
            episode_results.append(
                {
                    "episode_id": ep.id,
                    "index": ep.index,
                    "title": ep.title,
                    "storyboard": sb_result,
                    "video": video_result,
                }
            )

        # ④ Composite per episode + project
        final_videos = []
        for ep in episodes:
            try:
                comp = await CompositeService.merge_episode(db, ep, project)
                if comp.get("status") == "ok":
                    final_videos.append(
                        {"episode_id": ep.id, "index": ep.index, "path": comp["final_video_path"]}
                    )
            except Exception as e:
                logger.error("run_all_composite_failed", extra={"ep": ep.index, "error": str(e)})

        # Final project video
        project_final = None
        if final_videos:
            try:
                proj_merge = await CompositeService.merge_project(db, project)
                if proj_merge.get("project_final"):
                    project_final = proj_merge["project_final"]
            except Exception as e:
                logger.error("run_all_project_composite_failed", extra={"error": str(e)})

        await db.commit()

        return {
            "project_id": project.id,
            "characters": char_results.get("characters", []),
            "episodes": episode_results,
            "final_videos": final_videos,
            "project_final_video": project_final,
            "next_step": "GET /api/v1/projects/{id}/download/project",
        }