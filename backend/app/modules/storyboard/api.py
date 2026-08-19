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
from app.modules.storyboard.service import StoryboardService

router = APIRouter()


class StoryboardResponse(BaseModel):
    id: int
    episode_id: int
    index: int
    title: str
    prompt: str
    narration: str
    characters: list[str] = []
    keyframe_image_url: str
    video_path: str
    audio_path: str
    duration_seconds: float
    status: str
    error_message: str

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def model_validate(cls, obj):
        # Override to derive characters from characters_json
        from pydantic import ValidationError
        if hasattr(obj, "characters_json") and obj.characters_json:
            try:
                import json
                obj.characters = json.loads(obj.characters_json)
            except Exception:
                obj.characters = []
        return super().model_validate(obj)


class EpisodeShotsResponse(BaseModel):
    """Full episode storyboard (from storyboard_json)."""
    episode_id: int
    title: str
    shots: list[dict]


class GenerateStoryboardResponse(BaseModel):
    episode_id: int
    shots: list[dict]


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


@router.get(
    "/projects/{project_id}/episodes/{episode_id}/shots",
    response_model=EpisodeShotsResponse,
)
async def get_shot_plan(
    project_id: int,
    episode_id: int,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_session),
) -> EpisodeShotsResponse:
    """Return the LLM-generated shot plan (storyboard_json) for an episode."""
    project = await db.get(Project, project_id)
    if not project or project.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Project not found")
    episode = await db.get(Episode, episode_id)
    if not episode or episode.project_id != project.id:
        raise HTTPException(status_code=404, detail="Episode not found")
    if not episode.storyboard_json:
        return EpisodeShotsResponse(episode_id=episode.id, title=episode.title, shots=[])
    return EpisodeShotsResponse(
        episode_id=episode.id,
        title=episode.title,
        shots=episode.storyboard_json.get("shots", []),
    )


@router.post(
    "/projects/{project_id}/episodes/{episode_id}/storyboard/generate",
    response_model=GenerateStoryboardResponse,
)
async def generate_storyboard(
    project_id: int,
    episode_id: int,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_session),
) -> GenerateStoryboardResponse:
    """③ Generate storyboard (LLM decomposes episode into 3-5 shots)."""
    project = await db.get(Project, project_id)
    if not project or project.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Project not found")
    episode = await db.get(Episode, episode_id)
    if not episode or episode.project_id != project.id:
        raise HTTPException(status_code=404, detail="Episode not found")

    result = await StoryboardService.generate_for_episode(db, episode, project)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return GenerateStoryboardResponse(
        episode_id=episode.id,
        shots=result["shots"],
    )