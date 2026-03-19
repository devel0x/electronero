"""Data models used by the Rewards Portal backend."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional

from pydantic import BaseModel, Field, IPvAnyAddress, validator


class UserCreate(BaseModel):
    email: str
    password: str

    @validator("password")
    def _validate_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return value


class UserRead(BaseModel):
    id: str
    email: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class NodeCreate(BaseModel):
    name: str = Field(..., max_length=64)
    p2p_host: IPvAnyAddress
    p2p_port: int = Field(..., ge=1, le=65535)
    rpc_host: IPvAnyAddress
    rpc_port: int = Field(..., ge=1, le=65535)
    wallet_address: str = Field(..., min_length=32, max_length=128)


class NodeUpdate(BaseModel):
    name: Optional[str]
    p2p_host: Optional[IPvAnyAddress]
    p2p_port: Optional[int]
    rpc_host: Optional[IPvAnyAddress]
    rpc_port: Optional[int]
    wallet_address: Optional[str]


class NodeRead(BaseModel):
    id: str
    owner_id: str
    name: str
    p2p_host: str
    p2p_port: int
    rpc_host: str
    rpc_port: int
    wallet_address: str
    created_at: datetime
    flagged: bool


class HealthCheckResult(BaseModel):
    node_id: str
    timestamp: datetime
    online: bool
    rpc_latency_ms: Optional[float]
    sync_height: Optional[int]


class RewardRecord(BaseModel):
    node_id: str
    owner_id: str
    amount: float
    total_score: float
    timestamp: datetime


class DashboardSummary(BaseModel):
    total_nodes: int
    active_nodes: int
    reward_pool_daily: float
    last_distribution: Optional[datetime]
    flagged_nodes: int


class UptimeScore(BaseModel):
    node_id: str
    uptime_ratio: float
    total_checks: int
    successful_checks: int
    average_latency_ms: Optional[float]


class RewardPreview(BaseModel):
    node: NodeRead
    uptime: UptimeScore
    projected_reward: float


class NodeWithMetrics(NodeRead):
    uptime: UptimeScore
    last_health: Optional[HealthCheckResult]
