from __future__ import annotations

import base64
import json
import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import HTTPException

from app.license_gate import require_active_license
from app.settings import settings


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _public_key_value(private_key: Ed25519PrivateKey) -> str:
    raw = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return _b64url(raw)


def _signed_license_token(
    private_key: Ed25519PrivateKey,
    payload: dict[str, object],
) -> str:
    encoded_payload = _b64url(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signing_input = f"v1.{encoded_payload}".encode("ascii")
    signature = private_key.sign(signing_input)
    return f"v1.{encoded_payload}.{_b64url(signature)}"


def test_license_gate_skips_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "license_mode", "off")
    monkeypatch.setattr(settings, "license_key", "x" * 64)
    monkeypatch.setattr(settings, "license_revoked_token_ids", "")
    monkeypatch.setattr(settings, "license_revoked_subjects", "")

    require_active_license(x_license_key=None)


def test_license_gate_rejects_missing_license_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "license_mode", "required")
    monkeypatch.setattr(settings, "license_key", "x" * 32)
    monkeypatch.setattr(settings, "license_public_key", None)
    monkeypatch.setattr(settings, "license_revoked_token_ids", "")
    monkeypatch.setattr(settings, "license_revoked_subjects", "")

    with pytest.raises(HTTPException) as exc_info:
        require_active_license(x_license_key=None)

    assert exc_info.value.status_code == 403


def test_license_gate_rejects_wrong_license_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "license_mode", "required")
    monkeypatch.setattr(settings, "license_key", "x" * 32)
    monkeypatch.setattr(settings, "license_public_key", None)
    monkeypatch.setattr(settings, "license_revoked_token_ids", "")
    monkeypatch.setattr(settings, "license_revoked_subjects", "")

    with pytest.raises(HTTPException) as exc_info:
        require_active_license(x_license_key="wrong-key")

    assert exc_info.value.status_code == 403


def test_license_gate_rejects_when_mode_is_required_but_key_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "license_mode", "required")
    monkeypatch.setattr(settings, "license_key", None)
    monkeypatch.setattr(settings, "license_public_key", None)
    monkeypatch.setattr(settings, "license_revoked_token_ids", "")
    monkeypatch.setattr(settings, "license_revoked_subjects", "")

    with pytest.raises(HTTPException) as exc_info:
        require_active_license(x_license_key="anything")

    assert exc_info.value.status_code == 500


def test_license_gate_accepts_valid_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "license_mode", "required")
    monkeypatch.setattr(settings, "license_key", "x" * 32)
    monkeypatch.setattr(settings, "license_public_key", None)
    monkeypatch.setattr(settings, "license_revoked_token_ids", "")
    monkeypatch.setattr(settings, "license_revoked_subjects", "")

    require_active_license(x_license_key="x" * 32)


def test_license_gate_accepts_signed_on_prem_license_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_key = Ed25519PrivateKey.generate()
    monkeypatch.setattr(settings, "license_mode", "required")
    monkeypatch.setattr(settings, "license_key", None)
    monkeypatch.setattr(settings, "license_public_key", _public_key_value(private_key))
    monkeypatch.setattr(settings, "license_revoked_token_ids", "")
    monkeypatch.setattr(settings, "license_revoked_subjects", "")

    token = _signed_license_token(
        private_key,
        {
            "sub": "customer-acme",
            "plan": "enterprise",
            "jti": "license-2026-07",
            "exp": int(time.time()) + 3600,
            "seats": 25,
        },
    )

    require_active_license(x_license_key=token)


def test_license_gate_rejects_expired_signed_license_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_key = Ed25519PrivateKey.generate()
    monkeypatch.setattr(settings, "license_mode", "required")
    monkeypatch.setattr(settings, "license_key", None)
    monkeypatch.setattr(settings, "license_public_key", _public_key_value(private_key))
    monkeypatch.setattr(settings, "license_revoked_token_ids", "")
    monkeypatch.setattr(settings, "license_revoked_subjects", "")

    token = _signed_license_token(
        private_key,
        {
            "sub": "customer-acme",
            "plan": "enterprise",
            "exp": int(time.time()) - 1,
        },
    )

    with pytest.raises(HTTPException) as exc_info:
        require_active_license(x_license_key=token)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "license token is expired"


def test_license_gate_rejects_tampered_signed_license_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_key = Ed25519PrivateKey.generate()
    monkeypatch.setattr(settings, "license_mode", "required")
    monkeypatch.setattr(settings, "license_key", None)
    monkeypatch.setattr(settings, "license_public_key", _public_key_value(private_key))
    monkeypatch.setattr(settings, "license_revoked_token_ids", "")
    monkeypatch.setattr(settings, "license_revoked_subjects", "")

    token = _signed_license_token(
        private_key,
        {
            "sub": "customer-acme",
            "plan": "enterprise",
            "exp": int(time.time()) + 3600,
        },
    )
    version, _payload, signature = token.split(".")
    tampered_payload = _b64url(
        json.dumps(
            {
                "sub": "customer-acme",
                "plan": "enterprise-plus",
                "exp": int(time.time()) + 3600,
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    )

    with pytest.raises(HTTPException) as exc_info:
        require_active_license(x_license_key=f"{version}.{tampered_payload}.{signature}")

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "license token signature is invalid"


def test_license_gate_rejects_revoked_signed_license_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_key = Ed25519PrivateKey.generate()
    monkeypatch.setattr(settings, "license_mode", "required")
    monkeypatch.setattr(settings, "license_key", None)
    monkeypatch.setattr(settings, "license_public_key", _public_key_value(private_key))
    monkeypatch.setattr(settings, "license_revoked_token_ids", "license-2026-07")
    monkeypatch.setattr(settings, "license_revoked_subjects", "")

    token = _signed_license_token(
        private_key,
        {
            "sub": "customer-acme",
            "plan": "enterprise",
            "jti": "license-2026-07",
            "exp": int(time.time()) + 3600,
        },
    )

    with pytest.raises(HTTPException) as exc_info:
        require_active_license(x_license_key=token)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "license token is revoked"


def test_license_gate_rejects_signed_license_with_padded_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_key = Ed25519PrivateKey.generate()
    monkeypatch.setattr(settings, "license_mode", "required")
    monkeypatch.setattr(settings, "license_key", None)
    monkeypatch.setattr(settings, "license_public_key", _public_key_value(private_key))
    monkeypatch.setattr(settings, "license_revoked_token_ids", "license-2026-07")
    monkeypatch.setattr(settings, "license_revoked_subjects", "")

    token = _signed_license_token(
        private_key,
        {
            "sub": "customer-acme",
            "plan": "enterprise",
            "jti": " license-2026-07 ",
            "exp": int(time.time()) + 3600,
        },
    )

    with pytest.raises(HTTPException) as exc_info:
        require_active_license(x_license_key=token)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "license token payload is invalid"


def test_license_gate_rejects_revoked_license_subject(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_key = Ed25519PrivateKey.generate()
    monkeypatch.setattr(settings, "license_mode", "required")
    monkeypatch.setattr(settings, "license_key", None)
    monkeypatch.setattr(settings, "license_public_key", _public_key_value(private_key))
    monkeypatch.setattr(settings, "license_revoked_token_ids", "")
    monkeypatch.setattr(settings, "license_revoked_subjects", "customer-acme")

    token = _signed_license_token(
        private_key,
        {
            "sub": "customer-acme",
            "plan": "enterprise",
            "jti": "license-2026-08",
            "exp": int(time.time()) + 3600,
        },
    )

    with pytest.raises(HTTPException) as exc_info:
        require_active_license(x_license_key=token)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "license token is revoked"
