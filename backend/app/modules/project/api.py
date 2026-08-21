"""Project API router."""
from __future__ import annotations

from datetime import datetime

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.db import get_session
from app.core.security import verify_token_type
from app.modules.auth.models import User
from app.modules.project.models import Project

router = APIRouter(prefix="/projects",)
bearer_scheme = HTTPBearer(auto_error=False)


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    type: str = Field(default="manju", pattern="^(manju|daihuo)$")
    style: str = Field(default="", max_length=64)
    topic: str = Field(default="", max_length=2000)
    product_url: str = Field(default="", max_length=500)
    product_detail: str = Field(default="", max_length=5000)
    episode_count: int = Field(default=3, ge=1, le=10)
    seconds_per_episode: int = Field(default=15, ge=5, le=60)
    aspect_ratio: str = Field(default="16:9", pattern="^(16:9|9:16|1:1)$")


class ProjectUpdate(BaseModel):
    name: str | None = None
    topic: str | None = None
    product_url: str | None = None
    product_detail: str | None = None
    style: str | None = None


class EpisodeSummary(BaseModel):
    id: int
    index: int
    title: str
    outline: str
    storyboard_json: dict | None = None
    video_status: str
    final_video_path: str

    model_config = ConfigDict(from_attributes=True)


class ProjectResponse(BaseModel):
    id: int
    name: str
    type: str
    style: str
    topic: str
    product_url: str
    episode_count: int
    seconds_per_episode: int
    aspect_ratio: str
    characters_status: str
    storyboard_status: str
    video_status: str
    final_video_path: str
    created_at: datetime
    updated_at: datetime
    episodes: list[EpisodeSummary] = []

    model_config = ConfigDict(from_attributes=True)


async def current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_session),
) -> User:
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing token")
    try:
        payload = verify_token_type(credentials.credentials, "access")
    except JWTError as e:
        raise HTTPException(status_code=401, detail=str(e))
    user = await db.get(User, int(payload["sub"]))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_session),
) -> list[ProjectResponse]:
    """List current user's projects, newest first."""
    result = await db.execute(
        select(Project).where(Project.owner_id == user.id).order_by(Project.created_at.desc())
    )
    projects = result.scalars().all()
    return [await _project_to_response(db, p) for p in projects]


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    req: ProjectCreate,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_session),
) -> ProjectResponse:
    """Create a new project."""
    project = Project(
        owner_id=user.id,
        **req.model_dump(),
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return await _project_to_response(db, project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_session),
) -> ProjectResponse:
    project = await db.get(Project, project_id)
    if not project or project.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Project not found")
    return await _project_to_response(db, project)


@router.get("/{project_id}/download/{file_type}")
async def download_file(
    project_id: int,
    file_type: str,  # "project" | "episode-{n}" | "script"
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_session),
):
    """Download generated file.

    file_type options:
    - "project": final concatenated project video
    - "episode-1", "episode-2", ...: per-episode video
    - "script": the script JSON (LLM-generated or template)
    """
    from fastapi.responses import FileResponse, JSONResponse
    from sqlalchemy import select

    project = await db.get(Project, project_id)
    if not project or project.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Project not found")

    if file_type == "project":
        if not project.final_video_path:
            raise HTTPException(status_code=404, detail="Project video not ready yet")
        path = Path(project.final_video_path)
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {path}")
        return FileResponse(
            path=str(path), media_type="video/mp4",
            filename=f"project_{project.id}.mp4",
        )

    if file_type == "script":
        if not project.script_json:
            raise HTTPException(status_code=404, detail="Script not generated yet")
        return JSONResponse(content=project.script_json)

    if file_type.startswith("episode-"):
        try:
            ep_idx = int(file_type.split("-")[1])
        except (ValueError, IndexError):
            raise HTTPException(status_code=400, detail="Bad episode index")
        ep = (
            await db.execute(
                select(Episode).where(
                    Episode.project_id == project.id, Episode.index == ep_idx
                )
            )
        ).scalar_one_or_none()
        if not ep:
            raise HTTPException(status_code=404, detail=f"Episode {ep_idx} not found")
        if not ep.final_video_path:
            raise HTTPException(status_code=404, detail=f"Episode {ep_idx} video not ready yet")
        path = Path(ep.final_video_path)
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {path}")
        return FileResponse(
            path=str(path), media_type="video/mp4",
            filename=f"episode_{ep_idx}.mp4",
        )

    raise HTTPException(status_code=400, detail=f"Unknown file_type: {file_type}")


