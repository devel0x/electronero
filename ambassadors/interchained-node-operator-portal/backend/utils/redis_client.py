"""Utility helpers for working with Redis connections."""
from __future__ import annotations

import os
from functools import lru_cache
from typing import AsyncIterator

from redis.asyncio import Redis


@lru_cache
def _build_redis_client() -> Redis:
    """Instantiate a Redis client targeting DB 6 by default.

    The connection URL can be overridden with the ``REDIS_URL`` environment
    variable so deployments can supply their own Redis host/port credentials.
    """

    url = os.getenv("REDIS_URL", "redis://localhost:6379/6")
    return Redis.from_url(url, decode_responses=True)


async def get_redis() -> Redis:
    """Return a cached Redis client instance.

    The redis-py asyncio client manages its own connection pool so we can share
    the instance safely between requests. The application is responsible for
    calling :func:`close_redis` on shutdown to close the pool cleanly.
    """

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
