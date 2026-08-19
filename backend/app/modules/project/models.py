"""Project + Episode data models."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Project(Base):
    """A production project (漫剧 or 带货 series)."""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(32), default="manju", nullable=False)  # manju | daihuo
    style: Mapped[str] = mapped_column(String(64), default="", nullable=False)     # 国风 / 穿越 / 现代 / 仙侠 ...
    topic: Mapped[str] = mapped_column(Text, default="", nullable=False)
    product_url: Mapped[str] = mapped_column(String(500), default="", nullable=False)  # 带货商品链接
    product_detail: Mapped[str] = mapped_column(Text, default="", nullable=False)
    episode_count: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    seconds_per_episode: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    aspect_ratio: Mapped[str] = mapped_column(String(16), default="16:9", nullable=False)

    # Generated state
    script_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    characters_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    storyboard_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    video_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)

    # Output
    final_video_path: Mapped[str] = mapped_column(String(500), default="", nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    owner = relationship("User", back_populates="projects")
    episodes = relationship("Episode", back_populates="project", cascade="all, delete-orphan",
                            order_by="Episode.index")
    characters = relationship("Character", back_populates="project", cascade="all, delete-orphan")
    assets = relationship("Asset", back_populates="project", cascade="all, delete-orphan")


class Episode(Base):
    """Single episode in a project."""

    __tablename__ = "episodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)

    index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    outline: Mapped[str] = mapped_column(Text, default="", nullable=False)

    # Generation state
    storyboard_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    video_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    final_video_path: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    script_outline: Mapped[str] = mapped_column(Text, default="", nullable=False)  # full narration per shot, JSON string

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    project = relationship("Project", back_populates="episodes")
    storyboards = relationship("Storyboard", back_populates="episode", cascade="all, delete-orphan",
                                order_by="Storyboard.index")