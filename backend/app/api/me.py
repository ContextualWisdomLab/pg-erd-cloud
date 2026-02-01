from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth import CurrentUser, get_current_user
from app.schemas import MeOut


router = APIRouter(prefix="/api", tags=["me"])


@router.get("/me", response_model=MeOut)
async def get_me(user: CurrentUser = Depends(get_current_user)) -> MeOut:
    """Return the current user's identity."""
    return MeOut(
        user_account_uuid=user.user_account_uuid,
        subject=user.subject,
        display_name=user.display_name,
    )
