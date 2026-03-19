"""Domain services for monitoring uptime and distributing rewards."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

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
        rpc_online, rpc_latency_ms, height = await self._check_rpc(node)
        p2p_online, p2p_latency_ms = await self._check_p2p(node)
        result = HealthCheckResult(
            node_id=node.id,
            timestamp=datetime.now(timezone.utc),
            online=rpc_online,
            rpc_latency_ms=rpc_latency_ms,
            sync_height=height,
            p2p_online=p2p_online,
            p2p_latency_ms=p2p_latency_ms,
        )
        await self.repo.store_health_result(result)
        uptime = await self.repo.update_uptime(node.id, rpc_online, rpc_latency_ms, p2p_online, p2p_latency_ms)
        await self._update_flag(node, uptime)

    async def _check_rpc(self, node: NodeRead) -> Tuple[bool, Optional[float], Optional[int]]:
        rpc_url = f"http://{node.rpc_host}:{node.rpc_port}/json_rpc"
        loop = asyncio.get_running_loop()
        start = loop.time()
        try:
            async with httpx.AsyncClient(timeout=self.settings.rpc_timeout_seconds) as client:
                response = await client.post(
                    rpc_url,
                    json={"jsonrpc": "2.0", "method": "get_info", "id": "0"},
                )
            if response.status_code != 200:
                return False, None, None
            latency_ms = (loop.time() - start) * 1000
            payload = response.json()
            height = payload.get("result", {}).get("height")
            return True, latency_ms, height
        except httpx.HTTPError:
            return False, None, None

    async def _check_p2p(self, node: NodeRead) -> Tuple[bool, Optional[float]]:
        loop = asyncio.get_running_loop()
        start = loop.time()
        try:
            connect = asyncio.open_connection(node.p2p_host, node.p2p_port)
            _reader, writer = await asyncio.wait_for(connect, timeout=self.settings.p2p_timeout_seconds)
        except (OSError, asyncio.TimeoutError):
            return False, None
        else:
            latency_ms = (loop.time() - start) * 1000
            writer.close()
            with suppress(Exception):
                await writer.wait_closed()
            return True, latency_ms

    async def _update_flag(self, node: NodeRead, uptime: UptimeScore) -> None:
        flag_threshold = 0.98
        flag = (
            uptime.uptime_ratio >= flag_threshold
            and uptime.p2p_uptime_ratio >= flag_threshold
            and (uptime.average_latency_ms or 0) <= 1500
            and (uptime.p2p_average_latency_ms or 0) <= 1500
        )
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

    def score_from_uptime(self, uptime: UptimeScore) -> float:
        if uptime.total_checks == 0 or uptime.p2p_total_checks == 0:
            return 0.0
        reliability = min(uptime.uptime_ratio, uptime.p2p_uptime_ratio)
        if reliability <= 0:
            return 0.0
        rpc_latency_factor = (
            1.0 if uptime.average_latency_ms is None else max(0.1, 1.5 - (uptime.average_latency_ms / 1500))
        )
        p2p_latency_factor = (
            1.0 if uptime.p2p_average_latency_ms is None else max(0.1, 1.5 - (uptime.p2p_average_latency_ms / 1500))
        )
        return max(0.0, reliability * rpc_latency_factor * p2p_latency_factor)

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
            score = self.score_from_uptime(uptime)
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
