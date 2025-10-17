"""Reward data endpoints."""
from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends

from .. import auth
from ..models import RewardHistory, RewardHistoryItem, RewardSummary, UserPublic
from ..rewards import distribute_daily_rewards
from ..utils.redis_client import get_redis

router = APIRouter(prefix="/rewards", tags=["rewards"])


@router.post("/run", response_model=RewardSummary)
async def trigger_rewards(_: UserPublic = Depends(auth.get_current_user)) -> RewardSummary:
    rewards = await distribute_daily_rewards()
    snapshot = datetime.utcnow()
    redis = await get_redis()
    pool_balance = float(await redis.get("pool:balance") or 0)
    return RewardSummary(date=snapshot, rewards=rewards, pool_balance=pool_balance)


@router.get("/today", response_model=RewardSummary)
async def rewards_today(_: UserPublic = Depends(auth.get_current_user)) -> RewardSummary:
    today = date.today().isoformat()
    redis = await get_redis()
    rewards = await redis.hgetall(f"rewards:{today}")
    rewards_float = {email: float(amount) for email, amount in rewards.items()}
    pool_balance = float(await redis.get("pool:balance") or 0)
    return RewardSummary(date=datetime.utcnow(), rewards=rewards_float, pool_balance=pool_balance)


@router.get("/history", response_model=RewardHistory)
async def reward_history(current_user: UserPublic = Depends(auth.get_current_user)) -> RewardHistory:
    redis = await get_redis()
    entries = await redis.lrange(f"rewards:history:{current_user.email}", 0, 30)
    history: list[RewardHistoryItem] = []
    for entry in entries:
        try:
            date_str, amount_str = entry.split(":", 1)
            history.append(
                RewardHistoryItem(date=datetime.fromisoformat(date_str), amount=float(amount_str))
            )
        except ValueError:
            continue
    return RewardHistory(email=current_user.email, history=list(reversed(history)))
