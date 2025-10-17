"""Security utilities for password hashing and JWT token management."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import jwt
from fastapi import HTTPException, status
from passlib.context import CryptContext

from .config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""

    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """Check whether the password matches the stored hash."""

    return pwd_context.verify(password, hashed)


def create_access_token(subject: str, claims: Dict[str, Any] | None = None) -> str:
    """Generate a signed JWT containing the provided subject and optional claims."""

    settings = get_settings()
    expire_delta = timedelta(seconds=settings.access_token_ttl_seconds)
    to_encode: Dict[str, Any] = {
        "sub": subject,
        "exp": datetime.now(timezone.utc) + expire_delta,
        "iat": datetime.now(timezone.utc),
    }
    if claims:
        to_encode.update(claims)
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT access token."""

    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired") from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc
    return payload
