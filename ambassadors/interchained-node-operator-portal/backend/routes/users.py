"""User authentication routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from .. import auth
from ..dependencies import require_org_admin
from ..models import InviteCreate, InvitePublic, SessionToken, UserCreate, UserLogin, UserPublic

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def register_user(payload: UserCreate) -> UserPublic:
    return await auth.create_user(payload)


@router.post("/login", response_model=SessionToken)
async def login_user(payload: UserLogin) -> SessionToken:
    user = await auth.authenticate_user(payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return await auth.create_session_token(user)


@router.get("/me", response_model=UserPublic)
async def get_me(current_user: UserPublic = Depends(auth.get_current_user)) -> UserPublic:
    return current_user


@router.post("/invites", response_model=InvitePublic)
async def create_invite(
    payload: InviteCreate,
    current_user: UserPublic = Depends(require_org_admin()),
) -> InvitePublic:
    return await auth.create_invite(payload, current_user)


@router.get("/invites", response_model=list[InvitePublic])
async def list_invites(current_user: UserPublic = Depends(require_org_admin())) -> list[InvitePublic]:
    return await auth.list_invites(current_user.organization_id)
