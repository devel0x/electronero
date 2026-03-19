"""Reusable FastAPI dependencies."""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import get_settings
from .models import AuthenticatedUser
from .security import decode_access_token
from .storage import RedisRepository

security = HTTPBearer(auto_error=True)
repo = RedisRepository()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> AuthenticatedUser:
    payload = decode_access_token(credentials.credentials)
    user_id = payload.get("sub")
    email = payload.get("email")
    if not user_id or not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    user_data = await repo.get_user_by_id(str(user_id))
    if not user_data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    role = user_data.get("role", "operator")
    is_admin = payload.get("is_admin", role == "admin")
    return AuthenticatedUser(id=str(user_id), email=email, is_admin=bool(is_admin))


async def require_admin_user(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    return user


async def require_admin_access(
    user: AuthenticatedUser = Depends(require_admin_user),
    portal_key: str | None = Header(default=None, alias="X-Admin-Portal-Key"),
) -> AuthenticatedUser:
    settings = get_settings()
    required_password = settings.admin_portal_password
    if required_password:
        if not portal_key or portal_key != required_password:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin portal password required",
            )
    return user
