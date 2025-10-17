"""Utility helpers for working with Redis connections."""
from __future__ import annotations

from functools import lru_cache
from typing import AsyncIterator

from redis.asyncio import Redis

from ..config import get_settings


@lru_cache
def _build_redis_client() -> Redis:
    """Instantiate a Redis client using the configured connection URL."""

    settings = get_settings()
    return Redis.from_url(str(settings.redis_url), decode_responses=True)


async def get_redis() -> Redis:
    """Return a cached Redis client instance."""

    return _build_redis_client()


async def close_redis() -> None:
    """Close the cached Redis connection pool, if one has been instantiated."""

    client = _build_redis_client()
    await client.close()


async def iter_hash_keys(prefix: str) -> AsyncIterator[str]:
    """Iterate over keys that match the provided hash prefix.

    Parameters
    ----------
    prefix:
        A glob-compatible prefix, e.g. ``"node:*"``.
    """

    client = await get_redis()
    async for key in client.scan_iter(match=prefix):
        yield key
