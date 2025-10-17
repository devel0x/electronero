"""FastAPI dependency helpers."""
from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, status

from .auth import get_current_user
from .models import UserPublic, UserRole


def require_roles(*roles: UserRole) -> Callable[[UserPublic], UserPublic]:
    """FastAPI dependency enforcing that the current user has one of the roles."""

    allowed_roles: set[UserRole] = set(roles)

    async def dependency(current_user: UserPublic = Depends(get_current_user)) -> UserPublic:
        if current_user.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return current_user

    return dependency


def require_super_admin() -> Callable[[UserPublic], UserPublic]:
    """Shortcut dependency for super-admin protected endpoints."""

    return require_roles(UserRole.SUPER_ADMIN)


def require_org_admin() -> Callable[[UserPublic], UserPublic]:
    """Shortcut dependency for org-admin and super-admin roles."""

    return require_roles(UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN)
