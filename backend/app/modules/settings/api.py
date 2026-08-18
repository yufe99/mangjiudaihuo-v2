"""User settings API: get / update provider configs (BYOK)."""
from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends

from app.modules.auth.models import User
from app.modules.project.api import current_user
from app.modules.settings.models import UserSettings
from app.core.db import get_session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

router = APIRouter(prefix="/settings",)


class ProviderConfig(BaseModel):
    api_key: str = Field(default="", max_length=500)
    base_url: str = Field(default="", max_length=500)
    model: str = Field(default="", max_length=128)


class SettingsResponse(BaseModel):
    billing_mode: str
    provider_configs: dict[str, dict]
    default_llm_model: str
    default_image_model: str
    default_video_model: str
    notify_email: bool


class SettingsUpdate(BaseModel):
    billing_mode: str | None = Field(default=None, pattern="^(byok|credit)$")
    provider_configs: dict[str, ProviderConfig] | None = None
    default_llm_model: str | None = None
    default_image_model: str | None = None
    default_video_model: str | None = None
    notify_email: bool | None = None


async def _get_or_create_settings(db: AsyncSession, user: User) -> UserSettings:
    s = (await db.execute(select(UserSettings).where(UserSettings.user_id == user.id))).scalar_one_or_none()
    if s:
        return s
    s = UserSettings(user_id=user.id)
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return s


@router.get("", response_model=SettingsResponse)
async def get_settings(
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_session),
) -> SettingsResponse:
    s = await _get_or_create_settings(db, user)
    # Mask api_keys on read (show only last 4 chars)
    masked = {}
    for name, cfg in s.provider_configs.items():
        cfg_d = dict(cfg) if cfg else {}
        if cfg_d.get("api_key"):
            k = cfg_d["api_key"]
            cfg_d["api_key"] = ("*" * (len(k) - 4)) + k[-4:] if len(k) > 4 else "****"
        masked[name] = cfg_d

    return SettingsResponse(
        billing_mode=s.billing_mode,
        provider_configs=masked,
        default_llm_model=s.default_llm_model,
        default_image_model=s.default_image_model,
        default_video_model=s.default_video_model,
        notify_email=s.notify_email,
    )


@router.patch("", response_model=SettingsResponse)
async def update_settings(
    req: SettingsUpdate,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_session),
) -> SettingsResponse:
    s = await _get_or_create_settings(db, user)
    update_data = req.model_dump(exclude_unset=True)

    if "billing_mode" in update_data:
        s.billing_mode = update_data["billing_mode"]
    if "provider_configs" in update_data:
        new_configs = dict(s.provider_configs)
        for name, cfg in update_data["provider_configs"].items():
            new_configs[name] = cfg if isinstance(cfg, dict) else cfg
        s.provider_configs = new_configs
    for k in ("default_llm_model", "default_image_model", "default_video_model", "notify_email"):
        if k in update_data:
            setattr(s, k, update_data[k])

    await db.commit()
    await db.refresh(s)
    return await get_settings(user=user, db=db)