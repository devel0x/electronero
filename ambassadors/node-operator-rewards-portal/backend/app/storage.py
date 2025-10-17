"""Redis-based persistence helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, List, Optional

import redis.asyncio as redis

from .config import get_redis_url
from .models import (
    HealthCheckResult,
    NodeRead,
    NodeStatus,
    UptimeScore,
)


@dataclass
class RedisKeys:
    users: str = "portal:users"
    nodes: str = "portal:nodes"
    node_owner_index: str = "portal:node_owners"
    node_health: str = "portal:node:health"
    node_uptime: str = "portal:node:uptime"
    rewards: str = "portal:rewards"
    last_distribution: str = "portal:last_distribution"
    pool_balance: str = "portal:pool:balance"
    pool_daily: str = "portal:pool:daily"


class RedisRepository:
    """Abstraction over Redis access patterns used by the backend."""

    def __init__(self) -> None:
        self.client = redis.from_url(get_redis_url(), decode_responses=True)
        self.keys = RedisKeys()

    async def close(self) -> None:
        await self.client.aclose()

    # User management -----------------------------------------------------
    async def create_user(self, email: str, password_hash: str, *, is_admin: bool = False) -> str:
        user_id = await self.client.incr("portal:ids:users")
        user_key = f"portal:user:{user_id}"
        await self.client.hset(
            user_key,
            mapping={
                "id": str(user_id),
                "email": email.lower(),
                "password": password_hash,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "role": "admin" if is_admin else "operator",
            },
        )
        await self.client.hset(self.keys.users, email.lower(), user_key)
        return str(user_id)

    async def get_user_by_email(self, email: str) -> Optional[dict]:
        user_key = await self.client.hget(self.keys.users, email.lower())
        if not user_key:
            return None
        return await self.client.hgetall(user_key)

    async def get_user_by_id(self, user_id: str) -> Optional[dict]:
        user_key = f"portal:user:{user_id}"
        data = await self.client.hgetall(user_key)
        return data or None

    async def set_user_role(self, user_id: str, role: str) -> None:
        user_key = f"portal:user:{user_id}"
        await self.client.hset(user_key, mapping={"role": role})

    # Node management -----------------------------------------------------
    async def create_node(self, owner_id: str, node_data: dict) -> str:
        node_id = await self.client.incr("portal:ids:nodes")
        node_key = f"portal:node:{node_id}"
        node_payload = {
            **node_data,
            "id": str(node_id),
            "owner_id": owner_id,
            "status": node_data.get("status", NodeStatus.APPROVED.value),
        }
        await self.client.hset(node_key, mapping=node_payload)
        await self.client.sadd(f"portal:owner:{owner_id}:nodes", node_key)
        await self.client.hset(self.keys.nodes, node_key, owner_id)
        return str(node_id)

    async def update_node(self, node_id: str, updates: dict) -> None:
        node_key = f"portal:node:{node_id}"
        if updates:
            await self.client.hset(node_key, mapping=updates)

    async def delete_node(self, node_id: str) -> None:
        node_key = f"portal:node:{node_id}"
        owner_id = await self.client.hget(self.keys.nodes, node_key)
        pipeline = self.client.pipeline()
        pipeline.delete(node_key)
        pipeline.hdel(self.keys.nodes, node_key)
        pipeline.delete(f"portal:health:{node_id}")
        pipeline.delete(f"portal:uptime:{node_id}")
        if owner_id:
            pipeline.srem(f"portal:owner:{owner_id}:nodes", node_key)
        await pipeline.execute()

    async def get_nodes_for_owner(self, owner_id: str) -> List[NodeRead]:
        node_keys = await self.client.smembers(f"portal:owner:{owner_id}:nodes")
        nodes: List[NodeRead] = []
        for key in node_keys:
            data = await self.client.hgetall(key)
            if data:
                nodes.append(_deserialize_node(data))
        return nodes

    async def get_all_nodes(self) -> List[NodeRead]:
        node_entries = await self.client.hgetall(self.keys.nodes)
        nodes: List[NodeRead] = []
        for node_key in node_entries.keys():
            data = await self.client.hgetall(node_key)
            if data:
                nodes.append(_deserialize_node(data))
        return nodes

    async def get_node(self, node_id: str) -> Optional[NodeRead]:
        node_key = f"portal:node:{node_id}"
        data = await self.client.hgetall(node_key)
        if not data:
            return None
        return _deserialize_node(data)

    # Health + uptime -----------------------------------------------------
    async def store_health_result(self, result: HealthCheckResult) -> None:
        key = f"portal:health:{result.node_id}"
        await self.client.lpush(key, result.json())
        await self.client.ltrim(key, 0, 499)

    async def get_latest_health(self, node_id: str) -> Optional[HealthCheckResult]:
        key = f"portal:health:{node_id}"
        raw = await self.client.lindex(key, 0)
        if not raw:
            return None
        return HealthCheckResult.parse_raw(raw)

    async def update_uptime(self, node_id: str, online: bool, latency_ms: Optional[float]) -> UptimeScore:
        key = f"portal:uptime:{node_id}"
        data = await self.client.hgetall(key)
        total_checks = int(data.get("total_checks", 0)) + 1
        successful_checks = int(data.get("successful_checks", 0)) + (1 if online else 0)
        cumulative_latency = float(data.get("cumulative_latency", 0.0)) + (latency_ms or 0.0)
        uptime_ratio = successful_checks / total_checks
        average_latency = cumulative_latency / successful_checks if successful_checks else None
        await self.client.hset(
            key,
            mapping={
                "total_checks": total_checks,
                "successful_checks": successful_checks,
                "cumulative_latency": cumulative_latency,
                "uptime_ratio": uptime_ratio,
                "average_latency": average_latency or 0.0,
            },
        )
        return UptimeScore(
            node_id=node_id,
            uptime_ratio=uptime_ratio,
            total_checks=total_checks,
            successful_checks=successful_checks,
            average_latency_ms=average_latency,
        )

    async def get_uptime(self, node_id: str) -> Optional[UptimeScore]:
        key = f"portal:uptime:{node_id}"
        data = await self.client.hgetall(key)
        if not data:
            return None
        avg_latency = float(data.get("average_latency", 0.0)) if data.get("successful_checks") else None
        return UptimeScore(
            node_id=node_id,
            uptime_ratio=float(data.get("uptime_ratio", 0.0)),
            total_checks=int(data.get("total_checks", 0)),
            successful_checks=int(data.get("successful_checks", 0)),
            average_latency_ms=avg_latency,
        )

    # Rewards -------------------------------------------------------------
    async def record_reward(self, record: dict) -> None:
        await self.client.lpush(self.keys.rewards, json.dumps(record))

    async def get_recent_rewards(self, limit: int = 50) -> List[dict]:
        raw = await self.client.lrange(self.keys.rewards, 0, limit - 1)
        return [json.loads(item) for item in raw]

    async def set_last_distribution(self, timestamp: datetime) -> None:
        await self.client.set(self.keys.last_distribution, timestamp.isoformat())

    async def get_last_distribution(self) -> Optional[datetime]:
        raw = await self.client.get(self.keys.last_distribution)
        if not raw:
            return None
        return datetime.fromisoformat(raw)

    # Pool management ----------------------------------------------------
    async def ensure_pool_defaults(self, daily_amount: float, initial_balance: float) -> None:
        await self.client.setnx(self.keys.pool_daily, str(daily_amount))
        await self.client.setnx(self.keys.pool_balance, str(initial_balance))

    async def get_pool_daily_amount(self, fallback: float) -> float:
        raw = await self.client.get(self.keys.pool_daily)
        return float(raw) if raw is not None else fallback

    async def set_pool_daily_amount(self, value: float) -> float:
        await self.client.set(self.keys.pool_daily, str(value))
        return value

    async def get_pool_balance(self) -> float:
        raw = await self.client.get(self.keys.pool_balance)
        return float(raw) if raw is not None else 0.0

    async def set_pool_balance(self, value: float) -> float:
        capped = max(0.0, value)
        await self.client.set(self.keys.pool_balance, str(capped))
        return capped

    async def adjust_pool_balance(self, delta: float) -> float:
        async with self.client.pipeline(transaction=True) as pipe:
            while True:
                try:
                    await pipe.watch(self.keys.pool_balance)
                    raw = await pipe.get(self.keys.pool_balance)
                    current = float(raw) if raw is not None else 0.0
                    new_value = max(0.0, current + delta)
                    pipe.multi()
                    pipe.set(self.keys.pool_balance, str(new_value))
                    await pipe.execute()
                    return new_value
                except redis.WatchError:
                    continue

    async def get_pool_state(self, fallback_daily: float) -> dict:
        balance = await self.get_pool_balance()
        daily = await self.get_pool_daily_amount(fallback_daily)
        last_distribution = await self.get_last_distribution()
        return {
            "current_balance": balance,
            "daily_distribution": daily,
            "last_distribution": last_distribution,
        }


def _deserialize_node(data: dict) -> NodeRead:
    created_at = datetime.fromisoformat(data["created_at"])
    flagged = data.get("flagged", "false") == "true"
    status = NodeStatus(data.get("status", NodeStatus.APPROVED.value))
    return NodeRead(
        id=data["id"],
        owner_id=data["owner_id"],
        name=data["name"],
        p2p_host=data["p2p_host"],
        p2p_port=int(data["p2p_port"]),
        rpc_host=data["rpc_host"],
        rpc_port=int(data["rpc_port"]),
        wallet_address=data["wallet_address"],
        created_at=created_at,
        flagged=flagged,
        status=status,
    )
