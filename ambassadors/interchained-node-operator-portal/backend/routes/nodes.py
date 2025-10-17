"""Node registration and management endpoints."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status

from .. import auth
from ..models import NodeRegistration, NodeStatus, NodeUpdate, UserPublic
from ..utils.redis_client import get_redis

router = APIRouter(prefix="/nodes", tags=["nodes"])


@router.post("/register", response_model=NodeStatus, status_code=status.HTTP_201_CREATED)
async def register_node(payload: NodeRegistration, current_user: UserPublic = Depends(auth.get_current_user)) -> NodeStatus:
    if payload.email != current_user.email:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Email mismatch")

    redis = await get_redis()
    node_key = f"node:{payload.email}"
    await redis.hset(
        node_key,
        mapping={
            "email": payload.email,
            "p2p_address": payload.p2p_address,
            "rpc_url": str(payload.rpc_url),
            "wallet_address": payload.wallet_address,
            "created_at": datetime.utcnow().isoformat(),
        },
    )
    return await _build_node_status(payload.email)


@router.patch("/me", response_model=NodeStatus)
async def update_node(payload: NodeUpdate, current_user: UserPublic = Depends(auth.get_current_user)) -> NodeStatus:
    redis = await get_redis()
    node_key = f"node:{current_user.email}"
    exists = await redis.exists(node_key)
    if not exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not registered")

    updates = {k: v for k, v in payload.model_dump(exclude_none=True).items()}
    if updates:
        await redis.hset(node_key, mapping=updates)
    return await _build_node_status(current_user.email)


@router.get("/me", response_model=NodeStatus)
async def get_node(current_user: UserPublic = Depends(auth.get_current_user)) -> NodeStatus:
    return await _build_node_status(current_user.email)


async def _build_node_status(email: str) -> NodeStatus:
    redis = await get_redis()
    node = await redis.hgetall(f"node:{email}")
    if not node:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not registered")

    stats = await redis.hgetall(f"uptime:{email}")
    latency_raw = float(stats.get("latency_ms", 0)) if stats.get("latency_ms") else None
    if latency_raw is not None and latency_raw < 0:
        latency_raw = None

    return NodeStatus(
        email=email,
        p2p_address=node.get("p2p_address", ""),
        rpc_url=node.get("rpc_url", ""),
        wallet_address=node.get("wallet_address", ""),
        last_seen=datetime.fromisoformat(stats["last_seen"]) if stats.get("last_seen") else None,
        uptime_score=float(stats.get("uptime_score", 0.0)),
        total_checks=int(stats.get("total_checks", 0)),
        successful_checks=int(stats.get("successful_checks", 0)),
        latency_ms=latency_raw,
        block_height=int(stats.get("block_height", 0)) if stats.get("block_height") else None,
    )
