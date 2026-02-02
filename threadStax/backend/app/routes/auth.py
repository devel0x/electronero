from fastapi import APIRouter, Depends

from ..auth import create_session, login_user, logout_user
from ..models import ApiMessage, LoginRequest, LoginResponse, User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest) -> LoginResponse:
    user = await login_user(payload.username, payload.role)
    token = await create_session(user.uid)
    return LoginResponse(uid=user.uid, token=token, role=user.role)


@router.post("/logout", response_model=ApiMessage)
async def logout(_: None = Depends(logout_user)) -> ApiMessage:
    return ApiMessage(message="Logged out")


@router.get("/me", response_model=User)
async def me(user: User = Depends(get_current_user)) -> User:
    return user
