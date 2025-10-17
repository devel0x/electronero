"""Authentication utilities for the Node Operator portal."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext

from .config import get_settings
from .models import (
    AdminUserCreate,
    InviteCreate,
    InvitePublic,
    OrganizationCreate,
    ServicePlanTier,
    SessionToken,
    UserCreate,
    UserPublic,
    UserRole,
)
from .services.audit import record_audit_event
from .services.organizations import create_organization, get_organization
from .utils.ids import random_token
from .utils.redis_client import get_redis

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)


async def get_user(email: str) -> Optional[dict[str, str]]:
    redis = await get_redis()
    user_key = f"users:{email}"
    user = await redis.hgetall(user_key)
    return user or None


async def create_user(payload: UserCreate) -> UserPublic:
    """Register a user using an invite or bootstrap the first super admin."""

    redis = await get_redis()
    existing = await redis.hgetall(f"users:{payload.email}")
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already exists")

    invite_details = await _consume_invite(payload.invite_code) if payload.invite_code else None
    total_users = int(await redis.get("meta:user_count") or 0)

    if invite_details:
        organization_id = invite_details["organization_id"]
        role = UserRole(invite_details["role"])
    elif total_users == 0:
        org = await create_organization(
            OrganizationCreate(name="Interchained Core", billing_email=payload.email, plan=ServicePlanTier.ENTERPRISE),
            owner_email=payload.email,
        )
        organization_id = org.id
        role = UserRole.SUPER_ADMIN
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Registration requires an invitation")

    created_at = datetime.utcnow()
    await redis.hset(
        f"users:{payload.email}",
        mapping={
            "email": payload.email,
            "password": pwd_context.hash(payload.password),
            "full_name": payload.full_name,
            "created_at": created_at.isoformat(),
            "organization_id": organization_id,
            "role": role.value,
            "is_active": 1,
        },
    )
    await redis.sadd(f"org:{organization_id}:members", payload.email)
    await redis.incr("meta:user_count")
    await record_audit_event(
        actor_email=payload.email,
        action="user.registered",
        organization_id=organization_id,
        metadata={"role": role.value},
    )
    return UserPublic(
        email=payload.email,
        full_name=payload.full_name,
        organization_id=organization_id,
        role=role,
        created_at=created_at,
    )


async def create_admin_user(payload: AdminUserCreate, actor: UserPublic) -> UserPublic:
    redis = await get_redis()
    organization = await get_organization(payload.organization_id)
    if not organization:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    if actor.role != UserRole.SUPER_ADMIN and payload.organization_id != actor.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot manage another organization")
    if actor.role != UserRole.SUPER_ADMIN and payload.role == UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only super admins can grant super admin access")
    if await redis.exists(f"users:{payload.email}"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already exists")
    created_at = datetime.utcnow()
    await redis.hset(
        f"users:{payload.email}",
        mapping={
            "email": payload.email,
            "password": pwd_context.hash(payload.password),
            "full_name": payload.full_name,
            "created_at": created_at.isoformat(),
            "organization_id": payload.organization_id,
            "role": payload.role.value,
            "is_active": 1,
        },
    )
    await redis.sadd(f"org:{payload.organization_id}:members", payload.email)
    await redis.incr("meta:user_count")
    await record_audit_event(
        actor_email=actor.email,
        action="user.invited",
        organization_id=payload.organization_id,
        target=payload.email,
        metadata={"role": payload.role.value},
    )
    return UserPublic(
        email=payload.email,
        full_name=payload.full_name,
        organization_id=payload.organization_id,
        role=payload.role,
        created_at=created_at,
    )


async def list_org_users(organization_id: str) -> list[UserPublic]:
    redis = await get_redis()
    members = await redis.smembers(f"org:{organization_id}:members")
    results: list[UserPublic] = []
    for email in members:
        data = await redis.hgetall(f"users:{email}")
        if not data or not int(data.get("is_active", 1)):
            continue
        results.append(_deserialize_user(data))
    return sorted(results, key=lambda u: u.created_at)


async def update_user_role(email: str, role: UserRole, actor: UserPublic) -> UserPublic:
    redis = await get_redis()
    user_data = await redis.hgetall(f"users:{email}")
    if not user_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if actor.role != UserRole.SUPER_ADMIN and user_data.get("organization_id") != actor.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot manage another organization")
    if actor.role != UserRole.SUPER_ADMIN and role == UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only super admins can grant super admin access")
    await redis.hset(f"users:{email}", mapping={"role": role.value})
    await record_audit_event(
        actor_email=actor.email,
        action="user.role.updated",
        organization_id=user_data.get("organization_id"),
        target=email,
        metadata={"role": role.value},
    )
    user_data["role"] = role.value
    return _deserialize_user(user_data)


async def deactivate_user(email: str, actor: UserPublic) -> None:
    redis = await get_redis()
    user_key = f"users:{email}"
    user_data = await redis.hgetall(user_key)
    if not user_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if actor.role != UserRole.SUPER_ADMIN and user_data.get("organization_id") != actor.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot manage another organization")
    await redis.hset(user_key, mapping={"is_active": 0})
    await redis.srem(f"org:{user_data['organization_id']}:members", email)
    await record_audit_event(
        actor_email=actor.email,
        action="user.deactivated",
        organization_id=user_data.get("organization_id"),
        target=email,
    )


async def authenticate_user(email: str, password: str) -> Optional[UserPublic]:
    user = await get_user(email)
    if not user or not int(user.get("is_active", 1)):
        return None
    if not pwd_context.verify(password, user.get("password", "")):
        return None
    return _deserialize_user(user)


async def create_session_token(user: UserPublic) -> SessionToken:
    redis = await get_redis()
    settings = get_settings()
    token = random_token()
    payload = {
        "email": user.email,
        "role": user.role.value,
        "organization_id": user.organization_id,
    }
    await redis.setex(f"sessions:{token}", settings.session_ttl_seconds, json.dumps(payload))
    return SessionToken(access_token=token, expires_in=settings.session_ttl_seconds, user=user)


async def resolve_token(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> UserPublic:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing credentials")
    redis = await get_redis()
    raw = await redis.get(f"sessions:{credentials.credentials}")
    if not raw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    payload = json.loads(raw)
    user = await get_user(payload["email"])
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
    return _deserialize_user(user)


async def get_current_user(user: UserPublic = Depends(resolve_token)) -> UserPublic:
    return user


async def create_invite(payload: InviteCreate, actor: UserPublic) -> InvitePublic:
    redis = await get_redis()
    organization = await get_organization(payload.organization_id)
    if not organization:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    if actor.role != UserRole.SUPER_ADMIN and organization.id != actor.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot invite to another organization")
    if actor.role != UserRole.SUPER_ADMIN and payload.role == UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only super admins can invite super admins")
    code = random_token(20)
    expires_at = datetime.utcnow() + timedelta(hours=payload.expires_in_hours)
    await redis.hset(
        f"invites:{code}",
        mapping={
            "code": code,
            "organization_id": payload.organization_id,
            "role": payload.role.value,
            "expires_at": expires_at.isoformat(),
            "created_by": actor.email,
            "note": payload.note or "",
        },
    )
    await redis.sadd("invites:index", code)
    await record_audit_event(
        actor_email=actor.email,
        action="invite.created",
        organization_id=payload.organization_id,
        metadata={"code": code, "role": payload.role.value},
    )
    return InvitePublic(
        code=code,
        organization_id=payload.organization_id,
        role=payload.role,
        expires_at=expires_at,
        created_by=actor.email,
        note=payload.note,
    )


async def list_invites(organization_id: str) -> list[InvitePublic]:
    redis = await get_redis()
    codes = await redis.smembers("invites:index")
    invites: list[InvitePublic] = []
    for code in codes:
        data = await redis.hgetall(f"invites:{code}")
        if not data or data.get("organization_id") != organization_id:
            continue
        expires_at = datetime.fromisoformat(data["expires_at"])
        if expires_at < datetime.utcnow():
            await redis.delete(f"invites:{code}")
            await redis.srem("invites:index", code)
            continue
        invites.append(
            InvitePublic(
                code=data["code"],
                organization_id=data["organization_id"],
                role=UserRole(data["role"]),
                expires_at=expires_at,
                created_by=data["created_by"],
                note=data.get("note") or None,
            )
        )
    return invites


async def _consume_invite(code: str | None) -> dict[str, Any] | None:
    if not code:
        return None
    redis = await get_redis()
    data = await redis.hgetall(f"invites:{code}")
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid invitation code")
    expires_at = datetime.fromisoformat(data["expires_at"])
    if expires_at < datetime.utcnow():
        await redis.delete(f"invites:{code}")
        await redis.srem("invites:index", code)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invitation expired")
    await redis.delete(f"invites:{code}")
    await redis.srem("invites:index", code)
    return data


def _deserialize_user(data: dict[str, str]) -> UserPublic:
    return UserPublic(
        email=data["email"],
        full_name=data.get("full_name", data["email"]),
        organization_id=data.get("organization_id", ""),
        role=UserRole(data.get("role", UserRole.OPERATOR.value)),
        created_at=datetime.fromisoformat(data["created_at"]),
    )
