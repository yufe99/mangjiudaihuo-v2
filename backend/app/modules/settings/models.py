"""User settings module — provider API keys, billing mode, etc."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class UserSettings(Base):
    """Per-user configuration: provider keys, billing mode, preferences."""

    __tablename__ = "user_settings"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )

    # Billing mode: byok (user brings own key) | credit (platform proxy + deduct credits)
    billing_mode: Mapped[str] = mapped_column(String(32), default="byok", nullable=False)

    # Provider configs (JSON: {provider_name: {api_key: str, base_url: str, model: str}})
    # api_key stored plain for v2 simplicity; production should encrypt at rest.
    provider_configs: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    # Default preferences
    default_llm_model: Mapped[str] = mapped_column(String(128), default="deepseek-v4-flash", nullable=False)
    default_image_model: Mapped[str] = mapped_column(String(128), default="gpt-image-2", nullable=False)
    default_video_model: Mapped[str] = mapped_column(String(128), default="seedance-2-mini", nullable=False)

    # Notifications
    notify_email: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationship
    user = relationship("User", back_populates="settings")

    def get_provider_config(self, provider_name: str) -> dict:
        return self.provider_configs.get(provider_name, {})

    def set_provider_config(self, provider_name: str, config: dict) -> None:
        self.provider_configs = {**self.provider_configs, provider_name: config}