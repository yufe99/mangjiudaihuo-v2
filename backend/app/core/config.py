"""Application settings, loaded from environment + .env file.

Single source of truth. Imported as `settings` elsewhere.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ===== App =====
    app_env: Literal["development", "production", "test"] = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_debug: bool = True
    app_name: str = "mangjiudaihuo-v2"

    # ===== Security =====
    secret_key: str = Field(
        default="change-me-in-production-use-openssl-rand-hex-32",
        description="JWT signing key. ALWAYS override in production.",
    )
    jwt_algorithm: str = "HS256"
    jwt_access_token_ttl_minutes: int = 60 * 24 * 7
    jwt_refresh_token_ttl_minutes: int = 60 * 24 * 30

    # ===== Database =====
    database_url: str = "sqlite+aiosqlite:///./data/app.db"

    # ===== CORS =====
    # 开发阶段允许所有来源(tunnel/本地/IP 都能访问),上线前收紧
    cors_origins: str = "*"

    # ===== Storage =====
    storage_backend: Literal["local", "s3", "r2"] = "local"
    storage_local_root: Path = Path("./data/storage")
    storage_s3_bucket: str = ""
    storage_s3_region: str = ""
    storage_s3_access_key: str = ""
    storage_s3_secret_key: str = ""

    # ===== Provider defaults =====
    default_llm_provider: str = "toapis"
    default_llm_model: str = "deepseek-v4-flash"
    default_image_provider: str = "toapis"
    default_image_model: str = "gpt-image-2"
    default_video_provider: str = "toapis"
    default_video_model: str = "seedance-2-mini"
    default_tts_provider: str = "edge"

    # ===== Business model =====
    enable_credit_mode: bool = True
    default_free_credits: int = 100

    # ===== Rate limiting =====
    rate_limit_per_minute: int = 60
    rate_limit_burst: int = 120

    # ===== Logging =====
    log_level: str = "INFO"
    log_format: Literal["json", "text"] = "text"

    # ===== Task queue =====
    redis_url: str = "redis://localhost:6379/0"

    # ===== Platform fallback API keys (for credit mode) =====
    platform_toapis_api_key: str = ""
    platform_toapis_base_url: str = "https://toapis.com/v1"
    platform_yijia_api_key: str = ""
    platform_yijia_base_url: str = "https://ai.yijiarj.cn/v1"

    @field_validator("cors_origins")
    @classmethod
    def _split_cors(cls, v: str) -> list[str]:
        return [o.strip() for o in v.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor."""
    return Settings()


# Global singleton
settings = get_settings()