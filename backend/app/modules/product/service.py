"""ProductService — 从手工填写的商品信息创建带货项目。

输入:商品名/卖点/价格/风格等,自动创建 Project + Episode,
把 selling_points 织入每个 episode 的 outline 和剧本题材。
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.project.models import Episode, Project


class ProductService:
    @staticmethod
    async def create_from_manual(
        db: AsyncSession,
        user: User,
        *,
        name: str,
        price: float | None,
        selling_points: list[str],
        target_audience: str = "",
        style: str = "美妆时尚",
        episode_count: int = 5,
        seconds_per_episode: int = 15,
    ) -> Project:
        """Create a 带货 project + episodes from manual product info."""
        topic_parts = [f"带货商品:{name}"]
        if price:
            topic_parts.append(f"售价:¥{price}")
        if target_audience:
            topic_parts.append(f"目标人群:{target_audience}")
        topic_parts.append("核心卖点:" + " / ".join(selling_points))
        topic = " | ".join(topic_parts)

        project = Project(
            owner_id=user.id,
            name=f"带货:{name}",
            type="daihuo",
            style=style,
            topic=topic,
            product_detail=" / ".join(selling_points),
            episode_count=episode_count,
            seconds_per_episode=seconds_per_episode,
            aspect_ratio="9:16",  # 带货短剧默认竖屏
        )
        db.add(project)
        await db.flush()

        # Create one episode per selling_point + 1 opening + 1 closing
        episode_titles = ProductService._build_episode_titles(name, selling_points, episode_count)
        for idx, title in enumerate(episode_titles[:episode_count], start=1):
            outline = ProductService._build_outline(name, selling_points, idx, episode_count)
            db.add(
                Episode(
                    project_id=project.id,
                    index=idx,
                    title=title,
                    outline=outline,
                )
            )

        await db.commit()
        await db.refresh(project)
        return project

    @staticmethod
    def _build_episode_titles(name: str, points: list[str], count: int) -> list[str]:
        """Build episode titles for 带货 structure."""
        titles = ["开场·痛点引入"]
        for i, p in enumerate(points[: count - 2]):
            titles.append(f"卖点{i + 1}·{p[:8]}")
        titles.append("结尾·行动号召")
        # Pad if needed
        while len(titles) < count:
            titles.append(f"补充镜头")
        return titles[:count]

    @staticmethod
    def _build_outline(name: str, points: list[str], idx: int, total: int) -> str:
        """Build episode outline that weaves the product into a story."""
        if idx == 1:
            return f"第一集:观众日常场景中遇到痛点,自然引出{name},埋下期待。"
        if idx == total:
            last_point = points[-1] if points else "性价比"
            return f"最终集:总结所有卖点({last_point}),限时优惠,引导立即下单。"
        # Middle episodes: one selling point per episode
        point_idx = idx - 2
        if 0 <= point_idx < len(points):
            return f"第{idx}集:围绕'{points[point_idx]}'展开,展示{name}的真实使用场景。"
        return f"第{idx}集:{name}的补充使用场景。"