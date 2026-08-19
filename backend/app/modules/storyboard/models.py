"""Storyboard model."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Storyboard(Base):
    """A single shot in an episode.

    storyboard_json holds the structured plan: prompts, image_url, video path, timing, etc.
    """

    __tablename__ = "storyboards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    episode_id: Mapped[int] = mapped_column(
        ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False, index=True
    )

    index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    prompt: Mapped[str] = mapped_column(Text, default="", nullable=False)

    # Generation outputs
    keyframe_image_url: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    keyframe_image_path: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    video_path: Mapped[str] = mapped_column(String(500), default="", nullable=False)

    # Audio (TTS)
    audio_path: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    voice: Mapped[str] = mapped_column(String(64), default="zh-CN-YunyangNeural", nullable=False)

    # Metadata
    duration_seconds: Mapped[float] = mapped_column(Integer, default=5, nullable=False)
    narration: Mapped[str] = mapped_column(Text, default="", nullable=False)
    characters_json: Mapped[str] = mapped_column(String(500), default="", nullable=False)  # JSON list
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    episode = relationship("Episode", back_populates="storyboards")