"""TTS API."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_session
from app.core.log import get_logger
from app.modules.auth.models import User
from app.modules.project.api import current_user
from app.modules.project.models import Episode, Project
from app.modules.storyboard.models import Storyboard
from app.providers.base import ProviderRegistry

router = APIRouter(prefix="/tts")
logger = get_logger(__name__)


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    voice: str = "zh-CN-YunyangNeural"
    storyboard_id: int | None = None
    episode_id: int | None = None


class TTSResponse(BaseModel):
    audio_path: str
    duration_seconds: float
    voice: str
    size_bytes: int


@router.post("/synthesize", response_model=TTSResponse)
async def synthesize(
    req: TTSRequest,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_session),
) -> TTSResponse:
    """Synthesize text to audio. Optionally attach to a storyboard/episode.

    Storage: backend/data/storage/tts/{user_id}/{task_id}.mp3
    """
    provider = ProviderRegistry.get_tts("edge")

    # Storage path
    base = Path(settings.storage_local_root) / "tts" / str(user.id)
    base.mkdir(parents=True, exist_ok=True)
    # Use ms timestamp + text hash for filename uniqueness
    import hashlib
    import time

    digest = hashlib.md5(req.text.encode()).hexdigest()[:10]
    fname = f"{int(time.time() * 1000)}_{digest}.mp3"
    out_path = base / fname

    result = await provider.synthesize(
        text=req.text,
        voice=req.voice,
        output_path=out_path,
    )
    if not result.success:
        raise HTTPException(status_code=502, detail=result.error or "TTS failed")

    size_bytes = out_path.stat().st_size if out_path.exists() else 0
    duration = result.metadata.get("approx_seconds", 0.0)

    # Optionally attach to storyboard
    if req.storyboard_id:
        sb = await db.get(Storyboard, req.storyboard_id)
        if sb and sb.episode.project.owner_id == user.id:
            sb.audio_path = str(out_path)
            sb.voice = req.voice
            await db.commit()

    return TTSResponse(
        audio_path=str(out_path),
        duration_seconds=duration,
        voice=req.voice,
        size_bytes=size_bytes,
    )


@router.post("/episodes/{episode_id}/synthesize-all")
async def synthesize_episode(
    episode_id: int,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_session),
):
    """Synthesize TTS for all storyboards in an episode.

    Reads the storyboard prompt as the narration script.
    Returns the count of generated audio files.
    """
    episode = await db.get(Episode, episode_id)
    if not episode or (await db.get(Project, episode.project_id)) is None:
        raise HTTPException(status_code=404, detail="Episode not found")
    project = await db.get(Project, episode.project_id)
    if project.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Episode not found")

    if not episode.storyboard_json or "shots" not in episode.storyboard_json:
        raise HTTPException(status_code=400, detail="Episode has no storyboards yet")

    provider = ProviderRegistry.get_tts("edge")
    base = Path(settings.storage_local_root) / "tts" / str(user.id) / f"ep_{episode_id}"
    base.mkdir(parents=True, exist_ok=True)

    results = []
    for shot in episode.storyboard_json["shots"]:
        narration = shot.get("narration", "").strip()
        if not narration:
            results.append({"index": shot.get("index"), "status": "skipped", "reason": "empty narration"})
            continue

        out_path = base / f"shot_{shot.get('index', 0):03d}.mp3"
        result = await provider.synthesize(
            text=narration,
            voice="zh-CN-YunyangNeural",
            output_path=out_path,
        )
        if result.success:
            # Find the storyboard row to update audio_path
            sb_index = shot.get("index", 0)
            sb = (
                await db.execute(
                    select(Storyboard).where(
                        Storyboard.episode_id == episode_id,
                        Storyboard.index == sb_index,
                    )
                )
            ).scalar_one_or_none()
            if sb:
                sb.audio_path = str(out_path)
            results.append(
                {
                    "index": sb_index,
                    "status": "ok",
                    "path": str(out_path),
                    "duration": result.metadata.get("approx_seconds", 0),
                }
            )
        else:
            results.append(
                {"index": shot.get("index"), "status": "error", "error": result.error}
            )

    await db.commit()
    return {"episode_id": episode_id, "results": results}