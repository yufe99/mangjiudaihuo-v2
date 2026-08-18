"""TTS API skeleton."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.modules.auth.models import User
from app.modules.project.api import current_user

router = APIRouter()


class TTSRequest(BaseModel):
    text: str
    voice: str = "zh-CN-YunyangNeural"
    storyboard_id: int | None = None


class TTSResponse(BaseModel):
    status: str
    audio_path: str = ""
    duration_seconds: float = 0.0
    error: str = ""


@router.post("/synthesize", response_model=TTSResponse)
async def synthesize(
    req: TTSRequest,
    user: User = Depends(current_user),
) -> TTSResponse:
    """合成语音:v2.0 stub."""
    return TTSResponse(
        status="stub",
        audio_path="",
        duration_seconds=0.0,
        error="TTS not yet implemented in v2.0",
    )