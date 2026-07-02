from __future__ import annotations

import base64
import binascii
import hmac
import json
import time
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from fastapi import Header, HTTPException

from app.settings import settings

LICENSE_HEADER_NAME = "X-LICENSE-KEY"
LICENSE_TOKEN_VERSION = "v1"
LICENSE_TOKEN_MAX_LENGTH = 16_384


class LicenseConfigurationError(ValueError):
    """Raised when required-mode licensing is misconfigured."""


class LicenseValidationError(ValueError):
    """Raised when a provided license token is not valid for this deployment."""


def _license_required() -> bool:
    """Return whether license enforcement is currently active."""
    return settings.license_mode == "required"


def _normalize_key(value: str | None) -> str:
    return value.strip() if value else ""


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    try:
        return base64.b64decode(
            (value + padding).encode("ascii"),
            altchars=b"-_",
            validate=True,
        )
    except (binascii.Error, UnicodeEncodeError, ValueError) as exc:
        raise LicenseValidationError("license token payload is invalid") from exc


def _load_ed25519_public_key(value: str | None) -> Ed25519PublicKey:
    key_text = (value or "").strip().replace("\\n", "\n")
    if not key_text:
        raise LicenseConfigurationError(
            "license verification key is not configured for required mode"
        )

    if "-----BEGIN" in key_text:
        try:
            loaded_key = load_pem_public_key(key_text.encode("utf-8"))
        except ValueError as exc:
            raise LicenseConfigurationError(
                "license verification key must be an Ed25519 public key"
            ) from exc
        if not isinstance(loaded_key, Ed25519PublicKey):
            raise LicenseConfigurationError(
                "license verification key must be an Ed25519 public key"
            )
        return loaded_key

    try:
        raw_key = _b64url_decode(key_text)
    except LicenseValidationError as exc:
        raise LicenseConfigurationError(
            "license verification key must be an Ed25519 public key"
        ) from exc
    try:
        return Ed25519PublicKey.from_public_bytes(raw_key)
    except ValueError as exc:
        raise LicenseConfigurationError(
            "license verification key must be an Ed25519 public key"
        ) from exc


def _require_str_claim(payload: dict[str, Any], claim: str) -> None:
    value = payload.get(claim)
    if not isinstance(value, str) or not value.strip():
        raise LicenseValidationError("license token payload is invalid")


def _require_positive_int_claim(payload: dict[str, Any], claim: str) -> int:
    value = payload.get(claim)
    if not isinstance(value, int) or value <= 0:
        raise LicenseValidationError("license token payload is invalid")
    return value


def _validate_license_payload(payload: dict[str, Any], *, now: int) -> None:
    _require_str_claim(payload, "sub")
    _require_str_claim(payload, "plan")

    expires_at = _require_positive_int_claim(payload, "exp")
    if expires_at <= now:
        raise LicenseValidationError("license token is expired")

    not_before = payload.get("nbf")
    if not_before is not None:
        if not isinstance(not_before, int):
            raise LicenseValidationError("license token payload is invalid")
        if not_before > now:
            raise LicenseValidationError("license token is not yet valid")

    seats = payload.get("seats")
    if seats is not None and (not isinstance(seats, int) or seats <= 0):
        raise LicenseValidationError("license token payload is invalid")


def _validate_signed_license_token(
    token: str,
    public_key_value: str | None,
    *,
    now: int | None = None,
) -> None:
    if len(token) > LICENSE_TOKEN_MAX_LENGTH:
        raise LicenseValidationError("license token payload is invalid")

    parts = token.split(".")
    if len(parts) != 3 or parts[0] != LICENSE_TOKEN_VERSION:
        raise LicenseValidationError("license token payload is invalid")

    public_key = _load_ed25519_public_key(public_key_value)
    signing_input = f"{parts[0]}.{parts[1]}".encode("ascii")
    signature = _b64url_decode(parts[2])
    try:
        public_key.verify(signature, signing_input)
    except InvalidSignature as exc:
        raise LicenseValidationError("license token signature is invalid") from exc

    payload_bytes = _b64url_decode(parts[1])
    try:
        decoded = json.loads(payload_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LicenseValidationError("license token payload is invalid") from exc
    if not isinstance(decoded, dict):
        raise LicenseValidationError("license token payload is invalid")

    _validate_license_payload(decoded, now=now or int(time.time()))


def _matches_static_license_key(candidate: str) -> bool:
    expected = settings.license_key
    return expected is not None and hmac.compare_digest(candidate, expected)


def require_active_license(
    x_license_key: str | None = Header(default=None, alias=LICENSE_HEADER_NAME),
) -> None:
    """Reject requests without a valid license key when required."""
    if not _license_required():
        return

    if not (settings.license_key or settings.license_public_key):
        # This indicates a deployment misconfiguration in required mode.
        raise HTTPException(
            status_code=500,
            detail="license key is not configured for required mode",
        )

    candidate = _normalize_key(x_license_key)
    if not candidate:
        raise HTTPException(status_code=403, detail="invalid or missing license key")

    if candidate.startswith(f"{LICENSE_TOKEN_VERSION}."):
        try:
            _validate_signed_license_token(candidate, settings.license_public_key)
        except LicenseConfigurationError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except LicenseValidationError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        return

    if _matches_static_license_key(candidate):
        return

    raise HTTPException(status_code=403, detail="invalid or missing license key")
