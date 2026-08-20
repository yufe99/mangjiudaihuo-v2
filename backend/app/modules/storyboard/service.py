"""Storyboard generation — step ③ in the wizard.

For each episode, ask LLM to break it into 3-5 shots.
Each shot has:
- index
- title
- characters: which characters appear
- prompt: visual description for image/video generation
- narration: line(s) for TTS
- duration: seconds (default 5)
"""
from __future__ import annotations

import json
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.log import get_logger
from app.modules.character.models import Character
from app.modules.project.models import Episode, Project
from app.modules.settings.models import UserSettings
from app.providers.base import LLMProvider, ProviderRegistry, UserProviderConfig

logger = get_logger(__name__)


STORYBOARD_SYSTEM_PROMPT = """你是短视频分镜师,擅长为多集漫剧/带货短剧拆解镜头。

任务:根据用户给定的分集大纲 + 剧本角色,拆出 3-5 个镜头。

每个镜头要求:
- index: 镜头序号(1,2,3...)
- title: 镜头标题(8字以内)
- characters: 出镜角色名(列表,使用剧本里的角色名)
- prompt: 视觉描述,英文或中文皆可,用于生成图片/视频,需包含场景、人物动作、镜头语言
- narration: 该镜头的口播台词(中文,15-50字)
- duration: 秒数(3-8)

约束:
- 每个镜头只引入 1-2 个角色,避免人物过多
- prompt 要有电影感(景别 + 光线 + 动作 + 构图)
- narration 自然口语,适合 TTS 朗读
- 镜头之间有逻辑衔接,但不重复

严格输出 JSON,不要任何额外文字,不要 markdown 代码块。
JSON 结构:
{
  "shots": [
    {"index": 1, "title": "...", "characters": ["主角"], "prompt": "...", "narration": "...", "duration": 5},
    ...
  ]
}"""


STORYBOARD_USER_PROMPT = """项目类型: {project_type} ({project_type_label})
风格: {style}
集标题: {episode_title}
集概要: {episode_outline}
可用角色: {character_names}

请为这一集生成 3-5 个镜头。"""


def build_prompt(
    *,
    project_type: str,
    style: str,
    episode_title: str,
    episode_outline: str,
    character_names: list[str],
) -> tuple[str, str]:
    type_label = "带货短剧" if project_type == "daihuo" else "漫剧"
    user = STORYBOARD_USER_PROMPT.format(
        project_type=project_type,
        project_type_label=type_label,
        style=style or "现代都市",
        episode_title=episode_title or "本集",
        episode_outline=episode_outline or "",
        character_names="、".join(character_names) if character_names else "(无指定角色)",
    )
    return STORYBOARD_SYSTEM_PROMPT, user


def parse_response(text: str) -> dict:
    """Parse LLM response into shots list. Tolerant of markdown fences."""
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```\s*$", "", text)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            raise ValueError(f"Could not extract JSON: {text[:200]}")
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}; first 200 chars: {text[:200]}")

    if "shots" not in data or not isinstance(data["shots"], list):
        raise ValueError("Missing 'shots' array in response")

    # Normalize
    for i, shot in enumerate(data["shots"]):
        shot.setdefault("index", i + 1)
        shot.setdefault("title", "")
        shot.setdefault("characters", [])
        shot.setdefault("prompt", "")
        shot.setdefault("narration", "")
        shot.setdefault("duration", 5)

    return data


class StoryboardService:
    """Generate storyboards for one or all episodes."""

    @staticmethod
    async def generate_for_episode(
        db: AsyncSession,
        episode: Episode,
        project: Project,
    ) -> dict:
        """Generate storyboard for a single episode."""
        if not project.script_json:
            return {"error": "请先生成剧本(①)"}

        character_names = [c.get("name", "") for c in project.script_json.get("characters", [])]
        if not character_names:
            return {"error": "剧本无角色信息"}

        # Resolve LLM provider
        user_settings = (
            await db.execute(
                select(UserSettings).where(UserSettings.user_id == project.owner_id)
            )
        ).scalar_one_or_none()
        # Treat missing settings as empty; user can configure later
        cfg = user_settings.get_provider_config("geeknow") if user_settings else {}
        user_config = UserProviderConfig(
            provider_name="geeknow",
            api_key=cfg.get("api_key") or None,
            base_url=cfg.get("base_url") or None,
            model=cfg.get("model") or None,
        )

        # Try user-configured provider first; fallback to local_preview on any failure
        last_error = None
        llm = None
        system, user_prompt = build_prompt(
            project_type=project.type,
            style=project.style,
            episode_title=episode.title,
            episode_outline=episode.outline,
            character_names=character_names,
        )
        try:
            llm = ProviderRegistry.get_llm("geeknow")
            result = await llm.generate_text(
                prompt=user_prompt,
                system=system,
                config=user_config,
                max_tokens=4096,
                temperature=0.8,
                response_format={"type": "json_object"},
            )
            if not result.success or not result.text:
                raise ValueError(result.error or "empty response")
        except Exception as e:
            last_error = e
            logger.warning(
                "storyboard_llm_failed_fallback",
                extra={"error": str(e), "fallback": "local_preview"},
            )
            llm = ProviderRegistry.get_llm("local_preview")
            from app.providers.local_preview import LOCAL_STORYBOARD_TEMPLATE

            result = await llm.generate_text(
                prompt=user_prompt,
                system=system,
                config=None,
                max_tokens=4096,
                temperature=0.8,
                response_format={"type": "json_object"},
            )

        if not result.success or not result.text:
            return {"error": result.error or "LLM 返回为空", "last_error": str(last_error) if last_error else None}

        try:
            data = parse_response(result.text)
        except ValueError as e:
            logger.error("storyboard_parse_failed", extra={"error": str(e)})
            return {"error": str(e)}

        # Save
        episode.storyboard_json = data
        episode.storyboard_status = "pending"  # shots haven't generated yet
        await db.flush()

        # Replace storyboard rows
        from app.modules.storyboard.models import Storyboard

        # Delete existing storyboards for this episode
        existing = await db.execute(
            select(Storyboard).where(Storyboard.episode_id == episode.id)
        )
        for sb in existing.scalars().all():
            await db.delete(sb)
        await db.flush()

        for shot in data["shots"]:
            db.add(
                Storyboard(
                    episode_id=episode.id,
                    index=shot["index"],
                    title=shot.get("title", ""),
                    prompt=shot.get("prompt", ""),
                    duration_seconds=float(shot.get("duration", 5)),
                    narration=shot.get("narration", ""),
                    characters_json=json.dumps(shot.get("characters", []), ensure_ascii=False),
                    status="pending",
                )
            )

        await db.commit()

        return {"shots": data["shots"], "episode_id": episode.id}