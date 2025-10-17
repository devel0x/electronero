"""Organisation management services."""
from __future__ import annotations

from datetime import datetime

from slugify import slugify

from ..models import FeatureSettings, Organization, OrganizationCreate, OrganizationUpdate, ServicePlanTier
from ..utils.ids import short_ulid
from ..utils.redis_client import get_redis


def _plan_defaults(plan: ServicePlanTier) -> FeatureSettings:
    if plan == ServicePlanTier.LAUNCH:
        return FeatureSettings(
            realtime_alerting=False,
            gamified_badges=True,
            compliance_reporting=False,
        )
    if plan == ServicePlanTier.GROWTH:
        return FeatureSettings(
            realtime_alerting=True,
            gamified_badges=True,
            automated_payouts=False,
            ai_insights=False,
        )
    return FeatureSettings(
        realtime_alerting=True,
        automated_payouts=True,
        ai_insights=True,
        gamified_badges=True,
        compliance_reporting=True,
        unlimited_seats=True,
    )


async def create_organization(payload: OrganizationCreate, owner_email: str) -> Organization:
    redis = await get_redis()
    org_id = short_ulid("org")
    now = datetime.utcnow()
    slug = payload.slug or slugify(payload.name)
    features = payload.feature_overrides or _plan_defaults(payload.plan)
    org_key = f"org:{org_id}"
    await redis.hset(
        org_key,
        mapping={
            "id": org_id,
            "name": payload.name,
            "slug": slug,
            "billing_email": payload.billing_email,
            "plan": payload.plan.value,
            "features": features.model_dump_json(),
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "owner_email": owner_email,
            "is_active": 1,
        },
    )
    await redis.hset("org:slugs", slug, org_id)
    await redis.sadd("org:index", org_id)
    return Organization(
        id=org_id,
        name=payload.name,
        slug=slug,
        billing_email=payload.billing_email,
        plan=payload.plan,
        features=features,
        created_at=now,
        updated_at=now,
        owner_email=owner_email,
        is_active=True,
    )


async def get_organization(org_id: str) -> Organization | None:
    redis = await get_redis()
    data = await redis.hgetall(f"org:{org_id}")
    if not data:
        return None
    return _deserialize_org(data)


async def get_organization_by_slug(slug: str) -> Organization | None:
    redis = await get_redis()
    org_id = await redis.hget("org:slugs", slug)
    if not org_id:
        return None
    return await get_organization(org_id)


async def update_organization(org_id: str, payload: OrganizationUpdate) -> Organization | None:
    redis = await get_redis()
    org_key = f"org:{org_id}"
    data = await redis.hgetall(org_key)
    if not data:
        return None
    updates: dict[str, str | int] = {}
    if payload.name:
        updates["name"] = payload.name
        new_slug = slugify(payload.name)
        current_slug = data.get("slug")
        if current_slug and new_slug != current_slug:
            await redis.hdel("org:slugs", current_slug)
            await redis.hset("org:slugs", new_slug, org_id)
        updates["slug"] = new_slug
    if payload.billing_email:
        updates["billing_email"] = payload.billing_email
    if payload.plan:
        updates["plan"] = payload.plan.value
    if payload.feature_overrides:
        updates["features"] = payload.feature_overrides.model_dump_json()
    if payload.is_active is not None:
        updates["is_active"] = 1 if payload.is_active else 0
    if updates:
        updates["updated_at"] = datetime.utcnow().isoformat()
        await redis.hset(org_key, mapping=updates)
    data.update({k: str(v) for k, v in updates.items()})
    return _deserialize_org(data)


async def list_organizations() -> list[Organization]:
    redis = await get_redis()
    org_ids = await redis.smembers("org:index")
    results: list[Organization] = []
    for org_id in org_ids:
        data = await redis.hgetall(f"org:{org_id}")
        if data:
            org = _deserialize_org(data)
            results.append(org)
    return sorted(results, key=lambda org: org.created_at)


async def count_organizations() -> int:
    redis = await get_redis()
    return await redis.scard("org:index")


def _deserialize_org(data: dict[str, str]) -> Organization:
    return Organization(
        id=data["id"],
        name=data["name"],
        slug=data["slug"],
        billing_email=data["billing_email"],
        plan=ServicePlanTier(data.get("plan", ServicePlanTier.LAUNCH.value)),
        features=FeatureSettings.model_validate_json(data.get("features", FeatureSettings().model_dump_json())),
        created_at=datetime.fromisoformat(data["created_at"]),
        updated_at=datetime.fromisoformat(data["updated_at"]),
        owner_email=data.get("owner_email", ""),
        is_active=bool(int(data.get("is_active", "1"))),
    )
