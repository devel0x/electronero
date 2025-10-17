"""FastAPI application for the Node Operator Rewards Portal."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import List

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .dependencies import get_current_user, require_admin_user
from .models import (
    AdminNodeDetail,
    AuthenticatedUser,
    DashboardSummary,
    NodeCreate,
    NodeRead,
    NodeStatus,
    NodeUpdate,
    NodeWithMetrics,
    PoolAdjustment,
    PoolDailyUpdate,
    PoolState,
    RewardPreview,
    PayoutExportRow,
    TokenResponse,
    UptimeScore,
    UserCreate,
    UserRead,
)
from .security import create_access_token, hash_password, verify_password
from .services import HealthMonitor, RewardEngine
from .storage import RedisRepository

app = FastAPI(title="Interchained Rewards Portal", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

repo = RedisRepository()
health_monitor = HealthMonitor(repo)
reward_engine = RewardEngine(repo)


@app.on_event("startup")
async def startup_event() -> None:
    settings = get_settings()
    await repo.ensure_pool_defaults(settings.reward_pool_daily, settings.initial_pool_balance)
    await health_monitor.start()
    await reward_engine.start()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await health_monitor.stop()
    await reward_engine.stop()
    await repo.close()


@app.post("/auth/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register_user(payload: UserCreate) -> UserRead:
    existing = await repo.get_user_by_email(payload.email)
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    settings = get_settings()
    is_admin = payload.email.lower() in settings.admin_emails
    user_id = await repo.create_user(payload.email, hash_password(payload.password), is_admin=is_admin)
    return UserRead(id=user_id, email=payload.email.lower())


@app.post("/auth/login", response_model=TokenResponse)
async def login_user(payload: UserCreate) -> TokenResponse:
    stored = await repo.get_user_by_email(payload.email)
    if not stored or not verify_password(payload.password, stored.get("password", "")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    settings = get_settings()
    user_id = stored.get("id", stored.get("email"))
    email = stored.get("email", payload.email).lower()
    is_admin = stored.get("role") == "admin" or email in settings.admin_emails
    if is_admin and stored.get("role") != "admin":
        await repo.set_user_role(str(user_id), "admin")
    token = create_access_token(
        user_id,
        {"email": email, "is_admin": is_admin},
    )
    return TokenResponse(access_token=token)


@app.get("/nodes", response_model=List[NodeWithMetrics])
async def list_nodes(current_user: AuthenticatedUser = Depends(get_current_user)) -> List[NodeWithMetrics]:
    nodes = await repo.get_nodes_for_owner(current_user.id)
    results: List[NodeWithMetrics] = []
    for node in nodes:
        uptime = await repo.get_uptime(node.id)
        last_health = await repo.get_latest_health(node.id)
        results.append(
            NodeWithMetrics(
                **node.dict(),
                uptime=uptime
                or UptimeScore(node_id=node.id, uptime_ratio=0.0, total_checks=0, successful_checks=0, average_latency_ms=None),
                last_health=last_health,
            )
        )
    return results


@app.post("/nodes", response_model=NodeRead, status_code=status.HTTP_201_CREATED)
async def create_node(payload: NodeCreate, current_user: AuthenticatedUser = Depends(get_current_user)) -> NodeRead:
    now = datetime.now(timezone.utc)
    node_data = {
        "name": payload.name,
        "p2p_host": str(payload.p2p_host),
        "p2p_port": str(payload.p2p_port),
        "rpc_host": str(payload.rpc_host),
        "rpc_port": str(payload.rpc_port),
        "wallet_address": payload.wallet_address,
        "created_at": now.isoformat(),
        "flagged": "false",
        "status": NodeStatus.APPROVED.value,
    }
    node_id = await repo.create_node(current_user.id, node_data)
    return NodeRead(
        id=node_id,
        owner_id=current_user.id,
        name=payload.name,
        p2p_host=str(payload.p2p_host),
        p2p_port=payload.p2p_port,
        rpc_host=str(payload.rpc_host),
        rpc_port=payload.rpc_port,
        wallet_address=payload.wallet_address,
        created_at=now,
        flagged=False,
        status=NodeStatus.APPROVED,
    )


@app.put("/nodes/{node_id}", response_model=NodeRead)
async def update_node(node_id: str, payload: NodeUpdate, current_user: AuthenticatedUser = Depends(get_current_user)) -> NodeRead:
    node = await repo.get_node(node_id)
    if not node or node.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")
    updates = {k: str(v) if v is not None else None for k, v in payload.dict(exclude_unset=True).items()}
    updates = {k: v for k, v in updates.items() if v is not None}
    if updates:
        await repo.update_node(node_id, updates)
    refreshed = await repo.get_node(node_id)
    if not refreshed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node missing after update")
    return refreshed


@app.delete("/nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_node(node_id: str, current_user: AuthenticatedUser = Depends(get_current_user)) -> None:
    node = await repo.get_node(node_id)
    if not node or node.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")
    await repo.delete_node(node_id)


@app.get("/dashboard", response_model=DashboardSummary)
async def get_dashboard(current_user: AuthenticatedUser = Depends(get_current_user)) -> DashboardSummary:
    nodes = await repo.get_nodes_for_owner(current_user.id)
    active = 0
    flagged = 0
    for node in nodes:
        uptime = await repo.get_uptime(node.id)
        if uptime and uptime.total_checks:
            if uptime.uptime_ratio > 0.9:
                active += 1
        if node.flagged:
            flagged += 1
    settings = get_settings()
    last_distribution = await repo.get_last_distribution()
    daily_distribution = await repo.get_pool_daily_amount(settings.reward_pool_daily)
    return DashboardSummary(
        total_nodes=len(nodes),
        active_nodes=active,
        reward_pool_daily=daily_distribution,
        last_distribution=last_distribution,
        flagged_nodes=flagged,
    )


@app.get("/rewards", response_model=List[RewardPreview])
async def get_reward_preview(current_user: AuthenticatedUser = Depends(get_current_user)) -> List[RewardPreview]:
    nodes = await repo.get_nodes_for_owner(current_user.id)
    settings = get_settings()
    daily_pool = await repo.get_pool_daily_amount(settings.reward_pool_daily)
    previews: List[RewardPreview] = []
    for node in nodes:
        uptime = await repo.get_uptime(node.id)
        if not uptime or uptime.total_checks == 0:
            uptime = UptimeScore(node_id=node.id, uptime_ratio=0.0, total_checks=0, successful_checks=0, average_latency_ms=None)
            projected = 0.0
        else:
            score = uptime.uptime_ratio * (1.0 if uptime.average_latency_ms is None else max(0.1, 1.5 - (uptime.average_latency_ms / 1500)))
            projected = score * daily_pool
        if node.status == NodeStatus.REJECTED:
            projected = 0.0
        previews.append(RewardPreview(node=node, uptime=uptime, projected_reward=round(projected, 8)))
    return previews


@app.get("/admin/pool", response_model=PoolState)
async def get_pool_state(_: AuthenticatedUser = Depends(require_admin_user)) -> PoolState:
    return await _build_pool_state()


@app.post("/admin/pool/adjust", response_model=PoolState)
async def adjust_pool_balance(
    payload: PoolAdjustment,
    _: AuthenticatedUser = Depends(require_admin_user),
) -> PoolState:
    await repo.adjust_pool_balance(payload.amount)
    return await _build_pool_state()


@app.put("/admin/pool/daily", response_model=PoolState)
async def update_pool_daily(
    payload: PoolDailyUpdate,
    _: AuthenticatedUser = Depends(require_admin_user),
) -> PoolState:
    await repo.set_pool_daily_amount(payload.daily_distribution)
    return await _build_pool_state()


@app.get("/admin/nodes", response_model=List[AdminNodeDetail])
async def get_admin_nodes(_: AuthenticatedUser = Depends(require_admin_user)) -> List[AdminNodeDetail]:
    nodes = await repo.get_all_nodes()
    results: List[AdminNodeDetail] = []
    for node in nodes:
        uptime = await repo.get_uptime(node.id)
        if not uptime:
            uptime = UptimeScore(
                node_id=node.id,
                uptime_ratio=0.0,
                total_checks=0,
                successful_checks=0,
                average_latency_ms=None,
            )
        last_health = await repo.get_latest_health(node.id)
        owner = await repo.get_user_by_id(node.owner_id)
        owner_email = owner.get("email", "unknown") if owner else "unknown"
        results.append(
            AdminNodeDetail(
                node=NodeWithMetrics(**node.dict(), uptime=uptime, last_health=last_health),
                owner_email=owner_email,
            )
        )
    return results


@app.post("/admin/nodes/{node_id}/reject", response_model=AdminNodeDetail)
async def reject_node(node_id: str, _: AuthenticatedUser = Depends(require_admin_user)) -> AdminNodeDetail:
    node = await repo.get_node(node_id)
    if not node:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")
    await repo.update_node(node_id, {"status": NodeStatus.REJECTED.value})
    return await _admin_node_detail(node_id)


@app.post("/admin/nodes/{node_id}/reinstate", response_model=AdminNodeDetail)
async def reinstate_node(node_id: str, _: AuthenticatedUser = Depends(require_admin_user)) -> AdminNodeDetail:
    node = await repo.get_node(node_id)
    if not node:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")
    await repo.update_node(node_id, {"status": NodeStatus.APPROVED.value})
    return await _admin_node_detail(node_id)


@app.get("/admin/exports/payouts", response_model=List[PayoutExportRow])
async def export_payouts(_: AuthenticatedUser = Depends(require_admin_user)) -> List[PayoutExportRow]:
    projections = await reward_engine.calculate_reward_shares()
    rows: List[PayoutExportRow] = []
    for record in projections:
        owner = await repo.get_user_by_id(record.owner_id)
        owner_email = owner.get("email", "unknown") if owner else "unknown"
        node = await repo.get_node(record.node_id)
        if not node:
            continue
        rows.append(
            PayoutExportRow(
                node_id=record.node_id,
                node_name=node.name,
                owner_email=owner_email,
                wallet_address=node.wallet_address,
                projected_reward=record.amount,
            )
        )
    return rows


async def _build_pool_state() -> PoolState:
    settings = get_settings()
    state = await repo.get_pool_state(settings.reward_pool_daily)
    nodes = await repo.get_all_nodes()
    active = sum(1 for node in nodes if node.status == NodeStatus.APPROVED)
    rejected = sum(1 for node in nodes if node.status == NodeStatus.REJECTED)
    return PoolState(
        current_balance=state["current_balance"],
        daily_distribution=state["daily_distribution"],
        last_distribution=state["last_distribution"],
        total_nodes=len(nodes),
        active_nodes=active,
        rejected_nodes=rejected,
    )


async def _admin_node_detail(node_id: str) -> AdminNodeDetail:
    refreshed = await repo.get_node(node_id)
    if not refreshed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")
    uptime = await repo.get_uptime(node_id)
    if not uptime:
        uptime = UptimeScore(
            node_id=node_id,
            uptime_ratio=0.0,
            total_checks=0,
            successful_checks=0,
            average_latency_ms=None,
        )
    last_health = await repo.get_latest_health(node_id)
    owner = await repo.get_user_by_id(refreshed.owner_id)
    owner_email = owner.get("email", "unknown") if owner else "unknown"
    return AdminNodeDetail(
        node=NodeWithMetrics(**refreshed.dict(), uptime=uptime, last_health=last_health),
        owner_email=owner_email,
    )
