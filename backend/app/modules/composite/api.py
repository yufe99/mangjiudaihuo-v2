"""Composite API skeleton."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.modules.auth.models import User
from app.modules.project.api import current_user

router = APIRouter()


class CompositeRequest(BaseModel):
    project_id: int
    add_subtitle: bool = True
    background_music_path: str = ""


class CompositeResponse(BaseModel):
    status: str
    final_video_path: str = ""
    duration_seconds: float = 0.0
    error: str = ""


@router.post("/merge", response_model=CompositeResponse)
async def merge(
    req: CompositeRequest,
    user: User = Depends(current_user),
) -> CompositeResponse:
    """合成最终视频:v2.0 stub."""
    return CompositeResponse(
        status="stub",
        final_video_path="",
        duration_seconds=0.0,
        error="Composite not yet implemented in v2.0",
    )