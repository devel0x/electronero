"""Reward data endpoints."""
from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends

from .. import auth
from ..dependencies import require_org_admin, require_super_admin
from ..models import RewardHistory, RewardHistoryItem, RewardSummary, UserPublic, UserRole
from ..rewards import distribute_daily_rewards
from ..utils.redis_client import get_redis

router = APIRouter(prefix="/rewards", tags=["rewards"])


@router.post("/run", response_model=RewardSummary)
async def trigger_rewards(_: UserPublic = Depends(require_super_admin())) -> RewardSummary:
    rewards = await distribute_daily_rewards()
    snapshot = datetime.utcnow()
    redis = await get_redis()
    pool_balance = float(await redis.get("pool:balance") or 0)
    return RewardSummary(date=snapshot, rewards=rewards, pool_balance=pool_balance)


@router.get("/today", response_model=RewardSummary)
async def rewards_today(current_user: UserPublic = Depends(auth.get_current_user)) -> RewardSummary:
    today = date.today().isoformat()
    redis = await get_redis()
    rewards = await redis.hgetall(f"rewards:{today}")
    rewards_float: dict[str, float] = {}
    for node_id, amount in rewards.items():
        if current_user.role != UserRole.SUPER_ADMIN:
            node = await redis.hgetall(f"node:{node_id}")
            if node.get("organization_id") != current_user.organization_id:
                continue
        rewards_float[node_id] = float(amount)
    pool_balance = float(await redis.get("pool:balance") or 0)
    return RewardSummary(date=datetime.utcnow(), rewards=rewards_float, pool_balance=pool_balance)


@router.get("/history", response_model=RewardHistory)
async def reward_history(current_user: UserPublic = Depends(require_org_admin())) -> RewardHistory:
    redis = await get_redis()
    entries = await redis.lrange(f"rewards:history:{current_user.organization_id}", 0, 50)
    history: list[RewardHistoryItem] = []
    for entry in entries:
        try:
            date_str, amount_str, node_id = entry.split(":", 2)
            history.append(
                RewardHistoryItem(date=datetime.fromisoformat(date_str), amount=float(amount_str), node_id=node_id)
            )
        except ValueError:
            continue
    return RewardHistory(organization_id=current_user.organization_id, history=list(reversed(history)))
