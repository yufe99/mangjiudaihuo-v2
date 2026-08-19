"""Composite service — step ④ (final).

Concatenates all storyboard videos + audio for an episode into a single MP4.
Uses ffmpeg via subprocess; falls back gracefully if not available.
"""
from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.log import get_logger
from app.modules.project.models import Episode, Project
from app.modules.storyboard.models import Storyboard

logger = get_logger(__name__)


def _find_ffmpeg() -> str | None:
    candidates = [
        Path("./tools/ffmpeg/ffmpeg.exe") if __import__("os").name == "nt" else Path("./tools/ffmpeg/ffmpeg"),
        Path("./tools/ffmpeg/ffmpeg"),
        shutil.which("ffmpeg"),
    ]
    for p_ in candidates:
        if p_ and hasattr(p_, "exists") and p_.exists():
            return str(p_)
    return shutil.which("ffmpeg")


async def _run_ffmpeg(args: list[str], timeout: int = 300) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return 124, "", "timeout"
    return proc.returncode, stdout.decode("utf-8", errors="ignore"), stderr.decode("utf-8", errors="ignore")


class CompositeService:
    @staticmethod
    async def merge_episode(
        db: AsyncSession,
        episode: Episode,
        project: Project,
        add_subtitle: bool = True,
    ) -> dict:
        """Concatenate storyboard videos (with audio) for one episode."""
        storyboards = (
            await db.execute(
                select(Storyboard)
                .where(Storyboard.episode_id == episode.id)
                .order_by(Storyboard.index)
            )
        ).scalars().all()

        if not storyboards:
            return {"error": "Episode has no storyboards"}

        ffmpeg = _find_ffmpeg()
        if not ffmpeg:
            return {"error": "ffmpeg not found in PATH or ./tools/ffmpeg/"}

        # Build segment inputs
        segments = []
        for sb in storyboards:
            if not sb.video_path:
                continue
            segments.append((sb, sb.video_path))

        if not segments:
            return {"error": "No storyboard videos available"}

        # Output path
        out_dir = Path(settings.storage_local_root) / "composite" / str(project.id)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"episode_{episode.index}.mp4"

        # Strategy:
        # 1) Concatenate all video segments (using concat demuxer for safety with different codecs)
        # 2) If audio_path available per sb, mix audio; else skip
        # 3) Optional subtitle burn-in (skip for v2.1 — too complex)

        concat_list = out_dir / f"concat_ep_{episode.id}.txt"
        with open(concat_list, "w", encoding="utf-8") as f:
            for sb, vp in segments:
                # Use absolute path, escape single quotes
                escaped = vp.replace("'", "'\\''")
                f.write(f"file '{escaped}'\n")

        cmd = [
            ffmpeg, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list),
            "-c", "copy",
            "-movflags", "+faststart",
            str(out_path),
        ]

        rc, _, stderr = await _run_ffmpeg(cmd)
        concat_list.unlink(missing_ok=True)

        if rc != 0 or not out_path.exists() or out_path.stat().st_size == 0:
            logger.error("ffmpeg_concat_failed", extra={"stderr": stderr[:500]})
            return {"error": f"ffmpeg concat failed: {stderr[:300]}"}

        episode.final_video_path = str(out_path)
        await db.commit()

        return {
            "status": "ok",
            "episode_id": episode.id,
            "final_video_path": str(out_path),
            "size_bytes": out_path.stat().st_size,
            "duration_seconds": sum(
                float(getattr(sb, "duration_seconds", 5) or 5) for sb, _ in segments
            ),
        }

    @staticmethod
    async def merge_project(
        db: AsyncSession,
        project: Project,
    ) -> dict:
        """Merge all episodes into a final project video."""
        episodes = (
            await db.execute(
                select(Episode).where(Episode.project_id == project.id).order_by(Episode.index)
            )
        ).scalars().all()

        # First make sure each episode has final_video_path
        results = []
        for ep in episodes:
            if ep.final_video_path:
                results.append({"episode": ep.index, "status": "ready", "path": ep.final_video_path})
                continue
            r = await CompositeService.merge_episode(db, ep, project)
            results.append({"episode": ep.index, **r})

        # If all episodes have final video, concat them into one
        ready = [ep for ep in episodes if ep.final_video_path]
        if len(ready) < len(episodes):
            return {"episodes": results, "project_final": "pending", "missing": len(episodes) - len(ready)}

        ffmpeg = _find_ffmpeg()
        if not ffmpeg:
            return {"episodes": results, "error": "ffmpeg not found"}

        out_dir = Path(settings.storage_local_root) / "composite" / str(project.id)
        out_dir.mkdir(parents=True, exist_ok=True)
        final_path = out_dir / f"project_{project.id}_final.mp4"

        concat_list = out_dir / "concat_project.txt"
        with open(concat_list, "w", encoding="utf-8") as f:
            for ep in ready:
                escaped = ep.final_video_path.replace("'", "'\\''")
                f.write(f"file '{escaped}'\n")

        cmd = [
            ffmpeg, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list),
            "-c", "copy",
            "-movflags", "+faststart",
            str(final_path),
        ]
        rc, _, stderr = await _run_ffmpeg(cmd)
        concat_list.unlink(missing_ok=True)

        if rc != 0 or not final_path.exists():
            return {"episodes": results, "error": f"project concat failed: {stderr[:300]}"}

        project.final_video_path = str(final_path)
        project.video_status = "done"
        await db.commit()

        return {
            "episodes": results,
            "project_final": str(final_path),
            "size_bytes": final_path.stat().st_size,
        }