@router.post("/{project_id}/approve/{step}")
async def approve_step(
    project_id: int,
    step: str,  # "script" | "characters" | "storyboard"
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Mark a pipeline step as approved.

    Frontend workflow:
      ① 生成剧本 → 显示剧本 → 用户审核 → [通过] → 调本端点
      ② 生成角色/资产 → 显示 → 用户审核 → [通过] → 调本端点
      ③ 生成集1分镜 → 显示 → 用户审核 → [通过] → 调本端点

    step ∈ "script" | "characters" | "storyboard"
    (视频/配音/合成的审核按集,在 episode scope 下做)
    """
    from app.modules.approval import approve, persist

    project = await db.get(Project, project_id)
    if not project or project.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Project not found")

    if step not in ("script", "characters", "storyboard"):
        raise HTTPException(status_code=400, detail=f"Unknown step: {step}")

    # Validate that the step's content actually exists before allowing approval
    if step == "script" and not project.script_json:
        raise HTTPException(status_code=400, detail="剧本还没生成,无法审核")
    if step == "characters":
        # at least one character must have a done status
        from app.modules.character.models import Character
        from sqlalchemy import select
        chars = (
            await db.execute(
                select(Character).where(Character.project_id == project_id)
            )
        ).scalars().all()
        if not chars:
            raise HTTPException(status_code=400, detail="角色还没生成,无法审核")
        if not all(c.status == "done" for c in chars):
            bad = [c.name for c in chars if c.status != "done"]
            raise HTTPException(
                status_code=400,
                detail=f"有角色未生成完成:{','.join(bad)}",
            )
    if step == "storyboard":
        from sqlalchemy import select
        from app.modules.storyboard.models import Storyboard
        from app.modules.project.models import Episode
        eps = (
            await db.execute(
                select(Episode).where(Episode.project_id == project_id)
            )
        ).scalars().all()
        if not eps:
            raise HTTPException(status_code=400, detail="项目没有剧集")
        has_shot = False
        for ep in eps:
            sb = (
                await db.execute(
                    select(Storyboard).where(Storyboard.episode_id == ep.id)
                )
            ).scalars().all()
            if sb:
                has_shot = True
        if not has_shot:
            raise HTTPException(
                status_code=400,
                detail="还没生成分镜",
            )

    approve(project, step)
    await persist(db, project)

    return {"status": "approved", "step": step, "approved_at": now_iso()}


def now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


@router.post("/{project_id}/unapprove/{step}")
async def unapprove_step(
    project_id: int,
    step: str,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Un-approve a step (allows regenerating)."""
    from app.modules.approval import disapprove

    project = await db.get(Project, project_id)
    if not project or project.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Project not found")
    if step not in ("script", "characters", "storyboard"):
        raise HTTPException(status_code=400, detail=f"Unknown step: {step}")
    disapprove(project, step)
    await db.commit()
    return {"status": "unapproved", "step": step}


@router.get("/{project_id}/approvals")
async def get_approvals(
    project_id: int,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Return all step approvals for the project + per-episode approvals."""
    from app.modules.approval import build_approvals_view
    from app.modules.project.models import Episode

    project = await db.get(Project, project_id)
    if not project or project.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Project not found")

    base = build_approvals_view(project)

    # Per-episode approvals: stored in episode.script_outline (or a separate field)
    eps = (
        await db.execute(
            select(Episode).where(Episode.project_id == project_id)
        )
    ).scalars().all()
    base["episodes"] = {
        ep.index: {
            "video": ep.video_status,
            "final_video": ep.final_video_path,
            "script_outline": ep.script_outline,
        }
        for ep in eps
    }
    return base


@router.post("/{project_id}/episodes/{episode_id}/approve/{step}")
async def approve_episode_step(
    project_id: int,
    episode_id: int,
    step: str,  # "video" | "tts" | "compose"
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Approve a per-episode step (video/tts/compose).

    video: 所有分镜都生成完成 + 视频下载就绪
    tts: TTS 配音生成完成
    compose: 合成 MP4 生成完成
    """
    from datetime import datetime, timezone
    from app.modules.project.models import Episode

    episode = await db.get(Episode, episode_id)
    if not episode or episode.project_id != project_id:
        raise HTTPException(status_code=404, detail="Episode not found")
    project = await db.get(Project, episode.project_id)
    if not project or project.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Episode not found")

    if step not in ("video", "tts", "compose"):
        raise HTTPException(status_code=400, detail=f"Unknown step: {step}")

    # Validate prerequisite
    if step == "video":
        from app.modules.storyboard.models import Storyboard
        sb = (
            await db.execute(
                select(Storyboard).where(Storyboard.episode_id == episode_id)
            )
        ).scalars().all()
        if not sb:
            raise HTTPException(status_code=400, detail="EP 没有分镜")
        missing = [s.index for s in sb if not s.video_path]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"分镜 {missing} 还没生成视频",
            )
    elif step == "compose":
        if not episode.final_video_path:
            raise HTTPException(status_code=400, detail="EP 没合成最终视频")

    # Store approval in episode.script_outline as JSON
    import json
    outline = {}
    try:
        outline = json.loads(episode.script_outline or "{}")
    except Exception:
        pass
    outline[f"approved_{step}_at"] = datetime.now(timezone.utc).isoformat()
    episode.script_outline = json.dumps(outline, ensure_ascii=False)
    await db.commit()

    return {"status": "approved", "episode_id": episode_id, "step": step}


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    req: ProjectUpdate,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_session),
) -> ProjectResponse:
    project = await db.get(Project, project_id)
    if not project or project.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Project not found")
    for k, v in req.model_dump(exclude_unset=True).items():
        setattr(project, k, v)
    await db.commit()
    await db.refresh(project)
    return await _project_to_response(db, project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_session),
) -> None:
    project = await db.get(Project, project_id)
    if not project or project.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Project not found")
    await db.delete(project)
    await db.commit()


async def _project_to_response(db: AsyncSession, project: Project) -> ProjectResponse:
    """Build ProjectResponse, eagerly loading episodes to avoid lazy-load errors."""
    from app.modules.project.models import Episode
    from sqlalchemy import select

    episodes_q = (
        await db.execute(
            select(Episode).where(Episode.project_id == project.id).order_by(Episode.index)
        )
    ).scalars().all()
    episodes = [EpisodeSummary.model_validate(e) for e in episodes_q]
    # Build response dict directly to avoid Pydantic trying to lazy-load episodes via from_attributes
    return ProjectResponse(
        id=project.id,
        name=project.name,
        type=project.type,
        style=project.style,
        topic=project.topic,
        product_url=project.product_url,
        episode_count=project.episode_count,
        seconds_per_episode=project.seconds_per_episode,
        aspect_ratio=project.aspect_ratio,
        characters_status=project.characters_status,
        storyboard_status=project.storyboard_status,
        video_status=project.video_status,
        final_video_path=project.final_video_path,
        created_at=project.created_at,
        updated_at=project.updated_at,
        episodes=episodes,
    )