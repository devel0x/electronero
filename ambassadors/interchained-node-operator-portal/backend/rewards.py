"""Reward distribution utilities."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any

from .utils.redis_client import get_redis, iter_hash_keys


REWARD_PREFIX = "rewards:"
REWARD_HISTORY_PREFIX = "rewards:history:"


async def distribute_daily_rewards(date: datetime | None = None) -> dict[str, float]:
    redis = await get_redis()
    snapshot_date = (date or datetime.utcnow()).date()
    date_key = f"{REWARD_PREFIX}{snapshot_date.isoformat()}"

    total_pool_raw = await redis.get("pool:balance")
    total_pool = float(total_pool_raw or 0)
    if total_pool <= 0:
        return {}

    active_nodes: list[tuple[str, float]] = []
    async for key in iter_hash_keys("uptime:*"):
        stats = await redis.hgetall(key)
        email = key.split(":", 1)[1]
        score = float(stats.get("uptime_score", 0))
        if score >= 0.9:
            active_nodes.append((email, score))

    if not active_nodes:
        return {}

    total_weight = sum(score for _, score in active_nodes)
    if total_weight == 0:
        return {}

    rewards: dict[str, float] = {}
    for email, score in active_nodes:
        share = (score / total_weight) * total_pool
        rewards[email] = round(share, 8)

    if rewards:
        await redis.hset(date_key, mapping=rewards)
        await redis.set("pool:balance", 0)
        for email, amount in rewards.items():
            await redis.lpush(
                f"{REWARD_HISTORY_PREFIX}{email}",
                f"{snapshot_date.isoformat()}:{amount}",
            )
    return rewards


class RewardDistributor:
    """Background job that triggers a distribution once every 24 hours."""

    def __init__(self, run_at_hour: int = 0, run_at_minute: int = 5) -> None:
        self._run_at_hour = run_at_hour
        self._run_at_minute = run_at_minute
        self._task: asyncio.Task[Any] | None = None
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        if self._task is None:
            self._stop_event.clear()
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task:
            self._stop_event.set()
            await self._task
            self._task = None

    async def _loop(self) -> None:
        while not self._stop_event.is_set():
            seconds_until_run = self._seconds_until_next_run()
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=seconds_until_run)
                continue
            except asyncio.TimeoutError:
                await distribute_daily_rewards()

    def _seconds_until_next_run(self) -> float:
        now = datetime.utcnow()
        next_run = now.replace(hour=self._run_at_hour, minute=self._run_at_minute, second=0, microsecond=0)
        if next_run <= now:
            next_run = next_run + timedelta(days=1)
        return (next_run - now).total_seconds()
