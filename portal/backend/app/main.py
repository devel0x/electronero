"""FastAPI application for the Node Operator Rewards Portal."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import List

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .dependencies import get_current_user_id
from .models import (
    DashboardSummary,
    NodeCreate,
    NodeRead,
    NodeUpdate,
    NodeWithMetrics,
    RewardPreview,
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
    user_id = await repo.create_user(payload.email, hash_password(payload.password))
    return UserRead(id=user_id, email=payload.email.lower())


@app.post("/auth/login", response_model=TokenResponse)
async def login_user(payload: UserCreate) -> TokenResponse:
    stored = await repo.get_user_by_email(payload.email)
    if not stored or not verify_password(payload.password, stored.get("password", "")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(stored.get("id", stored.get("email")))
    return TokenResponse(access_token=token)


@app.get("/nodes", response_model=List[NodeWithMetrics])
async def list_nodes(user_id: str = Depends(get_current_user_id)) -> List[NodeWithMetrics]:
    nodes = await repo.get_nodes_for_owner(user_id)
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
async def create_node(payload: NodeCreate, user_id: str = Depends(get_current_user_id)) -> NodeRead:
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
    }
    node_id = await repo.create_node(user_id, node_data)
    return NodeRead(
        id=node_id,
        owner_id=user_id,
        name=payload.name,
        p2p_host=str(payload.p2p_host),
        p2p_port=payload.p2p_port,
        rpc_host=str(payload.rpc_host),
        rpc_port=payload.rpc_port,
        wallet_address=payload.wallet_address,
        created_at=now,
        flagged=False,
    )


@app.put("/nodes/{node_id}", response_model=NodeRead)
async def update_node(node_id: str, payload: NodeUpdate, user_id: str = Depends(get_current_user_id)) -> NodeRead:
    node = await repo.get_node(node_id)
    if not node or node.owner_id != user_id:
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
async def delete_node(node_id: str, user_id: str = Depends(get_current_user_id)) -> None:
    node = await repo.get_node(node_id)
    if not node or node.owner_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")
    await repo.delete_node(node_id)


@app.get("/dashboard", response_model=DashboardSummary)
async def get_dashboard(user_id: str = Depends(get_current_user_id)) -> DashboardSummary:
    nodes = await repo.get_nodes_for_owner(user_id)
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
    return DashboardSummary(
        total_nodes=len(nodes),
        active_nodes=active,
        reward_pool_daily=settings.reward_pool_daily,
        last_distribution=last_distribution,
        flagged_nodes=flagged,
    )


@app.get("/rewards", response_model=List[RewardPreview])
async def get_reward_preview(user_id: str = Depends(get_current_user_id)) -> List[RewardPreview]:
    nodes = await repo.get_nodes_for_owner(user_id)
    settings = get_settings()
    previews: List[RewardPreview] = []
    for node in nodes:
        uptime = await repo.get_uptime(node.id)
        if not uptime or uptime.total_checks == 0:
            uptime = UptimeScore(node_id=node.id, uptime_ratio=0.0, total_checks=0, successful_checks=0, average_latency_ms=None)
            projected = 0.0
        else:
            score = uptime.uptime_ratio * (1.0 if uptime.average_latency_ms is None else max(0.1, 1.5 - (uptime.average_latency_ms / 1500)))
            projected = score * settings.reward_pool_daily
        previews.append(RewardPreview(node=node, uptime=uptime, projected_reward=round(projected, 8)))
    return previews
