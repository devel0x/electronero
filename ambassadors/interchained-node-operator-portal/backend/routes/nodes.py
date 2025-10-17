"""Node management endpoints."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status

from ..dependencies import require_org_admin, require_roles
from ..models import NodeRegistration, NodeStatus, NodeUpdate, UserPublic, UserRole
from ..services.audit import record_audit_event
from ..utils.ids import short_ulid
from ..utils.redis_client import get_redis


router = APIRouter(prefix="/nodes", tags=["nodes"])


NodeWriter = require_roles(UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.OPERATOR)


@router.post("", response_model=NodeStatus, status_code=status.HTTP_201_CREATED)
async def create_node(
    payload: NodeRegistration,
    current_user: UserPublic = Depends(NodeWriter),
) -> NodeStatus:
    organization_id = current_user.organization_id
    owner_email = payload.owner_email or current_user.email
    if current_user.role in {UserRole.OPERATOR, UserRole.AUDITOR} and owner_email != current_user.email:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot assign nodes to other members")

    redis = await get_redis()
    node_id = short_ulid("node")
    now = datetime.utcnow()
    await redis.hset(
        f"node:{node_id}",
        mapping={
            "id": node_id,
            "organization_id": organization_id,
            "name": payload.name,
            "p2p_address": payload.p2p_address,
            "rpc_url": str(payload.rpc_url),
            "wallet_address": payload.wallet_address,
            "owner_email": owner_email,
            "tags": ",".join(payload.tags),
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "is_flagged": 0,
        },
    )
    await redis.sadd("node:index", node_id)
    await redis.sadd(f"org:{organization_id}:nodes", node_id)
    await redis.sadd(f"user:{owner_email}:nodes", node_id)
    await record_audit_event(
        actor_email=current_user.email,
        action="node.created",
        organization_id=organization_id,
        target=node_id,
        metadata={"name": payload.name},
    )
    return await _build_node_status(node_id)


@router.post("/register", response_model=NodeStatus, status_code=status.HTTP_201_CREATED)
async def register_legacy_node(
    payload: NodeRegistration,
    current_user: UserPublic = Depends(NodeWriter),
) -> NodeStatus:
    return await create_node(payload, current_user)


@router.get("", response_model=list[NodeStatus])
async def list_nodes(current_user: UserPublic = Depends(require_org_admin())) -> list[NodeStatus]:
    redis = await get_redis()
    if current_user.role == UserRole.SUPER_ADMIN:
        node_ids = await redis.smembers("node:index")
    else:
        node_ids = await redis.smembers(f"org:{current_user.organization_id}:nodes")
    results: list[NodeStatus] = []
    for node_id in node_ids:
        try:
            results.append(await _build_node_status(node_id))
        except HTTPException:
            continue
    return results


@router.get("/{node_id}", response_model=NodeStatus)
async def get_node(node_id: str, current_user: UserPublic = Depends(require_org_admin())) -> NodeStatus:
    node = await _build_node_status(node_id)
    if current_user.role != UserRole.SUPER_ADMIN and node.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Node does not belong to your organization")
    return node


@router.patch("/{node_id}", response_model=NodeStatus)
async def update_node(
    node_id: str,
    payload: NodeUpdate,
    current_user: UserPublic = Depends(NodeWriter),
) -> NodeStatus:
    redis = await get_redis()
    node_key = f"node:{node_id}"
    node_data = await redis.hgetall(node_key)
    if not node_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")
    if current_user.role != UserRole.SUPER_ADMIN and node_data.get("organization_id") != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Node does not belong to your organization")
    updates = payload.model_dump(exclude_none=True)
    if "tags" in updates:
        updates["tags"] = ",".join(updates["tags"])
    if "is_flagged" in updates:
        updates["is_flagged"] = 1 if bool(updates["is_flagged"]) else 0
    if updates:
        updates["updated_at"] = datetime.utcnow().isoformat()
        await redis.hset(node_key, mapping=updates)
        if "owner_email" in updates:
            await redis.srem(f"user:{node_data.get('owner_email')}:nodes", node_id)
            await redis.sadd(f"user:{updates['owner_email']}:nodes", node_id)
        if "is_flagged" in updates:
            await record_audit_event(
                actor_email=current_user.email,
                action="node.flagged" if updates["is_flagged"] else "node.unflagged",
                organization_id=node_data.get("organization_id"),
                target=node_id,
            )
    return await _build_node_status(node_id)


async def _build_node_status(node_id: str) -> NodeStatus:
    redis = await get_redis()
    node = await redis.hgetall(f"node:{node_id}")
    if not node:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")
    stats = await redis.hgetall(f"uptime:{node_id}")
    latency_raw = float(stats.get("latency_ms", 0)) if stats.get("latency_ms") else None
    if latency_raw is not None and latency_raw < 0:
        latency_raw = None
    tags = node.get("tags", "")
    
    return NodeStatus(
        id=node_id,
        organization_id=node.get("organization_id", ""),
        name=node.get("name", ""),
        p2p_address=node.get("p2p_address", ""),
        rpc_url=node.get("rpc_url", ""),
        wallet_address=node.get("wallet_address", ""),
        owner_email=node.get("owner_email") or None,
        tags=[tag for tag in tags.split(",") if tag],
        last_seen=datetime.fromisoformat(stats["last_seen"]) if stats.get("last_seen") else None,
        uptime_score=float(stats.get("uptime_score", 0.0)),
        total_checks=int(stats.get("total_checks", 0)),
        successful_checks=int(stats.get("successful_checks", 0)),
        latency_ms=latency_raw,
        block_height=int(stats.get("block_height", 0)) if stats.get("block_height") else None,
        is_flagged=bool(int(node.get("is_flagged", 0))),
        # ✅ NEW: expose online status from Redis
        is_online=bool(int(stats.get("is_online", 0))),
    )
