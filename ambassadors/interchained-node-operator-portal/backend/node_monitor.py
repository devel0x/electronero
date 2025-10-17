"""Background task that periodically checks node health metrics."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from typing import Any

from .config import get_settings
from .utils.bitcoin_rpc import check_node_health
from .utils.redis_client import get_redis


class NodeMonitor:
    """Continuously check registered nodes and persist uptime metrics."""

    def __init__(self, interval_seconds: int | None = None) -> None:
        settings = get_settings()
        self._interval = interval_seconds or settings.monitor_interval_seconds
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
        node_ids = await redis.smembers("node:index")
        now = datetime.utcnow()

        for node_id in node_ids:
            node = await redis.hgetall(f"node:{node_id}")
            if not node:
                continue
            health = await check_node_health(node.get("p2p_address", ""), node.get("rpc_url", ""))
            stats_key = f"uptime:{node_id}"
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
                    "last_seen": now.isoformat(),
                    "latency_ms": health.latency_ms,
                    "block_height": health.block_height or 0,
                    "rpc_responding": int(health.rpc_responding),
                    "p2p_online": int(health.p2p_online),
                    "fully_online": int(health.is_fully_online),
                    "is_online": int(health.is_online), 
                },
            )
            timeseries_entry = json.dumps(
                {
                    "timestamp": now.isoformat(),
                    "node_id": node_id,
                    "uptime": uptime_score,
                }
            )
            await redis.zadd("metrics:uptime:global", {timeseries_entry: now.timestamp()})

        # Trim old uptime data
        cutoff = (datetime.utcnow() - timedelta(days=14)).timestamp()
        await redis.zremrangebyscore("metrics:uptime:global", 0, cutoff)
