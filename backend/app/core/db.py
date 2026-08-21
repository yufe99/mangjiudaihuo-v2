"""Database engine + session factory."""
from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    """SQLAlchemy 2.0 declarative base."""


def _ensure_sqlite_dir(url: str) -> None:
    """Create SQLite file parent directory if missing."""
    if url.startswith("sqlite"):
        # sqlite+aiosqlite:///./data/app.db → ./data/
        path = url.split("///", 1)[1]
        if path and path != ":memory:":
            parent = Path(path).parent
            parent.mkdir(parents=True, exist_ok=True)


# Ensure SQLite parent dir exists before engine creation
_ensure_sqlite_dir(settings.database_url)


def _make_sqlite_url(url: str) -> str:
    """Append WAL mode + busy_timeout to SQLite URLs to avoid 'database is locked'."""
    if not url.startswith("sqlite"):
        return url
    # Strip any prior params and re-append with our settings
    base = url.split("?")[0]
    return f"{base}?journal_mode=WAL&synchronous=NORMAL&busy_timeout=30000"


engine = create_async_engine(
    _make_sqlite_url(settings.database_url),
    echo=settings.app_debug,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields a session, commits/rolls back on exit.

    Note: We DON'T commit here if router already committed (would cause
    'readonly database' under aiosqlite due to stale lock).
    Routers should call await session.commit() explicitly when needed.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            # Only commit if there's pending work (not yet committed)
            if session.in_transaction():
                await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Create all tables. Used in dev / first run. In production use Alembic."""
    # Import models so they register on Base.metadata
    from app.modules.auth import models as auth_models  # noqa: F401
    from app.modules.project import models as project_models  # noqa: F401
    from app.modules.character import models as char_models  # noqa: F401
    from app.modules.storyboard import models as sb_models  # noqa: F401
    from app.modules.settings import models as settings_models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)