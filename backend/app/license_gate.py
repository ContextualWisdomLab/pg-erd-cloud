from __future__ import annotations

import hmac

from fastapi import Header, HTTPException

from app.settings import settings

LICENSE_HEADER_NAME = "X-LICENSE-KEY"


def _license_required() -> bool:
    """Return whether license enforcement is currently active."""
    return settings.license_mode == "required"


def _normalize_key(value: str | None) -> str:
    return value.strip() if value else ""


def require_active_license(
    x_license_key: str | None = Header(default=None, alias=LICENSE_HEADER_NAME),
) -> None:
    """Reject requests without a valid license key when required."""
    if not _license_required():
        return

    if not settings.license_key:
        # This indicates a deployment misconfiguration in required mode.
        raise HTTPException(
            status_code=500, detail="license key is not configured for required mode"
        )

    candidate = _normalize_key(x_license_key)
    if not candidate or not hmac.compare_digest(candidate, settings.license_key):
        raise HTTPException(status_code=403, detail="invalid or missing license key")
