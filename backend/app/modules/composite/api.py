"""Composite API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.modules.auth.models import User
from app.modules.composite.service import CompositeService
from app.modules.project.api import current_user
from app.modules.project.models import Episode, Project

router = APIRouter()


class CompositeRequest(BaseModel):
    add_subtitle: bool = True


class CompositeResponse(BaseModel):
    status: str
    episode_id: int | None = None
    final_video_path: str | None = None
    size_bytes: int | None = None
    duration_seconds: float | None = None
    error: str | None = None


class ProjectCompositeResponse(BaseModel):
    episodes: list[dict]
    project_final: str | None = None
    size_bytes: int | None = None
    error: str | None = None


@router.post(
    "/projects/{project_id}/episodes/{episode_id}/merge",
    response_model=CompositeResponse,
)
async def merge_episode(
    project_id: int,
    episode_id: int,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_session),
) -> CompositeResponse:
    project = await db.get(Project, project_id)
    if not project or project.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Project not found")
    episode = await db.get(Episode, episode_id)
    if not episode or episode.project_id != project.id:
        raise HTTPException(status_code=404, detail="Episode not found")

    result = await CompositeService.merge_episode(db, episode, project)
    return CompositeResponse(**{k: v for k, v in result.items() if k in CompositeResponse.model_fields})


@router.post(
    "/projects/{project_id}/merge-all",
    response_model=ProjectCompositeResponse,
)
async def merge_project(
    project_id: int,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_session),
) -> ProjectCompositeResponse:
    project = await db.get(Project, project_id)
    if not project or project.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Project not found")

    result = await CompositeService.merge_project(db, project)
    return ProjectCompositeResponse(**{k: v for k, v in result.items() if k in ProjectCompositeResponse.model_fields})