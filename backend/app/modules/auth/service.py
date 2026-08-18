"""Auth service: registration, login, JWT issuance."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.modules.auth.models import User


class AuthService:
    """All auth business logic. Stateless — instance is a thin namespace."""

    @staticmethod
    async def register(
        db: AsyncSession,
        *,
        email: str,
        password: str,
        name: str = "",
    ) -> User:
        """Register a new user. Raises 409 if email exists."""
        existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )

        user = User(
            email=email,
            hashed_password=hash_password(password),
            name=name or email.split("@")[0],
            credits=settings.default_free_credits,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    @staticmethod
    async def authenticate(
        db: AsyncSession,
        *,
        email: str,
        password: str,
    ) -> User:
        """Verify credentials. Raises 401 on failure."""
        user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User disabled",
            )
        user.last_login_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(user)
        return user

    @staticmethod
    def issue_tokens(user: User) -> dict[str, str]:
        """Issue access + refresh JWT pair for a user."""
        return {
            "access_token": create_access_token(str(user.id), {"email": user.email}),
            "refresh_token": create_refresh_token(str(user.id)),
            "token_type": "bearer",
        }