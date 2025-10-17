"""FastAPI entry point for the Node Operator Rewards Portal backend."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .node_monitor import NodeMonitor
from .rewards import RewardDistributor
from .routes import nodes, rewards, users
from .utils.redis_client import close_redis


@asynccontextmanager
def lifespan(_: FastAPI) -> AsyncIterator[None]:
    monitor = NodeMonitor()
    rewards_job = RewardDistributor()
    await asyncio.gather(monitor.start(), rewards_job.start())
    try:
        yield
    finally:
        await asyncio.gather(monitor.stop(), rewards_job.stop())
        await close_redis()


app = FastAPI(title="Interchained Node Operator Rewards Portal", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router)
app.include_router(nodes.router)
app.include_router(rewards.router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"status": "ok"}
