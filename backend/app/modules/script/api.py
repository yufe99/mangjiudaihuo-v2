"""Script API router — ① 剧本生成."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.log import get_logger
from app.modules.auth.models import User
from app.modules.project.api import current_user
from app.modules.project.models import Episode, Project
from app.modules.script.service import ScriptService
from app.modules.settings.models import UserSettings
from app.providers.base import ProviderRegistry

router = APIRouter(prefix="/projects/{project_id}/script", tags=["script"])
logger = get_logger(__name__)


class ScriptGenerateResponse(BaseModel):
    logline: str
    style: str
    characters: list[dict]
    assets: list[dict]
    episodes: list[dict]


@router.post("/generate", response_model=ScriptGenerateResponse)
async def generate_script(
    project_id: int,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_session),
) -> ScriptGenerateResponse:
    """① 生成剧本: 调 LLM → 解析 JSON → 写入 Project + Episode 表。"""
    project = await db.get(Project, project_id)
    if not project or project.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Project not found")

    # Determine provider
    user_settings = (
        await db.execute(select(UserSettings).where(UserSettings.user_id == user.id))
    ).scalar_one_or_none()

    provider_name = (
        (user_settings.provider_configs.get("toapis") or {}).get("provider_name") or "toapis"
        if user_settings and user_settings.provider_configs
        else "toapis"
    )
    # Actually: provider name comes from settings / first available
    from app.core.config import settings as app_settings

    provider_name = "geeknow"  # default for v2 (platform key in config)

    billing_mode = user_settings.billing_mode if user_settings else "byok"

    # Resolve user config (BYOK or platform fallback)
    user_config = ScriptService.build_user_config(
        settings_row=user_settings,
        provider_name=provider_name,
        billing_mode=billing_mode,
    )

    # Build prompts
    system, user_prompt = ScriptService.build_prompt(
        topic=project.topic,
        style=project.style,
        project_type=project.type,
        episode_count=project.episode_count,
        seconds_per_episode=project.seconds_per_episode,
        product_info=project.product_detail or project.product_url,
    )

    # Call LLM with fallback to local_preview on missing key / error
    try:
        llm = ProviderRegistry.get_llm(provider_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Provider {provider_name!r} not available: {e}")

    try:
        result = await llm.generate_text(
            prompt=user_prompt,
            system=system,
            config=user_config,
            max_tokens=8192,
            temperature=0.8,
            response_format={"type": "json_object"},
        )
    except Exception as e:
        logger.warning("script_llm_fallback", extra={"provider": provider_name, "error": str(e)})
        llm = ProviderRegistry.get_llm("local_preview")
        result = await llm.generate_text(
            prompt=user_prompt,
            system=system,
            config=None,
            max_tokens=8192,
            temperature=0.8,
            response_format={"type": "json_object"},
        )

    if not result.success or not result.text:
        raise HTTPException(status_code=502, detail=result.error or "Empty LLM response")

    # Parse JSON
    try:
        data = ScriptService.parse_response(result.text)
    except ValueError as e:
        logger.error("script_parse_failed", extra={"project_id": project_id, "error": str(e)})
        raise HTTPException(status_code=502, detail=str(e))

    # Persist
    project.script_json = data
    # Replace episode list
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

    return ScriptGenerateResponse(**data)


@router.get("", response_model=ScriptGenerateResponse)
async def get_script(
    project_id: int,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_session),
) -> ScriptGenerateResponse:
    project = await db.get(Project, project_id)
    if not project or project.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.script_json:
        raise HTTPException(status_code=404, detail="Script not generated yet")
    return ScriptGenerateResponse(**project.script_json)