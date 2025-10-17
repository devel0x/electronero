"""Authentication utilities for the Node Operator portal."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext

from .models import UserCreate, UserPublic
from .utils.redis_client import get_redis

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

TOKEN_TTL = int(timedelta(days=7).total_seconds())
security = HTTPBearer(auto_error=False)


async def get_user(email: str) -> Optional[dict[str, str]]:
    redis = await get_redis()
    user_key = f"users:{email}"
    user = await redis.hgetall(user_key)
    return user or None


async def create_user(payload: UserCreate) -> UserPublic:
    redis = await get_redis()
    user_key = f"users:{payload.email}"
    exists = await redis.exists(user_key)
    if exists:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already exists")

    hashed = pwd_context.hash(payload.password)
    created_at = datetime.utcnow().isoformat()
    await redis.hset(
        user_key,
        mapping={
            "email": payload.email,
            "password": hashed,
            "created_at": created_at,
        },
    )
    return UserPublic(email=payload.email, created_at=datetime.fromisoformat(created_at))


async def authenticate_user(email: str, password: str) -> Optional[UserPublic]:
    user = await get_user(email)
    if not user:
        return None
    if not pwd_context.verify(password, user.get("password", "")):
        return None
    return UserPublic(email=email, created_at=datetime.fromisoformat(user["created_at"]))


async def create_session_token(email: str) -> str:
    redis = await get_redis()
    token = secrets.token_urlsafe(32)
    await redis.setex(f"sessions:{token}", TOKEN_TTL, email)
    return token


async def resolve_token(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing credentials")
    redis = await get_redis()
    email = await redis.get(f"sessions:{credentials.credentials}")
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return email


async def get_current_user(email: str = Depends(resolve_token)) -> UserPublic:
    user = await get_user(email)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
    return UserPublic(email=email, created_at=datetime.fromisoformat(user["created_at"]))
