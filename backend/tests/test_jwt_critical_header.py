"""Regression contracts for fail-closed JOSE critical-header handling."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import HTTPException

from app import auth


def test_jwt_header_without_critical_extensions_remains_supported() -> None:
    """Return the normalized algorithm when no critical extension is declared."""

    assert auth._validate_jwt_header({"alg": "rs256"}) == "RS256"


@pytest.mark.parametrize(
    "critical_value",
    (
        None,
        "extension_name",
        [],
        [1],
        [""],
        ["extension_name", "extension_name"],
    ),
)
def test_jwt_header_rejects_malformed_critical_lists(
    critical_value: Any,
) -> None:
    """Reject null, non-array, empty, non-text, blank, and duplicate lists."""

    with pytest.raises(HTTPException) as error:
        auth._validate_jwt_header(
            {"alg": "RS256", "crit": critical_value},
        )

    assert error.value.status_code == 401
    assert error.value.detail == "invalid crit header"


@pytest.mark.parametrize("registered_name", ("alg", "typ", "cty", "crit"))
def test_jwt_header_rejects_registered_names_as_critical(
    registered_name: str,
) -> None:
    """Reject base JOSE parameters that RFC 7515 forbids in ``crit``."""

    header: dict[str, Any] = {
        "alg": "RS256",
        "crit": [registered_name],
    }
    if registered_name not in header:
        header[registered_name] = "extension_value"

    with pytest.raises(HTTPException) as error:
        auth._validate_jwt_header(header)

    assert error.value.status_code == 401
    assert error.value.detail == "invalid crit header"


def test_jwt_header_rejects_b64_as_registered_critical_name() -> None:
    """Reject RFC 7797 ``b64`` because this profile does not process it."""

    with pytest.raises(HTTPException) as error:
        auth._validate_jwt_header(
            {"alg": "RS256", "b64": False, "crit": ["b64"]},
        )

    assert error.value.status_code == 401
    assert error.value.detail == "invalid crit header"


def test_jwt_header_rejects_critical_name_missing_from_header() -> None:
    """Reject a critical extension name that has no matching header member."""

    with pytest.raises(HTTPException) as error:
        auth._validate_jwt_header(
            {"alg": "RS256", "crit": ["extension_name"]},
        )

    assert error.value.status_code == 401
    assert error.value.detail == "invalid crit header"


def test_jwt_header_rejects_structurally_valid_unsupported_extension() -> None:
    """Reject an extension that is present but unsupported by this profile."""

    with pytest.raises(HTTPException) as error:
        auth._validate_jwt_header(
            {
                "alg": "RS256",
                "crit": ["https://example.invalid/jose/extension"],
                "https://example.invalid/jose/extension": True,
            },
        )

    assert error.value.status_code == 401
    assert error.value.detail == "unsupported critical parameter"


@pytest.mark.asyncio
async def test_malformed_critical_header_rejection_precedes_jwks_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject malformed critical metadata before any signing-key I/O."""

    monkeypatch.setattr(
        auth.jwt,
        "get_unverified_header",
        lambda _token: {"alg": "RS256", "crit": []},
    )

    async def fail_jwks(*_args: object, **_kwargs: object) -> dict[str, object]:
        """Fail if malformed protected metadata crosses the validation boundary."""

        raise AssertionError("JWKS must not load for malformed critical headers")

    monkeypatch.setattr(auth, "_get_jwks", fail_jwks)

    with pytest.raises(HTTPException) as error:
        await auth._decode_verified_oidc_token("header.payload.signature")

    assert error.value.status_code == 401
    assert error.value.detail == "invalid crit header"


@pytest.mark.asyncio
async def test_critical_extension_rejection_precedes_jwks_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject an unsupported critical extension before any signing-key I/O."""

    critical_name = "https://example.invalid/jose/extension"
    monkeypatch.setattr(
        auth.jwt,
        "get_unverified_header",
        lambda _token: {
            "alg": "RS256",
            "crit": [critical_name],
            critical_name: True,
        },
    )

    async def fail_jwks(*_args: object, **_kwargs: object) -> dict[str, object]:
        """Fail if the rejected token crosses the pre-key validation boundary."""

        raise AssertionError("JWKS must not load for unsupported critical headers")

    monkeypatch.setattr(auth, "_get_jwks", fail_jwks)

    with pytest.raises(HTTPException) as error:
        await auth._decode_verified_oidc_token("header.payload.signature")

    assert error.value.status_code == 401
    assert error.value.detail == "unsupported critical parameter"


@pytest.mark.asyncio
async def test_jwk_algorithm_metadata_must_match_token_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject a JWK whose declared algorithm conflicts with the token header."""

    monkeypatch.setattr(auth, "OIDC_ALLOWED_ALGORITHMS", ("RS256", "RS384"))
    monkeypatch.setattr(
        auth.jwt,
        "get_unverified_header",
        lambda _token: {"kid": "key-1", "alg": "RS256"},
    )

    async def fake_jwks(*_args: object, **_kwargs: object) -> dict[str, object]:
        return {
            "keys": [
                {"kid": "key-1", "kty": "RSA", "alg": "RS384"},
            ]
        }

    monkeypatch.setattr(auth, "_get_jwks", fake_jwks)

    def fail_key_construction(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("mismatched JWK alg must fail before key construction")

    monkeypatch.setattr(auth.jwt.PyJWK, "from_dict", fail_key_construction)

    with pytest.raises(HTTPException) as error:
        await auth._decode_verified_oidc_token("header.payload.signature")

    assert error.value.status_code == 401
    assert error.value.detail == "algorithm/key type mismatch"
