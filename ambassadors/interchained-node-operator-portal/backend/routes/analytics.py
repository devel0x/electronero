"""Analytics API endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ..dependencies import require_org_admin, require_super_admin
from ..models import AdminDashboardMetrics, BillingSummary, UserPublic, UserRole
from ..services import analytics


router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/dashboard", response_model=AdminDashboardMetrics)
async def get_dashboard_metrics(_: UserPublic = Depends(require_super_admin())) -> AdminDashboardMetrics:
    return await analytics.get_dashboard_metrics()


@router.get("/billing/{organization_id}", response_model=BillingSummary)
async def get_billing_summary(
    organization_id: str,
    current_user: UserPublic = Depends(require_org_admin()),
) -> BillingSummary:
    if current_user.role != UserRole.SUPER_ADMIN and current_user.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot access another organization")
    return await analytics.get_billing_summary(organization_id)
