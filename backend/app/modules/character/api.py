"""Character + Asset API."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.modules.auth.models import User
from app.modules.character.models import Asset, Character
from app.modules.project.api import current_user
from app.modules.project.models import Project
from app.providers.base import ProviderRegistry

router = APIRouter()


class CharacterResponse(BaseModel):
    id: int
    name: str
    description: str
    appearance: str
    anchor_image_url: str
    status: str
    error_message: str

    model_config = ConfigDict(from_attributes=True)


class AssetResponse(BaseModel):
    id: int
    type: str
    name: str
    description: str
    image_url: str
    status: str
    error_message: str

    model_config = ConfigDict(from_attributes=True)


@router.get("/projects/{project_id}/characters", response_model=list[CharacterResponse])
async def list_characters(
    project_id: int,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_session),
) -> list[CharacterResponse]:
    project = await db.get(Project, project_id)
    if not project or project.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Project not found")
    result = await db.execute(
        select(Character).where(Character.project_id == project.id).order_by(Character.id)
    )
    return [CharacterResponse.model_validate(c) for c in result.scalars().all()]


@router.post("/projects/{project_id}/characters/{char_id}/regenerate", response_model=CharacterResponse)
async def regenerate_character(
    project_id: int,
    char_id: int,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_session),
) -> CharacterResponse:
    """Regenerate anchor image for one character (v2 skeleton: just marks as pending)."""
    project = await db.get(Project, project_id)
    if not project or project.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Project not found")
    char = await db.get(Character, char_id)
    if not char or char.project_id != project.id:
        raise HTTPException(status_code=404, detail="Character not found")
    char.status = "pending"
    char.error_message = ""
    await db.commit()
    await db.refresh(char)
    return CharacterResponse.model_validate(char)


@router.get("/projects/{project_id}/assets", response_model=list[AssetResponse])
async def list_assets(
    project_id: int,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_session),
) -> list[AssetResponse]:
    project = await db.get(Project, project_id)
    if not project or project.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Project not found")
    result = await db.execute(
        select(Asset).where(Asset.project_id == project.id).order_by(Asset.type, Asset.id)
    )
    return [AssetResponse.model_validate(a) for a in result.scalars().all()]