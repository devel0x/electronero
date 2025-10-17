"""Administrative API endpoints for the control panel."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from .. import auth
from ..dependencies import require_org_admin, require_super_admin
from ..models import (
    AdminUserCreate,
    Organization,
    OrganizationCreate,
    OrganizationUpdate,
    UserPublic,
    UserRole,
)
from ..services import organizations
from ..services.audit import record_audit_event


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/organizations", response_model=list[Organization])
async def list_organizations_route(_: UserPublic = Depends(require_super_admin())) -> list[Organization]:
    return await organizations.list_organizations()


@router.post("/organizations", response_model=Organization, status_code=status.HTTP_201_CREATED)
async def create_organization_route(
    payload: OrganizationCreate,
    current_user: UserPublic = Depends(require_super_admin()),
) -> Organization:
    org = await organizations.create_organization(payload, owner_email=current_user.email)
    await record_audit_event(actor_email=current_user.email, action="organization.created", organization_id=org.id)
    return org


@router.patch("/organizations/{organization_id}", response_model=Organization)
async def update_organization_route(
    organization_id: str,
    payload: OrganizationUpdate,
    current_user: UserPublic = Depends(require_super_admin()),
) -> Organization:
    org = await organizations.update_organization(organization_id, payload)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    changed_fields = list(payload.model_dump(exclude_none=True).keys())
    await record_audit_event(
        actor_email=current_user.email,
        action="organization.updated",
        organization_id=org.id,
        metadata={"fields": changed_fields},
    )
    return org


@router.post("/users", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def create_user_route(
    payload: AdminUserCreate,
    current_user: UserPublic = Depends(require_org_admin()),
) -> UserPublic:
    if current_user.role != UserRole.SUPER_ADMIN and payload.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot manage another organization")
    return await auth.create_admin_user(payload, current_user)


@router.get("/organizations/{organization_id}/users", response_model=list[UserPublic])
async def list_org_users_route(
    organization_id: str,
    current_user: UserPublic = Depends(require_org_admin()),
) -> list[UserPublic]:
    if current_user.role != UserRole.SUPER_ADMIN and current_user.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot view another organization")
    return await auth.list_org_users(organization_id)


@router.post("/users/{email}/role", response_model=UserPublic)
async def update_user_role_route(
    email: str,
    role: UserRole,
    current_user: UserPublic = Depends(require_org_admin()),
) -> UserPublic:
    return await auth.update_user_role(email, role, current_user)


@router.post("/users/{email}/deactivate", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_user_route(
    email: str,
    current_user: UserPublic = Depends(require_org_admin()),
) -> None:
    await auth.deactivate_user(email, current_user)
