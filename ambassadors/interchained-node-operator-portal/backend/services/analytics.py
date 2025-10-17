"""Analytics services supporting the admin dashboard."""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, datetime, timedelta

from ..models import AdminDashboardMetrics, BillingSummary, MetricTimeseriesPoint, ServicePlanTier
from ..utils.redis_client import get_redis


PLAN_PRICING = {
    ServicePlanTier.LAUNCH: {"price": 99.0, "included": 5, "overage": 20.0},
    ServicePlanTier.GROWTH: {"price": 299.0, "included": 20, "overage": 15.0},
    ServicePlanTier.ENTERPRISE: {"price": 799.0, "included": 100, "overage": 10.0},
}


async def get_dashboard_metrics() -> AdminDashboardMetrics:
    redis = await get_redis()
    node_ids = await redis.smembers("node:index")
    total_active_nodes = 0
    uptime_scores: list[float] = []
    flagged_nodes = 0

    for node_id in node_ids:
        node = await redis.hgetall(f"node:{node_id}")
        if not node:
            continue
        stats = await redis.hgetall(f"uptime:{node_id}")
        score = float(stats.get("uptime_score", 0.0)) if stats else 0.0
        if score >= 0.9:
            total_active_nodes += 1
        uptime_scores.append(score)
        if int(node.get("is_flagged", 0)):
            flagged_nodes += 1

    avg_uptime = sum(uptime_scores) / len(uptime_scores) if uptime_scores else 0.0

    plan_distribution: dict[str, int] = {}
    org_ids = await redis.smembers("org:index")
    for org_id in org_ids:
        raw_plan = await redis.hget(f"org:{org_id}", "plan") or ServicePlanTier.LAUNCH.value
        try:
            plan_enum = ServicePlanTier(raw_plan)
        except ValueError:
            plan_enum = ServicePlanTier.LAUNCH
        plan_distribution[plan_enum.value] = plan_distribution.get(plan_enum.value, 0) + 1

    mrr = 0.0
    for plan, count in plan_distribution.items():
        try:
            plan_enum = ServicePlanTier(plan)
        except ValueError:
            continue
        mrr += PLAN_PRICING.get(plan_enum, {"price": 0})["price"] * count

    now = datetime.utcnow()
    window_start = now - timedelta(days=6)
    raw_entries = await redis.zrangebyscore("metrics:uptime:global", window_start.timestamp(), "+inf")
    buckets: dict[date, list[float]] = defaultdict(list)
    for entry in raw_entries:
        try:
            payload = json.loads(entry)
            timestamp = datetime.fromisoformat(payload["timestamp"])
            uptime = float(payload.get("uptime", 0.0))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            continue
        buckets[timestamp.date()].append(uptime)

    points: list[MetricTimeseriesPoint] = []
    for offset in range(6, -1, -1):
        day = (now - timedelta(days=offset)).date()
        samples = buckets.get(day, [])
        average = sum(samples) / len(samples) if samples else 0.0
        points.append(
            MetricTimeseriesPoint(
                timestamp=datetime.combine(day, datetime.min.time()),
                value=round(average * 100, 2),
            )
        )

    return AdminDashboardMetrics(
        total_active_nodes=total_active_nodes,
        avg_uptime=round(avg_uptime, 4),
        flagged_nodes=flagged_nodes,
        mrr=float(mrr),
        plan_distribution=plan_distribution,
        uptime_timeseries=points,
    )


async def get_billing_summary(organization_id: str) -> BillingSummary:
    redis = await get_redis()
    plan_value = await redis.hget(f"org:{organization_id}", "plan") or ServicePlanTier.LAUNCH.value
    try:
        plan = ServicePlanTier(plan_value)
    except ValueError:
        plan = ServicePlanTier.LAUNCH
    pricing = PLAN_PRICING[plan]
    current_usage = await redis.scard(f"org:{organization_id}:nodes")
    included = pricing["included"]
    overage_nodes = max(current_usage - included, 0)
    monthly_cost = pricing["price"] + overage_nodes * pricing["overage"]
    return BillingSummary(
        organization_id=organization_id,
        plan=plan,
        monthly_cost=monthly_cost,
        included_nodes=included,
        additional_node_price=pricing["overage"],
        current_month_usage=current_usage,
    )
