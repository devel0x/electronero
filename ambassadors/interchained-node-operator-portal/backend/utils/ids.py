"""Helpers for generating human friendly identifiers."""
from __future__ import annotations

import secrets
import string
from uuid import uuid4


def short_ulid(prefix: str) -> str:
    """Return a short identifier prefixed with the provided namespace."""

    token = uuid4().hex[:12]
    return f"{prefix}_{token}"


def random_token(length: int = 32) -> str:
    """Generate a secure random token suitable for API keys or invites."""

    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))
