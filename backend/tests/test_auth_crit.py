import pytest
from fastapi import HTTPException
from app.auth import _decode_verified_oidc_token
import jwt

@pytest.mark.asyncio
async def test_decode_verified_oidc_token_with_unsupported_crit(monkeypatch):
    monkeypatch.setattr(jwt, "get_unverified_header", lambda x: {"alg": "RS256", "crit": ["zkp"]})

    with pytest.raises(HTTPException) as excinfo:
        await _decode_verified_oidc_token("dummy_token")

    assert excinfo.value.status_code == 401
    assert excinfo.value.detail == "critical header not understood"

@pytest.mark.asyncio
async def test_decode_verified_oidc_token_with_supported_crit(monkeypatch):
    monkeypatch.setattr(jwt, "get_unverified_header", lambda x: {"alg": "RS256", "crit": ["typ", "alg"]})

    # We expect it to fail later (e.g. invalid signature), but not on the crit check
    with pytest.raises(HTTPException) as excinfo:
        # Mock _validate_jwt_header to pass, so it goes to jwt.PyJWK
        monkeypatch.setattr("app.auth._validate_jwt_header", lambda x: "RS256")

        async def mock_get_jwks(force_refresh=False):
            return {"keys": []}
        monkeypatch.setattr("app.auth._get_jwks", mock_get_jwks)

        # Then we expect it to fail on finding JWK
        await _decode_verified_oidc_token("dummy_token")

    assert excinfo.value.status_code == 401
    assert excinfo.value.detail == "unknown signing key"

@pytest.mark.asyncio
async def test_decode_verified_oidc_token_with_no_crit(monkeypatch):
    monkeypatch.setattr(jwt, "get_unverified_header", lambda x: {"alg": "RS256"})

    # We expect it to fail later (e.g. invalid signature), but not on the crit check
    with pytest.raises(HTTPException) as excinfo:
        # Mock _validate_jwt_header to pass, so it goes to jwt.PyJWK
        monkeypatch.setattr("app.auth._validate_jwt_header", lambda x: "RS256")

        async def mock_get_jwks(force_refresh=False):
            return {"keys": []}
        monkeypatch.setattr("app.auth._get_jwks", mock_get_jwks)

        # Then we expect it to fail on finding JWK
        await _decode_verified_oidc_token("dummy_token")

    assert excinfo.value.status_code == 401
    assert excinfo.value.detail == "unknown signing key"
