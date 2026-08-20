"""Script generation module — the ① step in the wizard."""
from __future__ import annotations

import json
import re

from app.providers.base import UserProviderConfig

__all__ = ["ScriptService", "SCRIPT_SYSTEM_PROMPT"]


# ===== Prompt templates =====

SCRIPT_SYSTEM_PROMPT = """你是中国顶级的短视频编剧,精通抖音/快手/视频号的爆款短剧。

你的任务:根据用户给的主题/商品,生成一部多集漫剧/带货短剧的剧本框架。

要求:
1. 系列级别(全剧统一,不分集独立生成):
   - logline (一句话剧情)
   - 角色列表 (至少2个:主角 + 配角),每个角色包含 name / description / appearance
   - 资产清单 (至少2个:场景 + 道具)
   - 分集大纲 (按用户指定的集数,每集:index / title / outline)
2. 风格按用户指定的:国风 / 穿越 / 现代都市 / 仙侠 / 古风宫斗 / 职场精英 / 美妆时尚 / 短剧带货 / 悬疑复仇 / 甜宠
3. 如果用户给了商品,要在主角剧情里**自然**植入商品卖点(不硬广)
4. 输出**严格 JSON**,不要任何额外文字,不要 markdown 代码块

JSON 结构:
{
  "logline": "...",
  "style": "...",
  "characters": [{"name":"","description":"","appearance":""}, ...],
  "assets": [{"type":"scene|prop|product","name":"","description":""}, ...],
  "episodes": [{"index":1,"title":"","outline":""}, ...]
}"""


SCRIPT_USER_PROMPT = """主题: {topic}
风格: {style}
类型: {project_type} (manju=漫剧 / daihuo=带货)
集数: {episode_count}
每集时长: {seconds_per_episode} 秒
商品: {product_info}

请生成上述 JSON。"""


class ScriptService:
    """Service for generating project scripts via LLM."""

    @staticmethod
    def build_prompt(
        *,
        topic: str,
        style: str,
        project_type: str,
        episode_count: int,
        seconds_per_episode: int,
        product_info: str = "",
    ) -> tuple[str, str]:
        """Return (system, user) prompt pair."""
        user = SCRIPT_USER_PROMPT.format(
            topic=topic or "(未指定)",
            style=style or "现代都市",
            project_type=project_type,
            episode_count=episode_count,
            seconds_per_episode=seconds_per_episode,
            product_info=product_info or "(无商品)",
        )
        return SCRIPT_SYSTEM_PROMPT, user

    @staticmethod
    def parse_response(text: str) -> dict:
        """Parse LLM response into validated script dict.

        Tolerates: markdown code fences, leading/trailing prose.
        Raises ValueError on unparseable input.
        """
        # Strip markdown code fences
        text = re.sub(r"^```(?:json)?\s*", "", text.strip())
        text = re.sub(r"\s*```\s*$", "", text)

        # Try direct parse
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Find first { ... } block
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if not m:
                raise ValueError(f"Could not extract JSON from LLM response (first 200 chars): {text[:200]}")
            try:
                data = json.loads(m.group(0))
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in LLM response: {e}; first 200 chars: {text[:200]}")

        # Validate minimum required fields
        required = ["logline", "characters", "episodes"]
        missing = [k for k in required if k not in data]
        if missing:
            raise ValueError(f"Missing required fields in script: {missing}")

        # Ensure episodes are correctly indexed
        episodes = data.get("episodes", [])
        for i, ep in enumerate(episodes):
            if "index" not in ep:
                ep["index"] = i + 1

        # Defaults
        data.setdefault("style", "")
        data.setdefault("assets", [])

        return data

    @staticmethod
    def build_user_config(
        settings_row,
        provider_name: str,
        billing_mode: str,
    ) -> UserProviderConfig:
        """Resolve the actual UserProviderConfig to use for this call.

        """
        provider_name = provider_name or settings_row.default_llm_model  # or settings? default_llm_provider

        if billing_mode == "credit":
            # Platform proxy mode: use platform key (handled by provider's default)
            return UserProviderConfig(
                provider_name=provider_name,
                api_key=None,
                base_url=None,
                model=None,  # use provider default model
            )

        # BYOK mode: use user's stored keys
        cfg = settings_row.get_provider_config(provider_name) if settings_row else {}
        return UserProviderConfig(
            provider_name=provider_name,
            api_key=cfg.get("api_key") or None,
            base_url=cfg.get("base_url") or None,
            model=cfg.get("model") or None,
        )

    @staticmethod
    async def generate_for_project(
        db: AsyncSession,
        project,
        user_id: int,
        provider_name: str = "toapis",
    ) -> dict:
        """Generate script for a project. Reusable from run-all pipeline.

        Returns dict with keys: success, data, error, used_provider
        """
        from sqlalchemy import select
        from app.modules.project.models import Episode
        from app.modules.settings.models import UserSettings
        from app.providers.base import ProviderRegistry, UserProviderConfig
        from app.core.log import get_logger

        logger = get_logger(__name__)

        user_settings = (
            await db.execute(select(UserSettings).where(UserSettings.user_id == user_id))
        ).scalar_one_or_none()

        # If user has key for provider_name, use it; else try provider; else fallback to local_preview
        has_user_key = False
        if user_settings:
            cfg = user_settings.get_provider_config(provider_name) or {}
            if cfg.get("api_key"):
                has_user_key = True

        provider_name = provider_name  # keep explicit
        user_config = ScriptService.build_user_config(
            settings_row=user_settings,
            provider_name=provider_name,
            billing_mode=user_settings.billing_mode if user_settings else "byok",
        )

        system, user_prompt = ScriptService.build_prompt(
            topic=project.topic,
            style=project.style,
            project_type=project.type,
            episode_count=project.episode_count,
            seconds_per_episode=project.seconds_per_episode,
            product_info=project.product_detail or project.product_url,
        )

        # Try user-configured provider; fallback to local_preview on any failure
        used_provider = "unknown"
        try:
            llm = ProviderRegistry.get_llm(provider_name)
            result = await llm.generate_text(
                prompt=user_prompt,
                system=system,
                config=user_config,
                max_tokens=8192,
                temperature=0.8,
                response_format={"type": "json_object"},
            )
            if not result.success or not result.text:
                raise ValueError(result.error or "Empty response")
            used_provider = provider_name
        except Exception as e:
            logger.warning(
                "script_llm_fallback",
                extra={"provider": provider_name, "error": str(e)},
            )
            llm = ProviderRegistry.get_llm("local_preview")
            result = await llm.generate_text(
                prompt=user_prompt,
                system=system,
                config=None,
                max_tokens=8192,
                temperature=0.8,
                response_format={"type": "json_object"},
            )
            used_provider = "local_preview"

        if not result.success or not result.text:
            return {"success": False, "error": result.error or "Empty response", "used_provider": used_provider}

        try:
            data = ScriptService.parse_response(result.text)
        except ValueError as e:
            return {"success": False, "error": str(e), "used_provider": used_provider}

        # Persist
        project.script_json = data
        await db.execute(Episode.__table__.delete().where(Episode.project_id == project.id))
        for ep in data["episodes"]:
            db.add(Episode(
                project_id=project.id,
                index=ep["index"],
                title=ep.get("title", ""),
                outline=ep.get("outline", ""),
            ))
        await db.commit()
        await db.refresh(project)

        return {"success": True, "data": data, "used_provider": used_provider}