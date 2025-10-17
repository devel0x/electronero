"""Domain services for monitoring uptime and distributing rewards."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional

import httpx

from .config import get_settings
from .models import HealthCheckResult, NodeRead, NodeStatus, RewardRecord, UptimeScore
from .storage import RedisRepository


class HealthMonitor:
    """Asynchronous service that periodically probes registered nodes."""

    def __init__(self, repo: RedisRepository) -> None:
        self.repo = repo
        self.settings = get_settings()
        self._task: Optional[asyncio.Task[None]] = None
        self._stopped = asyncio.Event()

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stopped.clear()
        self._task = asyncio.create_task(self._run(), name="health-monitor")

    async def stop(self) -> None:
        self._stopped.set()
        if self._task:
            await self._task

    async def _run(self) -> None:
        interval = self.settings.health_check_interval_seconds
        while not self._stopped.is_set():
            await self._probe_all_nodes()
            try:
                await asyncio.wait_for(self._stopped.wait(), timeout=interval)
            except asyncio.TimeoutError:
                continue

    async def _probe_all_nodes(self) -> None:
        nodes = await self.repo.get_all_nodes()
        if not nodes:
            return
        await asyncio.gather(*(self._probe_node(node) for node in nodes if node.status != NodeStatus.REJECTED))

    async def _probe_node(self, node: NodeRead) -> None:
        latency_ms: Optional[float] = None
        online = False
        rpc_url = f"http://{node.rpc_host}:{node.rpc_port}/json_rpc"
        start = asyncio.get_event_loop().time()
        try:
            async with httpx.AsyncClient(timeout=self.settings.rpc_timeout_seconds) as client:
                response = await client.post(rpc_url, json={"jsonrpc": "2.0", "method": "get_info", "id": "0"})
                if response.status_code == 200:
                    online = True
                    latency_ms = (asyncio.get_event_loop().time() - start) * 1000
                    payload = response.json()
                    height = payload.get("result", {}).get("height")
                else:
                    height = None
        except httpx.HTTPError:
            height = None
        result = HealthCheckResult(
            node_id=node.id,
            timestamp=datetime.now(timezone.utc),
            online=online,
            rpc_latency_ms=latency_ms,
            sync_height=height,
        )
        await self.repo.store_health_result(result)
        uptime = await self.repo.update_uptime(node.id, online, latency_ms)
        await self._update_flag(node, uptime)

    async def _update_flag(self, node: NodeRead, uptime: UptimeScore) -> None:
        flag_threshold = 0.98
        flag = uptime.uptime_ratio >= flag_threshold and (uptime.average_latency_ms or 0) <= 1500
        await self.repo.update_node(node.id, {"flagged": "true" if flag else "false"})


class RewardEngine:
    """Service that calculates and records node rewards."""

    def __init__(self, repo: RedisRepository) -> None:
        self.repo = repo
        self.settings = get_settings()
        self._task: Optional[asyncio.Task[None]] = None
        self._stop = asyncio.Event()

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="reward-engine")

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            await self._task

    async def _run(self) -> None:
        interval = self.settings.reward_distribution_interval_seconds
        while not self._stop.is_set():
            await self.distribute_rewards()
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=interval)
            except asyncio.TimeoutError:
                continue

    async def distribute_rewards(self) -> List[RewardRecord]:
        records = await self.calculate_reward_shares()
        if not records:
            return []
        total_payout = sum(record.amount for record in records)
        await asyncio.gather(
            *(self.repo.record_reward(record.dict()) for record in records),
        )
        if total_payout:
            await self.repo.adjust_pool_balance(-total_payout)
        await self.repo.set_last_distribution(datetime.now(timezone.utc))
        return records

    async def calculate_reward_shares(self) -> List[RewardRecord]:
        nodes = await self.repo.get_all_nodes()
        if not nodes:
            return []
        daily_pool = await self.repo.get_pool_daily_amount(self.settings.reward_pool_daily)
        pool_balance = await self.repo.get_pool_balance()
        available_pool = min(daily_pool, pool_balance) if pool_balance > 0 else 0.0
        scores: Dict[str, float] = {}
        uptimes: Dict[str, UptimeScore] = {}
        total_score = 0.0
        for node in nodes:
            if node.status == NodeStatus.REJECTED:
                continue
            uptime = await self.repo.get_uptime(node.id)
            if not uptime or uptime.total_checks == 0:
                continue
            score = uptime.uptime_ratio * (
                1.0 if uptime.average_latency_ms is None else max(0.1, 1.5 - (uptime.average_latency_ms / 1500))
            )
            if score <= 0:
                continue
            uptimes[node.id] = uptime
            scores[node.id] = score
            total_score += score
        if total_score == 0 or available_pool <= 0:
            return []
        records: List[RewardRecord] = []
        for node in nodes:
            score = scores.get(node.id)
            if not score:
                continue
            uptime = uptimes[node.id]
            share = (score / total_score) * available_pool
            record = RewardRecord(
                node_id=node.id,
                owner_id=node.owner_id,
                amount=round(share, 8),
                total_score=score,
                timestamp=datetime.now(timezone.utc),
            )
            records.append(record)
        return records
