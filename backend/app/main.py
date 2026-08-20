"""FastAPI application factory + entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.db import init_db
from app.core.log import get_logger, setup_logging
from app.modules.auth.api import router as auth_router
from app.modules.character.api import router as character_router
from app.modules.composite.api import router as composite_router
from app.modules.project.api import router as project_router
from app.modules.script.api import router as script_router
from app.modules.settings.api import router as settings_router
from app.modules.storyboard.api import router as storyboard_router
from app.modules.tts.api import router as tts_router
from app.modules.video.api import router as video_router
from app.providers.registry import register_all_providers

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """App startup + shutdown hooks."""
    setup_logging()
    logger.info("app_starting", extra={"env": settings.app_env, "debug": settings.app_debug})

    # Register all built-in providers
    register_all_providers()
    logger.info("providers_registered")

    # Initialize DB (creates tables if missing; production uses Alembic)
    if settings.app_env in ("development", "test"):
        await init_db()
        logger.info("db_initialized")

    yield

    logger.info("app_shutdown")


def create_app() -> FastAPI:
    """Application factory."""
    app = FastAPI(
        title="mangjiudaihuo-v2",
        description="AI 漫剧 /带货 系列生产平台 — v2",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(project_router, prefix="/api/v1")
    app.include_router(settings_router, prefix="/api/v1")
    app.include_router(script_router, prefix="/api/v1")
    app.include_router(character_router, prefix="/api/v1")
    app.include_router(storyboard_router, prefix="/api/v1")
    app.include_router(video_router, prefix="/api/v1")
    app.include_router(tts_router, prefix="/api/v1")
    app.include_router(composite_router, prefix="/api/v1")
    from app.modules.product.api import router as product_router
    app.include_router(product_router, prefix="/api/v1")

    @app.get("/health")
    async def health() -> dict:
        return {
            "status": "ok",
            "env": settings.app_env,
            "version": "0.1.0",
        }

    @app.get("/")
    async def root() -> dict:
        return {
            "name": "mangjiudaihuo-v2",
            "tagline": "AI 漫剧/带货 系列生产平台",
            "docs": "/docs",
            "version": "0.1.0",
        }

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_debug,
        log_config=None,
    )