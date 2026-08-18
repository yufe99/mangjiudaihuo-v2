"""Project API router."""
from __future__ import annotations

from datetime import datetime

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
    return [ProjectResponse.model_validate(p) for p in result.scalars().all()]


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
    return ProjectResponse.model_validate(project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_session),
) -> ProjectResponse:
    project = await db.get(Project, project_id)
    if not project or project.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectResponse.model_validate(project)


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
    return ProjectResponse.model_validate(project)


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