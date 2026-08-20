"""Product API — the ONLY endpoint user-facing for.

POST /api/v1/products/from-manual
    输入:商品名/价格/卖点 → 返回 project_id
POST /api/v1/projects/{id}/run-all  (added in api.py)
GET /api/v1/projects/{id}/download/{type} (added in project module)
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.modules.product.service import ProductService

__all__ = ["ProductService"]