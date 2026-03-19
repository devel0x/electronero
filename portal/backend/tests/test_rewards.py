from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Dict

import pytest

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services import RewardEngine
from app.storage import RedisRepository
from app.models import UptimeScore, NodeRead


pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def test_reward_distribution(monkeypatch):
    monkeypatch.setenv("PORTAL_SECRET_KEY", "x" * 32)
    repo = RedisRepository()

    async def fake_get_all_nodes():
        return [
            NodeRead(
                id="1",
                owner_id="u1",
                name="Node 1",
                p2p_host="127.0.0.1",
                p2p_port=18080,
                rpc_host="127.0.0.1",
                rpc_port=18081,
                wallet_address="wallet1",
                created_at=datetime.now(timezone.utc),
                flagged=False,
            ),
            NodeRead(
                id="2",
                owner_id="u2",
                name="Node 2",
                p2p_host="127.0.0.1",
                p2p_port=28080,
                rpc_host="127.0.0.1",
                rpc_port=28081,
                wallet_address="wallet2",
                created_at=datetime.now(timezone.utc),
                flagged=True,
            ),
        ]

    uptimes: Dict[str, UptimeScore] = {
        "1": UptimeScore(node_id="1", uptime_ratio=0.99, total_checks=100, successful_checks=99, average_latency_ms=450.0),
        "2": UptimeScore(node_id="2", uptime_ratio=0.75, total_checks=100, successful_checks=75, average_latency_ms=900.0),
    }

    async def fake_get_uptime(node_id: str):
        return uptimes.get(node_id)

    recorded = []

    async def fake_record_reward(record):
        recorded.append(record)

    async def fake_set_last_distribution(timestamp):
        pass

    monkeypatch.setattr(repo, "get_all_nodes", fake_get_all_nodes)
    monkeypatch.setattr(repo, "get_uptime", fake_get_uptime)
    monkeypatch.setattr(repo, "record_reward", fake_record_reward)
    monkeypatch.setattr(repo, "set_last_distribution", fake_set_last_distribution)

    engine = RewardEngine(repo)
    results = await engine.distribute_rewards()

    assert len(results) == 2
    assert sum(r.amount for r in results) == pytest.approx(engine.settings.reward_pool_daily, rel=1e-6)
    assert recorded, "Rewards should be recorded in Redis"

    await repo.close()
