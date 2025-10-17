"""Reward data endpoints."""
from __future__ import annotations

import csv
from datetime import date, datetime
from io import StringIO

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from .. import auth
from ..dependencies import require_org_admin, require_super_admin
from ..models import (
    PoolBalance,
    PoolTopUpRequest,
    RewardHistory,
    RewardHistoryItem,
    RewardSummary,
    UserPublic,
    UserRole,
)
from ..rewards import distribute_daily_rewards, get_next_distribution_at
from ..services.audit import record_audit_event
from ..utils.redis_client import get_redis


def _as_float(value: str | None) -> float:
    try:
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0

router = APIRouter(prefix="/rewards", tags=["rewards"])


@router.post("/run", response_model=RewardSummary)
async def trigger_rewards(_: UserPublic = Depends(require_super_admin())) -> RewardSummary:
    snapshot = datetime.utcnow()
    rewards = await distribute_daily_rewards(snapshot)
    redis = await get_redis()
    pool_balance = float(await redis.get("pool:balance") or 0)
    next_payout_at = get_next_distribution_at(now=snapshot)
    return RewardSummary(
        date=snapshot,
        rewards=rewards,
        pool_balance=pool_balance,
        next_payout_at=next_payout_at,
    )


@router.post("/pool/top-up", response_model=PoolBalance)
async def top_up_reward_pool(
    payload: PoolTopUpRequest,
    current_user: UserPublic = Depends(require_super_admin()),
) -> PoolBalance:
    redis = await get_redis()
    new_balance = await redis.incrbyfloat("pool:balance", payload.amount)
    await record_audit_event(
        actor_email=current_user.email,
        action="rewards.pool.top_up",
        metadata={"amount": f"{payload.amount:.8f}", "balance": f"{new_balance:.8f}"},
    )
    return PoolBalance(balance=float(new_balance))


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
    snapshot = datetime.utcnow()
    next_payout_at = get_next_distribution_at(now=snapshot)
    return RewardSummary(
        date=snapshot,
        rewards=rewards_float,
        pool_balance=pool_balance,
        next_payout_at=next_payout_at,
    )


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


@router.get("/export", response_class=StreamingResponse)
async def export_rewards_csv(
    report_date: date | None = Query(default=None, alias="date"),
    organization_id: str | None = Query(default=None, alias="organizationId"),
    current_user: UserPublic = Depends(require_org_admin()),
) -> StreamingResponse:
    if organization_id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Cannot export other organizations")

    target_date = report_date or date.today()
    redis = await get_redis()
    rewards_key = f"rewards:{target_date.isoformat()}"
    reward_map = await redis.hgetall(rewards_key)

    node_ids: set[str] = set(reward_map.keys())
    if organization_id:
        node_ids.update(await redis.smembers(f"org:{organization_id}:nodes"))
    elif current_user.role == UserRole.SUPER_ADMIN:
        node_ids.update(await redis.smembers("node:index"))
    else:
        organization_id = current_user.organization_id
        node_ids.update(await redis.smembers(f"org:{organization_id}:nodes"))

    rows: list[dict[str, str]] = []
    org_cache: dict[str, dict[str, str]] = {}

    for node_id in sorted(node_ids):
        node = await redis.hgetall(f"node:{node_id}")
        if not node:
            continue
        org_id = node.get("organization_id") or ""
        if current_user.role != UserRole.SUPER_ADMIN and org_id != current_user.organization_id:
            continue
        if organization_id and org_id != organization_id:
            continue

        ledger = await redis.hgetall(f"node:{node_id}:rewards")
        org_data = org_cache.get(org_id)
        if org_data is None:
            org_data = await redis.hgetall(f"org:{org_id}") if org_id else {}
            org_cache[org_id] = org_data

        rows.append(
            {
                "organization_id": org_id,
                "organization_name": org_data.get("name", ""),
                "node_id": node_id,
                "node_name": node.get("name", ""),
                "wallet_address": node.get("wallet_address", ""),
                "owner_email": node.get("owner_email", ""),
                "today_share": f"{_as_float(reward_map.get(node_id)):.8f}",
                "pending_rewards": f"{_as_float(ledger.get('pending')):.8f}",
                "lifetime_rewards": f"{_as_float(ledger.get('lifetime')):.8f}",
                "last_rewarded_at": ledger.get("last_rewarded_at", ""),
            }
        )

    output = StringIO()
    fieldnames = [
        "organization_id",
        "organization_name",
        "node_id",
        "node_name",
        "wallet_address",
        "owner_email",
        "today_share",
        "pending_rewards",
        "lifetime_rewards",
        "last_rewarded_at",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

    filename = f"reward-export-{target_date.isoformat()}"
    if organization_id:
        filename += f"-{organization_id}"
    output.seek(0)
    csv_bytes = output.getvalue().encode("utf-8")
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}.csv"',
    }
    return StreamingResponse(iter([csv_bytes]), media_type="text/csv", headers=headers)
