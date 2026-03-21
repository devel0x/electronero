from collections.abc import Callable

from fastapi import Depends, HTTPException, status

from .auth import get_current_user
from .models import Role, User


def require_role(roles: list[Role]) -> Callable:
    async def _dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return user

    return _dependency
