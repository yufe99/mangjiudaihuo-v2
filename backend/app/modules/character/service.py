"""Character anchor image generation — step ② in the wizard.

For each character in the project script, generate ONE anchor image.
All future shots reuse this anchor (gpt-image-2 reference_images) so the
character looks consistent across episodes.
"""
from __future__ import annotations

import json
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.log import get_logger
from app.modules.character.models import Asset, Character
from app.modules.project.models import Project
from app.modules.script.service import ScriptService
from app.modules.settings.models import UserSettings
from app.providers.base import ImageProvider, ProviderRegistry, UserProviderConfig

logger = get_logger(__name__)

# Default style suffix appended to every character prompt for visual consistency.
STYLE_SUFFIX = (
    "，半身像，电影感构图，柔和自然光，"
    "高度写实风格，主体居中，背景虚化，"
    "专业人像摄影"
)


def _build_prompt(character: dict, style: str = "") -> str:
    """Build the image generation prompt for a character.

    Combines description + appearance + style hint.
    """
    parts = [
        character.get("description", "").strip(),
        f"外貌:{character.get('appearance', '').strip()}",
    ]
    parts = [p for p in parts if p]
    base = "，".join(parts) if parts else character.get("name", "character")
    if style:
        base = f"{style}风格。{base}"
    return f"{base}{STYLE_SUFFIX}"


def _build_asset_prompt(asset: dict, style: str = "") -> str:
    parts = [asset.get("description", "").strip()]
    parts = [p for p in parts if p]
    base = "，".join(parts) if parts else asset.get("name", "asset")
    if style:
        base = f"{style}风格。{base}"
    return f"{base}，电影感构图，高度写实"


def _resolve_image_config(settings_row: UserSettings | None) -> tuple[str, UserProviderConfig]:
    """Pick the image provider + user config. Hardcode toapis as default."""
    provider_name = "toapis"
    cfg = settings_row.get_provider_config("toapis") if settings_row else {}
    user_config = UserProviderConfig(
        provider_name=provider_name,
        api_key=cfg.get("api_key") or None,
        base_url=cfg.get("base_url") or None,
        model=cfg.get("model") or None,
    )
    return provider_name, user_config


