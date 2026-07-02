from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth import CurrentUser, get_current_user
from app.schemas import MeOut
from app.settings import settings

router = APIRouter(prefix="/api", tags=["me"])


def _split_csv(value: str) -> set[str]:
    return {item.strip() for item in value.split(",") if item.strip()}


@router.get("/me", response_model=MeOut)
async def get_me(user: CurrentUser = Depends(get_current_user)) -> MeOut:
    """Return the current user's identity."""
    return MeOut(
        user_account_uuid=user.user_account_uuid,
        subject=user.subject,
        display_name=user.display_name,
        support_operator=user.subject in _split_csv(settings.support_operator_subjects),
    )
