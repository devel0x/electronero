"""Pydantic models used across the FastAPI application."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, Field, HttpUrl


class UserRole(str, Enum):
    """Supported authorization roles."""

    SUPER_ADMIN = "super_admin"
    ORG_ADMIN = "org_admin"
    OPERATOR = "operator"
    AUDITOR = "auditor"


class ServicePlanTier(str, Enum):
    """Service plan tiers for tenant organisations."""

    LAUNCH = "launch"
    GROWTH = "growth"
    ENTERPRISE = "enterprise"


class FeatureSettings(BaseModel):
    """Feature toggles that can be attached to an organisation."""

    realtime_alerting: bool = True
    automated_payouts: bool = False
    ai_insights: bool = False
    gamified_badges: bool = True
    compliance_reporting: bool = True
    unlimited_seats: bool = False


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    billing_email: EmailStr
    plan: ServicePlanTier = ServicePlanTier.ENTERPRISE
    feature_overrides: Optional[FeatureSettings] = None
    slug: Optional[str] = Field(default=None, description="Custom slug for vanity URLs")


class Organization(BaseModel):
    id: str
    name: str
    slug: str
    billing_email: EmailStr
    plan: ServicePlanTier
    features: FeatureSettings
    created_at: datetime
    updated_at: datetime
    owner_email: EmailStr
    is_active: bool = True


class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    billing_email: Optional[EmailStr] = None
    plan: Optional[ServicePlanTier] = None
    feature_overrides: Optional[FeatureSettings] = None
    is_active: Optional[bool] = None


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12)
    full_name: str = Field(min_length=2)
    invite_code: Optional[str] = Field(default=None, description="Invitation code when registering")


class AdminUserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12)
    full_name: str
    role: UserRole = UserRole.OPERATOR
    organization_id: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserPublic(BaseModel):
    email: EmailStr
    full_name: str
    organization_id: str
    role: UserRole
    created_at: datetime


class SessionToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserPublic


class InviteCreate(BaseModel):
    organization_id: str
    role: UserRole = UserRole.OPERATOR
    expires_in_hours: int = Field(default=72, ge=1, le=24 * 14)
    note: Optional[str] = None


class InvitePublic(BaseModel):
    code: str
    organization_id: str
    role: UserRole
    expires_at: datetime
    created_by: EmailStr
    note: Optional[str] = None


class NodeRegistration(BaseModel):
    name: str = Field(min_length=3, max_length=80)
    p2p_address: str = Field(description="IP or hostname with port, e.g. node.example:18080")
    rpc_url: HttpUrl
    wallet_address: str
    owner_email: Optional[EmailStr] = None
    tags: list[str] = Field(default_factory=list)


class NodeUpdate(BaseModel):
    name: Optional[str] = None
    p2p_address: Optional[str] = None
    rpc_url: Optional[HttpUrl] = None
    wallet_address: Optional[str] = None
    owner_email: Optional[EmailStr] = None
    tags: Optional[list[str]] = None
    is_flagged: Optional[bool] = None


class NodeStatus(BaseModel):
    id: str
    organization_id: str
    name: str
    p2p_address: str
    rpc_url: HttpUrl
    wallet_address: str
    owner_email: Optional[EmailStr] = None
    tags: list[str] = Field(default_factory=list)
    last_seen: Optional[datetime] = None
    uptime_score: float = 0.0
    total_checks: int = 0
    successful_checks: int = 0
    latency_ms: Optional[float] = None
    block_height: Optional[int] = None
    is_flagged: bool = False
    p2p_online: bool = False
    rpc_responding: bool = False
    fully_online: bool = False


class RewardSummary(BaseModel):
    date: datetime
    rewards: dict[str, float]
    pool_balance: float


class RewardHistoryItem(BaseModel):
    date: datetime
    amount: float
    node_id: str


class RewardHistory(BaseModel):
    organization_id: str
    history: list[RewardHistoryItem]


class PoolBalance(BaseModel):
    balance: float


class PoolTopUpRequest(BaseModel):
    amount: float = Field(gt=0, description="Amount to add to the reward pool")


class AuditEvent(BaseModel):
    id: str
    actor_email: EmailStr
    organization_id: Optional[str]
    action: str
    target: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class MetricTimeseriesPoint(BaseModel):
    timestamp: datetime
    value: float


class AdminDashboardMetrics(BaseModel):
    total_active_nodes: int
    avg_uptime: float
    flagged_nodes: int
    mrr: float
    plan_distribution: dict[str, int]
    uptime_timeseries: list[MetricTimeseriesPoint]


class BillingSummary(BaseModel):
    organization_id: str
    plan: ServicePlanTier
    monthly_cost: float
    included_nodes: int
    additional_node_price: float
    current_month_usage: int
