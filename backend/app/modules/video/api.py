"""Video API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.modules.auth.models import User
from app.modules.project.api import current_user
from app.modules.project.models import Episode, Project
from app.modules.storyboard.models import Storyboard
from app.modules.video.service import VideoService

router = APIRouter()


class VideoShotResult(BaseModel):
    index: int
    status: str
    error: str | None = None
    storyboard_id: int | None = None
    keyframe_image_url: str | None = None
    video_path: str | None = None


class EpisodeVideoResponse(BaseModel):
    episode_id: int
    results: list[VideoShotResult]


class StoryboardVideoResponse(BaseModel):
    status: str
    error: str | None = None
    storyboard_id: int | None = None
    keyframe_image_url: str | None = None
    video_path: str | None = None


@router.post(
    "/projects/{project_id}/episodes/{episode_id}/generate-videos",
    response_model=EpisodeVideoResponse,
)
async def generate_episode_videos(
    project_id: int,
    episode_id: int,
    aspect_ratio: str = "16:9",
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_session),
) -> EpisodeVideoResponse:
    """③ Generate video for all storyboards in an episode (sequential)."""
    project = await db.get(Project, project_id)
    if not project or project.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Project not found")
    episode = await db.get(Episode, episode_id)
    if not episode or episode.project_id != project.id:
        raise HTTPException(status_code=404, detail="Episode not found")

    result = await VideoService.generate_for_episode(db, episode, project, aspect_ratio)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return EpisodeVideoResponse(episode_id=episode.id, results=result["results"])


@router.post(
    "/storyboards/{storyboard_id}/generate-video",
    response_model=StoryboardVideoResponse,
)
async def generate_storyboard_video(
    storyboard_id: int,
    aspect_ratio: str = "16:9",
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_session),
) -> StoryboardVideoResponse:
    """③ Regenerate video for one storyboard only."""
    sb = await db.get(Storyboard, storyboard_id)
    if not sb:
        raise HTTPException(status_code=404, detail="Storyboard not found")
    episode = await db.get(Episode, sb.episode_id)
    project = await db.get(Project, episode.project_id)
    if not project or project.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Project not found")

    result = await VideoService.generate_for_storyboard(db, sb, episode, project, aspect_ratio)
    return StoryboardVideoResponse(**{k: v for k, v in result.items() if k in StoryboardVideoResponse.model_fields})