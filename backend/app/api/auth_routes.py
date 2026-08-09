from __future__ import annotations

from fastapi import APIRouter, Request

from app.auth import revoke_current_request_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/logout")
async def logout(request: Request) -> dict[str, bool]:
    """Revoke the token currently presented by the user."""
    await revoke_current_request_token(request)
    return {"success": True}