class CharacterService:
    """Generate anchor images for all characters + assets in a project."""

    @staticmethod
    async def generate_anchors(
        db: AsyncSession,
        project: Project,
        resolution: str = "1024x1024",
    ) -> dict:
        """Generate anchor images for all characters and assets.

        Returns: {characters: [...], assets: [...]}
        Each entry: {id, name, status, image_url, error}
        """
        if not project.script_json or not project.script_json.get("characters"):
            return {"error": "请先生成剧本(①)"}

        user_settings = (
            await db.execute(
                select(UserSettings).where(UserSettings.user_id == project.owner_id)
            )
        ).scalar_one_or_none()
        # Treat missing settings as empty; user can configure later
        provider_name, user_config = _resolve_image_config(user_settings)

        try:
            image_provider: ImageProvider = ProviderRegistry.get_image(provider_name)
        except Exception:
            # Fallback to local preview
            image_provider = ProviderRegistry.get_image("local_preview")

        size = f"{resolution}x{resolution}" if resolution in ("512", "768", "1024") else "1024x1024"

        # === Characters ===
        existing_chars = (
            await db.execute(select(Character).where(Character.project_id == project.id))
        ).scalars().all()
        char_by_name = {c.name: c for c in existing_chars}

        results = {"characters": [], "assets": []}

        # Generate characters in parallel (limited concurrency)
        async def gen_character(char_data: dict):
            name = char_data.get("name", "")
            if not name:
                return {"name": "", "status": "error", "error": "missing name"}

            char_row = char_by_name.get(name)
            if char_row is None:
                char_row = Character(
                    project_id=project.id,
                    name=name,
                    description=char_data.get("description", ""),
                    appearance=char_data.get("appearance", ""),
                    status="generating",
                )
                db.add(char_row)
                await db.flush()
            else:
                char_row.status = "generating"
                char_row.error_message = ""

            prompt = _build_prompt(char_data, style=project.style)
            # Try toapis first; fallback to local_preview on missing key
            last_error = None
            try:
                result = await image_provider.generate_image(
                    prompt=prompt,
                    model=user_config.model,
                    config=user_config,
                    size=size,
                )
                if not result.success:
                    raise ValueError(result.error or "image gen failed")
            except Exception as e:
                last_error = e
                logger.warning(
                    "char_image_fallback",
                    extra={"name": name, "error": str(e), "fallback": "local_preview"},
                )
                fallback = ProviderRegistry.get_image("local_preview")
                result = await fallback.generate_image(
                    prompt=prompt,
                    size=size,
                )
            if not result.success:
                char_row.status = "failed"
                char_row.error_message = result.error or "image generation failed"
                return {
                    "name": name,
                    "status": "failed",
                    "error": char_row.error_message,
                }
            char_row.anchor_image_url = result.output_url or ""
            char_row.status = "done"
            return {
                "name": name,
                "status": "done",
                "image_url": result.output_url,
            }

        # Sequential: shared session, no concurrent flush issues
        char_results = []
        for c in project.script_json["characters"]:
            char_results.append(await gen_character(c))
        results["characters"] = char_results

        # === Assets ===
        assets_data = project.script_json.get("assets", [])
        existing_assets = (
            await db.execute(select(Asset).where(Asset.project_id == project.id))
        ).scalars().all()
        asset_by_key = {(a.type, a.name): a for a in existing_assets}

        async def gen_asset(asset_data: dict):
            atype = asset_data.get("type", "")
            name = asset_data.get("name", "")
            key = (atype, name)
            asset_row = asset_by_key.get(key)
            if asset_row is None:
                asset_row = Asset(
                    project_id=project.id,
                    type=atype,
                    name=name,
                    description=asset_data.get("description", ""),
                    status="generating",
                )
                db.add(asset_row)
                await db.flush()
            else:
                asset_row.status = "generating"
                asset_row.error_message = ""

            prompt = _build_asset_prompt(asset_data, style=project.style)
            try:
                result = await image_provider.generate_image(
                    prompt=prompt,
                    model=user_config.model,
                    config=user_config,
                    size=size,
                )
                if not result.success:
                    asset_row.status = "failed"
                    asset_row.error_message = result.error or "image generation failed"
                    return {
                        "type": atype,
                        "name": name,
                        "status": "failed",
                        "error": asset_row.error_message,
                    }
                asset_row.image_url = result.output_url or ""
                asset_row.status = "done"
                return {
                    "type": atype,
                    "name": name,
                    "status": "done",
                    "image_url": result.output_url,
                }
            except Exception as e:
                asset_row.status = "failed"
                asset_row.error_message = str(e)[:200]
                return {
                    "type": atype,
                    "name": name,
                    "status": "failed",
                    "error": str(e)[:200],
                }

        asset_results = []
        for a in assets_data:
            asset_results.append(await gen_asset(a))
        results["assets"] = asset_results

        # Update project status
        project.characters_status = (
            "done" if all(c.get("status") == "done" for c in results["characters"]) else "partial"
        )
        await db.commit()

        return results

    @staticmethod
    async def regenerate_one(
        db: AsyncSession,
        project: Project,
        character_id: int,
    ) -> dict:
        """Regenerate anchor for a single character (reset status first)."""
        char = await db.get(Character, character_id)
        if not char or char.project_id != project.id:
            return {"error": "Character not found"}

        char.status = "pending"
        char.error_message = ""
        await db.commit()

        # Reuse main flow but for one character
        user_settings = (
            await db.execute(
                select(UserSettings).where(UserSettings.user_id == project.owner_id)
            )
        ).scalar_one_or_none()
        # Treat missing settings as empty; user can configure later
        provider_name, user_config = _resolve_image_config(user_settings)

        try:
            image_provider: ImageProvider = ProviderRegistry.get_image(provider_name)
        except Exception:
            image_provider = ProviderRegistry.get_image("local_preview")

        prompt = _build_prompt(
            {"name": char.name, "description": char.description, "appearance": char.appearance},
            style=project.style,
        )
        char.status = "generating"
        try:
            result = await image_provider.generate_image(
                prompt=prompt,
                model=user_config.model,
                config=user_config,
                size="1024x1024",
            )
            if not result.success:
                char.status = "failed"
                char.error_message = result.error or "failed"
                await db.commit()
                return {"status": "failed", "error": char.error_message}
            char.anchor_image_url = result.output_url or ""
            char.status = "done"
            await db.commit()
            return {
                "status": "done",
                "image_url": result.output_url,
            }
        except Exception as e:
            char.status = "failed"
            char.error_message = str(e)[:200]
            await db.commit()
            return {"status": "failed", "error": str(e)[:200]}