"""Reward distribution utilities."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any

from .config import get_settings
from .models import ServicePlanTier
from .utils.redis_client import get_redis


REWARD_PREFIX = "rewards:"
REWARD_HISTORY_PREFIX = "rewards:history:"
PLAN_MULTIPLIER = {
    ServicePlanTier.LAUNCH: 1.0,
    ServicePlanTier.GROWTH: 1.15,
    ServicePlanTier.ENTERPRISE: 1.3,
}

P2P_ONLY_REWARD_FACTOR = 0.6
DEFAULT_DISTRIBUTION_MINUTE = 5


def get_next_distribution_at(
    now: datetime | None = None,
    run_at_hour: int | None = None,
    run_at_minute: int | None = None,
) -> datetime:
    """Return the next scheduled reward distribution timestamp in UTC."""

    current = now or datetime.utcnow()
    settings = get_settings()
    target = current.replace(
        hour=run_at_hour if run_at_hour is not None else settings.reward_distribution_hour_utc,
        minute=run_at_minute if run_at_minute is not None else DEFAULT_DISTRIBUTION_MINUTE,
        second=0,
        microsecond=0,
    )
    if target <= current:
        target = target + timedelta(days=1)
    return target


async def distribute_daily_rewards(date: datetime | None = None) -> dict[str, float]:
    redis = await get_redis()
    snapshot_date = (date or datetime.utcnow()).date()
    date_key = f"{REWARD_PREFIX}{snapshot_date.isoformat()}"

    total_pool_raw = await redis.get("pool:balance")
    total_pool = float(total_pool_raw or 0)
    if total_pool <= 0:
        return {}

    node_ids = await redis.smembers("node:index")
    active_nodes: list[tuple[str, float, str]] = []
    for node_id in node_ids:
        stats = await redis.hgetall(f"uptime:{node_id}")
        score = float(stats.get("uptime_score", 0))
        if score < 0.9:
            continue
        node = await redis.hgetall(f"node:{node_id}")
        if not node:
            continue
        rpc_responding = bool(int(stats.get("rpc_responding", "0") or 0))
        p2p_online = bool(int(stats.get("p2p_online", "0") or 0))
        if not p2p_online:
            continue
        org_id = node.get("organization_id") or ""
        plan_value = await redis.hget(f"org:{org_id}", "plan") or ServicePlanTier.LAUNCH.value
        try:
            plan_enum = ServicePlanTier(plan_value)
        except ValueError:
            plan_enum = ServicePlanTier.LAUNCH
        multiplier = PLAN_MULTIPLIER.get(plan_enum, 1.0)
        interface_multiplier = 1.0 if rpc_responding else P2P_ONLY_REWARD_FACTOR
        weight = score * multiplier * interface_multiplier
        active_nodes.append((node_id, weight, org_id))

    if not active_nodes:
        return {}

    total_weight = sum(weight for _, weight, _ in active_nodes)
    if total_weight == 0:
        return {}

    rewards: dict[str, float] = {}
    org_rewards: dict[str, float] = {}
    for node_id, weight, org_id in active_nodes:
        share = (weight / total_weight) * total_pool
        rewards[node_id] = round(share, 8)
        org_rewards[org_id] = org_rewards.get(org_id, 0.0) + share

    if rewards:
        await redis.hset(date_key, mapping={node_id: str(amount) for node_id, amount in rewards.items()})
        await redis.set("pool:balance", 0)
        for node_id, amount in rewards.items():
            node = await redis.hgetall(f"node:{node_id}")
            org_id = node.get("organization_id", "")
            ledger_key = f"node:{node_id}:rewards"
            await redis.hincrbyfloat(ledger_key, "pending", amount)
            await redis.hincrbyfloat(ledger_key, "lifetime", amount)
            await redis.hset(
                ledger_key,
                mapping={
                    "last_share": str(amount),
                    "last_rewarded_at": snapshot_date.isoformat(),
                },
            )
            await redis.lpush(
                f"{REWARD_HISTORY_PREFIX}{org_id}",
                f"{snapshot_date.isoformat()}:{amount}:{node_id}",
            )
        for org_id, total_amount in org_rewards.items():
            await redis.hincrbyfloat(f"org:{org_id}:rewards", "lifetime", total_amount)
            await redis.hset(f"org:{org_id}:rewards", mapping={"last_payout": snapshot_date.isoformat()})
    return rewards


class RewardDistributor:
    """Background job that triggers a distribution once every 24 hours."""

    def __init__(self, run_at_hour: int | None = None, run_at_minute: int = DEFAULT_DISTRIBUTION_MINUTE) -> None:
        settings = get_settings()
        self._run_at_hour = run_at_hour if run_at_hour is not None else settings.reward_distribution_hour_utc
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
        next_run = get_next_distribution_at(run_at_hour=self._run_at_hour, run_at_minute=self._run_at_minute)
        return (next_run - datetime.utcnow()).total_seconds()
