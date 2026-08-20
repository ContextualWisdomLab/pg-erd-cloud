"""Regression tests for OIDC JWK algorithm binding."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app import auth
from app.settings import settings


@pytest.mark.asyncio
@pytest.mark.parametrize("jwk_algorithm", ["RS256", 256])
async def test_oidc_rejects_mismatched_or_non_text_jwk_algorithm(
    monkeypatch: pytest.MonkeyPatch,
    jwk_algorithm: object,
) -> None:
    """Reject a present JWK alg that is non-text or differs from the JWT header."""

    monkeypatch.setattr(auth, "OIDC_ALLOWED_ALGORITHMS", ("RS256", "RS512"))
    monkeypatch.setattr(settings, "oidc_issuer", "https://issuer.example")
    monkeypatch.setattr(settings, "oidc_audience", "pg-erd")
    monkeypatch.setattr(
        auth.jwt,
        "get_unverified_header",
        lambda _: {"kid": "key-1", "alg": "RS512"},
    )

    async def fake_jwks(force_refresh: bool = False) -> dict[str, object]:
        """Return a key whose declared algorithm must bind verification."""

        del force_refresh
        return {
            "keys": [
                {
                    "kid": "key-1",
                    "kty": "RSA",
                    "alg": jwk_algorithm,
                }
            ]
        }

    class DummyPyJWK:
        """Provide the legacy raw-key path without real key material."""

        key = "dummy-key"

    def fake_pyjwk(_jwk: dict[str, object]) -> DummyPyJWK:
        """Return a key wrapper accepted by the predecessor implementation."""

        return DummyPyJWK()

    def fail_decode(*_args: object, **_kwargs: object) -> dict[str, object]:
        """Fail if verification reaches PyJWT despite the JWK mismatch."""

        raise AssertionError("jwt.decode must not run for a mismatched JWK alg")

    monkeypatch.setattr(auth, "_get_jwks", fake_jwks)
    monkeypatch.setattr(auth.jwt, "PyJWK", fake_pyjwk)
    monkeypatch.setattr(auth.jwt, "decode", fail_decode)

    with pytest.raises(HTTPException) as exc_info:
        await auth._decode_verified_oidc_token("header.payload.signature")

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "algorithm/key type mismatch"
