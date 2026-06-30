from __future__ import annotations


from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
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
async def patch_me(
    user_update: UserUpdate,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MeOut:
    """Update the current user's details."""
    stmt = select(UserAccount).where(
        UserAccount.user_account_uuid == user.user_account_uuid
    )
    result = await session.execute(stmt)
    user_account = result.scalar_one_or_none()

    if not user_account:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = user_update.model_dump(exclude_unset=True)
    if "display_name" in update_data:
        user_account.display_name = update_data["display_name"]

    await session.commit()

    return MeOut(
        user_account_uuid=user_account.user_account_uuid,
        subject=user_account.oidc_subject,
        display_name=user_account.display_name,
    )
