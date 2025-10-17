"""Audit trail endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..dependencies import require_org_admin
from ..models import AuditEvent, UserPublic, UserRole
from ..services.audit import fetch_audit_events


router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=list[AuditEvent])
async def get_audit_trail(
    limit: int = 100,
    current_user: UserPublic = Depends(require_org_admin()),
) -> list[AuditEvent]:
    if current_user.role == UserRole.SUPER_ADMIN:
        return await fetch_audit_events(limit=limit)
    return await fetch_audit_events(limit=limit, organization_id=current_user.organization_id)
