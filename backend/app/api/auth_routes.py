from __future__ import annotations

from fastapi import APIRouter, Request

from app.auth import revoke_current_request_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/logout")
async def logout(request: Request) -> dict[str, bool]:
    """Invalidate the current bearer token for this app process."""

    await revoke_current_request_token(request)
    return {"ok": True}
