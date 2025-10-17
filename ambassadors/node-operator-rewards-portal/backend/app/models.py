"""Data models used by the Rewards Portal backend."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
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


class NodeStatus(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"


class AuthenticatedUser(BaseModel):
    id: str
    email: str
    is_admin: bool = False


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
    status: NodeStatus = NodeStatus.APPROVED


class HealthCheckResult(BaseModel):
    node_id: str
    timestamp: datetime
    online: bool
    rpc_latency_ms: Optional[float]
    sync_height: Optional[int]
    p2p_online: bool = False
    p2p_latency_ms: Optional[float] = None


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
    p2p_uptime_ratio: float = 0.0
    p2p_total_checks: int = 0
    p2p_successful_checks: int = 0
    p2p_average_latency_ms: Optional[float] = None


class RewardPreview(BaseModel):
    node: NodeRead
    uptime: UptimeScore
    projected_reward: float


class NodeWithMetrics(NodeRead):
    uptime: UptimeScore
    last_health: Optional[HealthCheckResult]


class PoolState(BaseModel):
    current_balance: float
    daily_distribution: float
    last_distribution: Optional[datetime]
    total_nodes: int
    active_nodes: int
    rejected_nodes: int


class PoolAdjustment(BaseModel):
    amount: float


class PoolDailyUpdate(BaseModel):
    daily_distribution: float = Field(..., gt=0)


class AdminNodeDetail(BaseModel):
    node: NodeWithMetrics
    owner_email: str


class PayoutExportRow(BaseModel):
    node_id: str
    node_name: str
    owner_email: str
    wallet_address: str
    projected_reward: float
