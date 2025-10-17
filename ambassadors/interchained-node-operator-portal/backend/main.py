"""FastAPI entry point for the Node Operator Rewards Portal backend."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .node_monitor import NodeMonitor
from .rewards import RewardDistributor
from .routes import admin, analytics, audit, nodes, rewards, users
from .utils.redis_client import close_redis


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    monitor = NodeMonitor()
    rewards_job = RewardDistributor()
    await asyncio.gather(monitor.start(), rewards_job.start())
    try:
        yield
    finally:
        await asyncio.gather(monitor.stop(), rewards_job.stop())
        await close_redis()


settings = get_settings()

app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_prefix = "/api/v1"

app.include_router(users.router, prefix=api_prefix)
app.include_router(admin.router, prefix=api_prefix)
app.include_router(nodes.router, prefix=api_prefix)
app.include_router(rewards.router, prefix=api_prefix)
app.include_router(analytics.router, prefix=api_prefix)
app.include_router(audit.router, prefix=api_prefix)


@app.get("/")
async def root() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}
