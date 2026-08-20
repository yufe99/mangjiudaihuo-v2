"""Product API — 带货商品入口(只暴露 1 个端点)。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.modules.auth.models import User
from app.modules.product.service import ProductService
from app.modules.project.api import current_user

router = APIRouter(prefix="/products")


class FromManualRequest(BaseModel):
    """带货商品表单。最小字段,只填这 3 个就能跑。"""

    name: str = Field(min_length=1, max_length=100, description="商品名")
    price: float | None = Field(default=None, ge=0, description="价格")
    selling_points: list[str] = Field(
        min_length=1, max_length=10, description="卖点列表,1-10 条"
    )
    target_audience: str = Field(default="", max_length=100, description="目标人群")
    style: str = Field(
        default="美妆时尚", description="风格:美妆时尚/家居好物/数码电子/食品饮料/..."
    )
    episode_count: int = Field(default=5, ge=2, le=10, description="集数(2-10)")
    seconds_per_episode: int = Field(default=10, ge=5, le=30, description="每集秒数(5-30)")


class FromManualResponse(BaseModel):
    project_id: int
    project_name: str
    episode_count: int
    next_step: str  # 告诉前端下一步该调什么


@router.post("/from-manual", response_model=FromManualResponse)
async def create_product_from_manual(
    req: FromManualRequest,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_session),
) -> FromManualResponse:
    """从手工填写的商品信息创建带货项目。

    **这个端点就够了** —— 用户不需要碰其他模块的 API。

    下一步:POST /api/v1/projects/{project_id}/run-all
    """
    if not req.name.strip():
        raise HTTPException(status_code=400, detail="商品名称不能为空")
    clean_points = [p.strip() for p in req.selling_points if p.strip()]
    if not clean_points:
        raise HTTPException(status_code=400, detail="至少填 1 个卖点")

    project = await ProductService.create_from_manual(
        db,
        user,
        name=req.name.strip(),
        price=req.price,
        selling_points=clean_points,
        target_audience=req.target_audience.strip(),
        style=req.style,
        episode_count=req.episode_count,
        seconds_per_episode=req.seconds_per_episode,
    )

    return FromManualResponse(
        project_id=project.id,
        project_name=project.name,
        episode_count=project.episode_count,
        next_step=f"POST /api/v1/projects/{project.id}/run-all",
    )