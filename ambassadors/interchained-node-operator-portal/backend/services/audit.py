"""Audit logging services."""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from ..config import get_settings
from ..models import AuditEvent
from ..utils.ids import short_ulid
from ..utils.redis_client import get_redis


async def record_audit_event(
    *,
    actor_email: str,
    action: str,
    organization_id: str | None = None,
    target: str | None = None,
    metadata: dict[str, str] | None = None,
) -> AuditEvent:
    """Persist an immutable audit event."""

    redis = await get_redis()
    now = datetime.utcnow()
    event_id = short_ulid("audit")
    event = AuditEvent(
        id=event_id,
        actor_email=actor_email,
        organization_id=organization_id,
        action=action,
        target=target,
        metadata=metadata or {},
        created_at=now,
    )
    await redis.hset(
        f"audit:{event_id}",
        mapping={
            "id": event.id,
            "actor_email": event.actor_email,
            "organization_id": event.organization_id or "",
            "action": event.action,
            "target": event.target or "",
            "metadata": json.dumps(event.metadata),
            "created_at": event.created_at.isoformat(),
        },
    )
    await redis.zadd("audit:index", {event_id: now.timestamp()})
    await _enforce_retention()
    return event


async def fetch_audit_events(*, limit: int = 100, organization_id: str | None = None) -> list[AuditEvent]:
    redis = await get_redis()
    event_ids = await redis.zrevrange("audit:index", 0, limit - 1)
    events: list[AuditEvent] = []
    for event_id in event_ids:
        data = await redis.hgetall(f"audit:{event_id}")
        if not data:
            continue
        event = AuditEvent(
            id=data["id"],
            actor_email=data["actor_email"],
            organization_id=data["organization_id"] or None,
            action=data["action"],
            target=data["target"] or None,
            metadata=json.loads(data.get("metadata", "{}")),
            created_at=datetime.fromisoformat(data["created_at"]),
        )
        if organization_id and event.organization_id != organization_id:
            continue
        events.append(event)
    return events


async def _enforce_retention() -> None:
    settings = get_settings()
    redis = await get_redis()
    cutoff = datetime.utcnow() - timedelta(days=settings.audit_log_retention_days)
    await redis.zremrangebyscore("audit:index", 0, cutoff.timestamp())
