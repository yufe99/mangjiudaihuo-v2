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