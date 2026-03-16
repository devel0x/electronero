import os
import time
from datetime import datetime
from typing import Any, Dict

import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

app = FastAPI(title="IGP Staking")
templates = Jinja2Templates(directory="templates")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _norm_key(key: str) -> str:
    return key.strip().lower()


def _position_key(user: str, pos_id: str | int) -> str:
    return f"staking:positions:{user}:{pos_id}"


def _now_ts() -> int:
    return int(time.time())


def _multiplier(lock_days: int) -> float:
    return 1 + lock_days / 365


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class StakeRequest(BaseModel):
    email_or_wallet: str
    amount: float
    lock_days: int


class UnstakeRequest(BaseModel):
    email_or_wallet: str
    pos_id: str


class PoolFundRequest(BaseModel):
    cycle_id: str
    amount: float


class RewardDistributeRequest(BaseModel):
    cycle_id: str
    date: str  # YYYY-MM-DD


# ---------------------------------------------------------------------------
# User Endpoints
# ---------------------------------------------------------------------------


@app.post("/stake")
async def stake(req: StakeRequest) -> Dict[str, Any]:
    user = _norm_key(req.email_or_wallet)
    bal_key = f"balances:{user}"
    available = float(await redis_client.hget(bal_key, "available") or 0)
    if available < req.amount:
        raise HTTPException(status_code=400, detail="insufficient balance")

    pos_id = await redis_client.incr(f"staking:positions:{user}:next_id")
    start_ts = _now_ts()
    end_ts = start_ts + req.lock_days * 86400
    mult = _multiplier(req.lock_days)

    pipe = redis_client.pipeline()
    pipe.hincrbyfloat(bal_key, "available", -req.amount)
    pipe.hincrbyfloat(bal_key, "staked", req.amount)
    pipe.hset(
        _position_key(user, pos_id),
        mapping={
            "amount": req.amount,
            "lock_days": req.lock_days,
            "multiplier": mult,
            "start_ts": start_ts,
            "end_ts": end_ts,
            "active": 1,
        },
    )
    await pipe.execute()
    return {"ok": True, "pos_id": pos_id}


@app.post("/unstake")
async def unstake(req: UnstakeRequest) -> Dict[str, Any]:
    user = _norm_key(req.email_or_wallet)
    pkey = _position_key(user, req.pos_id)
    pos = await redis_client.hgetall(pkey)
    if not pos or pos.get("active") != "1":
        raise HTTPException(status_code=404, detail="position not found")
    if int(pos.get("end_ts", 0)) > _now_ts():
        raise HTTPException(status_code=400, detail="position still locked")

    amount = float(pos.get("amount", 0))
    bal_key = f"balances:{user}"
    pipe = redis_client.pipeline()
    pipe.hincrbyfloat(bal_key, "available", amount)
    pipe.hincrbyfloat(bal_key, "staked", -amount)
    pipe.hset(pkey, "active", 0)
    await pipe.execute()
    return {"ok": True}


@app.get("/staking/status/{email_or_wallet}")
async def staking_status(email_or_wallet: str) -> Dict[str, Any]:
    user = _norm_key(email_or_wallet)
    bal_key = f"balances:{user}"
    balances = await redis_client.hgetall(bal_key)

    positions = []
    pattern = f"staking:positions:{user}:*"
    async for key in redis_client.scan_iter(pattern):
        pos = await redis_client.hgetall(key)
        pos_id = key.split(":")[-1]
        pos["pos_id"] = pos_id
        positions.append(pos)

    today = datetime.utcnow().strftime("%Y-%m-%d")
    points = float(await redis_client.hget(f"staking:points:{today}", user) or 0)
    rewards = float(balances.get("rewards", 0))

    return {
        "balances": balances,
        "positions": positions,
        "points_today": points,
        "rewards": rewards,
    }


# ---------------------------------------------------------------------------
# Admin Endpoints
# ---------------------------------------------------------------------------


@app.post("/staking/pool/fund")
async def pool_fund(req: PoolFundRequest) -> Dict[str, Any]:
    key = f"staking:pool:{req.cycle_id}"
    await redis_client.hincrbyfloat(key, "pool_amount", req.amount)
    return {"ok": True}


@app.post("/staking/rewards/distribute")
async def rewards_distribute(req: RewardDistributeRequest) -> Dict[str, Any]:
    pool_key = f"staking:pool:{req.cycle_id}"
    pool = await redis_client.hgetall(pool_key)
    if pool.get("distributed") == "1":
        raise HTTPException(status_code=400, detail="already distributed")
    pool_amount = float(pool.get("pool_amount", 0))
    if pool_amount <= 0:
        raise HTTPException(status_code=400, detail="pool empty")

    points_key = f"staking:points:{req.date}"
    data = await redis_client.hgetall(points_key)
    total_points = float(data.get("total", 0))
    if total_points <= 0:
        raise HTTPException(status_code=400, detail="no points for date")

    reward_per_point = pool_amount / total_points
    pipe = redis_client.pipeline()
    for usr, pts in data.items():
        if usr == "total":
            continue
        reward = float(pts) * reward_per_point
        pipe.hincrbyfloat(f"balances:{usr}", "rewards", reward)
    pipe.hset(
        pool_key,
        mapping={
            "reward_per_point": reward_per_point,
            "total_points": total_points,
            "distributed": 1,
        },
    )
    await pipe.execute()
    return {"ok": True, "reward_per_point": reward_per_point}


# ---------------------------------------------------------------------------
# Dashboards
# ---------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/user/{email}", response_class=HTMLResponse)
async def user_dashboard(request: Request, email: str) -> HTMLResponse:
    data = await staking_status(email)
    return templates.TemplateResponse(
        "user.html", {"request": request, "user_id": email, **data}
    )


@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("admin.html", {"request": request})


__all__ = ["app"]
