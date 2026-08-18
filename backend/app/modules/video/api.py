"""Video API skeleton — v2.0: stub; v2.1 will implement real generation."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.modules.auth.models import User
from app.modules.project.api import current_user

router = APIRouter()


class VideoGenerateRequest(BaseModel):
    storyboard_id: int
    model: str | None = None  # override default


class VideoGenerateResponse(BaseModel):
    storyboard_id: int
    status: str
    video_path: str = ""
    error: str = ""


@router.post("/storyboards/{storyboard_id}/generate", response_model=VideoGenerateResponse)
async def generate_video(
    storyboard_id: int,
    user: User = Depends(current_user),
) -> VideoGenerateResponse:
    """③ 生成视频: stub.

    v2.1 will:
    - Resolve user's provider config (BYOK or platform)
    - Call ProviderRegistry.get_video(provider_name).generate_video(...)
    - Poll for completion (sync for fast models, async queue for slow)
    - Download result to local / S3 / R2
    - Update Storyboard.video_path
    """
    return VideoGenerateResponse(
        storyboard_id=storyboard_id,
        status="stub",
        video_path="",
        error="Video generation not yet implemented in v2.0 —. use local_preview or wait for v2.1",
    )