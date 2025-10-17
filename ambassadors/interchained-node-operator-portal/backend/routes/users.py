"""User authentication routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from .. import auth
from ..models import UserCreate, UserLogin, UserPublic

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def register_user(payload: UserCreate) -> UserPublic:
    return await auth.create_user(payload)


@router.post("/login")
async def login_user(payload: UserLogin) -> dict[str, str]:
    user = await auth.authenticate_user(payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = await auth.create_session_token(user.email)
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=UserPublic)
async def get_me(current_user: UserPublic = Depends(auth.get_current_user)) -> UserPublic:
    return current_user
