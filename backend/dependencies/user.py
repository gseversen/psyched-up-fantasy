from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.user import User
from backend.db.session import get_session


async def get_current_user(
    session: AsyncSession = Depends(get_session),
    x_user_id: int | None = Header(default=None, alias="X-User-Id"),
) -> User:
    if x_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-User-Id header",
        )
    user = await session.get(User, x_user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unknown user",
        )
    return user
