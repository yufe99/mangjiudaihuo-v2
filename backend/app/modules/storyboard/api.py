"""Storyboard API."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.modules.auth.models import User
from app.modules.project.api import current_user
from app.modules.project.models import Episode, Project
from app.modules.storyboard.models import Storyboard

router = APIRouter()


class StoryboardResponse(BaseModel):
    id: int
    episode_id: int
    index: int
    title: str
    prompt: str
    keyframe_image_url: str
    video_path: str
    audio_path: str
    duration_seconds: float
    status: str
    error_message: str

    model_config = ConfigDict(from_attributes=True)


@router.get(
    "/projects/{project_id}/episodes/{episode_id}/storyboards",
    response_model=list[StoryboardResponse],
)
async def list_storyboards(
    project_id: int,
    episode_id: int,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_session),
) -> list[StoryboardResponse]:
    project = await db.get(Project, project_id)
    if not project or project.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Project not found")
    episode = await db.get(Episode, episode_id)
    if not episode or episode.project_id != project.id:
        raise HTTPException(status_code=404, detail="Episode not found")
    result = await db.execute(
        select(Storyboard).where(Storyboard.episode_id == episode.id).order_by(Storyboard.index)
    )
    return [StoryboardResponse.model_validate(s) for s in result.scalars().all()]