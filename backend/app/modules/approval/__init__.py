"""审核流程模块。

每个项目(Project)有 6 个 step 状态:
- step_script_approved: bool   (①剧本)
- step_characters_approved: bool (②角色+资产)
- step_storyboard_approved: bool (③分镜)
- step_video_approved: bool      (④视频,按集)
- step_tts_approved: bool        (⑤配音,按集)
- step_compose_approved: bool    (⑥合成,按集)

不通过 = 不能进下一步。

为了让审核状态可记录但又不污染项目模型字段,
我们用 Project.script_json 的 _approved 子键:

script_json: {
    "approved_at":": "2026-08-20T...",
    "approved_characters_at": "...",
    "approved_storyboard_at": "...",
    "approved_episode_1": "...",   # 该集 ④⑤⑥ 通过时间
}
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.project.models import Project


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_approval(project: Project, step: str) -> str | None:
    """Get ISO timestamp of approval for a step, or None if not approved."""
    if not project.script_json:
        return None
    return project.script_json.get(f"approved_{step}")


def approve(project: Project, step: str) -> None:
    """Mark step as approved. Stores in script_json._approved_xxx."""
    if not project.script_json:
        project.script_json = {}
    project.script_json[f"approved_{step}"] = now_iso()


def disapprove(project: Project, step: str) -> None:
    """Unapprove a step (allows regenerating)."""
    if not project.script_json:
        return
    project.script_json.pop(f"approved_{step}", None)


def build_approvals_view(project: Project) -> dict:
    """Build a UI-friendly view of all approval states."""
    return {
        "script": get_approval(project, "script"),
        "characters": get_approval(project, "characters"),
        "storyboard": get_approval(project, "storyboard"),
        # 后续每集独立审核时再展开
    }


async def persist(db: AsyncSession, project: Project) -> None:
    """Persist approval state changes."""
    await db.commit()
    await db.refresh(project)