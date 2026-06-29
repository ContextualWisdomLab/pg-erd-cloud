from __future__ import annotations


from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user
from app.db import get_session
from app.models import UserAccount
from app.schemas import MeOut, UserUpdate

router = APIRouter(prefix="/api", tags=["me"])


@router.get("/me", response_model=MeOut)
async def get_me(user: CurrentUser = Depends(get_current_user)) -> MeOut:
    """Return the current user's identity."""
    return MeOut(
        user_account_uuid=user.user_account_uuid,
        subject=user.subject,
        display_name=user.display_name,
    )


@router.patch("/me", response_model=MeOut)
async def update_me(
    update_data: UserUpdate,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MeOut:
    """Update the current user's details."""
    async with session.begin():
        db_user = await session.get(UserAccount, user.user_account_uuid)
        if db_user:
            if update_data.display_name is not None:
                db_user.display_name = update_data.display_name

        # Note: if user is cached in auth, this doesn't invalidate cache,
        # but the request returns the updated data. In a real app we might
        # want to invalidate or update the cache.
        display_name = (
            update_data.display_name
            if update_data.display_name is not None
            else user.display_name
        )
        return MeOut(
            user_account_uuid=user.user_account_uuid,
            subject=user.subject,
            display_name=display_name,
        )
