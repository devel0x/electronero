import os
import time
from datetime import datetime
from typing import Dict

import redis.asyncio as redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_client = redis.from_url(REDIS_URL, decode_responses=True)


def _norm_user(key: str) -> str:
    return key.strip().lower()


def _now() -> int:
    return int(time.time())

async def snapshot_worker(date: str | None = None) -> None:
    if date is None:
        date = datetime.utcnow().strftime("%Y-%m-%d")
    user_points: Dict[str, float] = {}
    async for key in redis_client.scan_iter("staking:positions:*"):
        pos = await redis_client.hgetall(key)
        if pos.get("active") != "1":
            continue
        user = key.split(":")[2]
        amount = float(pos.get("amount", 0))
        mult = float(pos.get("multiplier", 1))
        user_points[user] = user_points.get(user, 0.0) + amount * mult
    total = sum(user_points.values())
    pipe = redis_client.pipeline()
    for user, pts in user_points.items():
        pipe.hset(f"staking:points:{date}", user, pts)
    pipe.hset(f"staking:points:{date}", "total", total)
    await pipe.execute()


async def reward_cycle_worker(cycle_id: str, date: str) -> None:
    pool_key = f"staking:pool:{cycle_id}"
    pool = await redis_client.hgetall(pool_key)
    if pool.get("distributed") == "1":
        return
    pool_amount = float(pool.get("pool_amount", 0))
    data = await redis_client.hgetall(f"staking:points:{date}")
    total_points = float(data.get("total", 0))
    if pool_amount <= 0 or total_points <= 0:
        return
    reward_per_point = pool_amount / total_points
    pipe = redis_client.pipeline()
    for user, pts in data.items():
        if user == "total":
            continue
        reward = float(pts) * reward_per_point
        pipe.hincrbyfloat(f"balances:{user}", "rewards", reward)
    pipe.hset(
        pool_key,
        mapping={
            "reward_per_point": reward_per_point,
            "total_points": total_points,
            "distributed": 1,
        },
    )
    await pipe.execute()


async def expiry_cleaner(now: int | None = None) -> None:
    if now is None:
        now = _now()
    async for key in redis_client.scan_iter("staking:positions:*"):
        pos = await redis_client.hgetall(key)
        if pos.get("active") != "1":
            continue
        end_ts = int(pos.get("end_ts", 0))
        if end_ts > now:
            continue
        user = key.split(":")[2]
        amount = float(pos.get("amount", 0))
        pipe = redis_client.pipeline()
        pipe.hincrbyfloat(f"balances:{user}", "available", amount)
        pipe.hincrbyfloat(f"balances:{user}", "staked", -amount)
        pipe.hset(key, "active", 0)
        await pipe.execute()
