from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings
from .models import Role, User
from .redis_client import get_redis
from . import redis_keys

security = HTTPBearer(auto_error=False)


async def _find_user_by_username(username: str) -> Optional[User]:
    redis = await get_redis()
    async for key in redis.scan_iter(match=f"{settings.redis_key_prefix}u:*"):
        data = await redis.hgetall(key)
        if data.get("username") == username:
            uid = key.split(":")[-1]
            return User(uid=uid, **data)
    return None


async def login_user(username: str, role: Role) -> User:
    redis = await get_redis()
    existing = await _find_user_by_username(username)
    if existing:
        return existing
    uid = uuid4().hex
    now = datetime.utcnow().isoformat()
    user_data = {
        "role": role,
        "username": username,
        "status": "active",
        "created_at": now,
    }
    await redis.hset(redis_keys.user(uid), mapping=user_data)
    await redis.sadd(redis_keys.role_set(role), uid)
    return User(uid=uid, **user_data)


async def create_session(uid: str) -> str:
    redis = await get_redis()
    token = uuid4().hex
    await redis.set(redis_keys.session(token), uid, ex=settings.session_ttl_seconds)
    return token


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    redis = await get_redis()
    token = credentials.credentials
    uid = await redis.get(redis_keys.session(token))
    if not uid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    data = await redis.hgetall(redis_keys.user(uid))
    if not data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return User(uid=uid, **data)


async def logout_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> None:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    redis = await get_redis()
    await redis.delete(redis_keys.session(credentials.credentials))
