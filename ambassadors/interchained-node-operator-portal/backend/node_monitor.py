"""Background task that periodically checks node health metrics."""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from .utils.bitcoin_rpc import check_node_health
from .utils.redis_client import get_redis, iter_hash_keys


class NodeMonitor:
    """Continuously check registered nodes and persist uptime metrics."""

    def __init__(self, interval_seconds: int = 60) -> None:
        self._interval = interval_seconds
        self._task: asyncio.Task[Any] | None = None
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        if self._task is None:
            self._stop_event.clear()
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task:
            self._stop_event.set()
            await self._task
            self._task = None

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            await self._check_all_nodes()
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self._interval)
            except asyncio.TimeoutError:
                continue

    async def _check_all_nodes(self) -> None:
        redis = await get_redis()
        async for key in iter_hash_keys("node:*"):
            node = await redis.hgetall(key)
            if not node:
                continue
            email = node.get("email")
            if not email:
                continue
            health = await check_node_health(node.get("p2p_address", ""), node.get("rpc_url", ""))
            stats_key = f"uptime:{email}"
            total_checks = await redis.hincrby(stats_key, "total_checks", 1)
            if health.is_online:
                successful_checks = await redis.hincrby(stats_key, "successful_checks", 1)
            else:
                successful_checks = int(await redis.hget(stats_key, "successful_checks") or 0)
            uptime_score = successful_checks / total_checks if total_checks else 0.0
            await redis.hset(
                stats_key,
                mapping={
                    "total_checks": total_checks,
                    "successful_checks": successful_checks,
                    "uptime_score": uptime_score,
                    "last_seen": datetime.utcnow().isoformat(),
                    "latency_ms": health.latency_ms,
                    "block_height": health.block_height or 0,
                    "rpc_responding": int(health.rpc_responding),
                },
            )
