"""Pydantic models used across the FastAPI application."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, HttpUrl


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserPublic(BaseModel):
    email: EmailStr
    created_at: datetime


class NodeRegistration(BaseModel):
    email: EmailStr
    p2p_address: str = Field(description="IP or hostname with port, e.g. node.example:18080")
    rpc_url: HttpUrl
    wallet_address: str


class NodeUpdate(BaseModel):
    p2p_address: Optional[str] = None
    rpc_url: Optional[HttpUrl] = None
    wallet_address: Optional[str] = None


class NodeStatus(BaseModel):
    email: EmailStr
    p2p_address: str
    rpc_url: HttpUrl
    wallet_address: str
    last_seen: Optional[datetime] = None
    uptime_score: float = 0.0
    total_checks: int = 0
    successful_checks: int = 0
    latency_ms: Optional[float] = None
    block_height: Optional[int] = None


class RewardSummary(BaseModel):
    date: datetime
    rewards: dict[str, float]
    pool_balance: float


class RewardHistoryItem(BaseModel):
    date: datetime
    amount: float


class RewardHistory(BaseModel):
    email: EmailStr
    history: list[RewardHistoryItem]
