import jwt
import pytest
from fastapi import HTTPException

from app.auth import _decode_verified_oidc_token


async def _empty_jwks(force_refresh=False):
    return {"keys": []}


@pytest.mark.asyncio
async def test_decode_verified_oidc_token_with_unsupported_crit(monkeypatch):
    monkeypatch.setattr(
        jwt,
        "get_unverified_header",
        lambda x: {"alg": "RS256", "crit": ["zkp"]},
    )

    with pytest.raises(HTTPException) as excinfo:
        await _decode_verified_oidc_token("dummy_token")

    assert excinfo.value.status_code == 401
    assert excinfo.value.detail == "critical header not understood"


@pytest.mark.asyncio
async def test_decode_verified_oidc_token_rejects_registered_header_as_critical(
    monkeypatch,
):
    monkeypatch.setattr(
        jwt,
        "get_unverified_header",
        lambda x: {"alg": "RS256", "typ": "JWT", "crit": ["typ", "alg"]},
    )
    monkeypatch.setattr("app.auth._get_jwks", _empty_jwks)

    with pytest.raises(HTTPException) as excinfo:
        await _decode_verified_oidc_token("dummy_token")

    assert excinfo.value.status_code == 401
    assert excinfo.value.detail == "critical header not understood"


@pytest.mark.asyncio
async def test_decode_verified_oidc_token_rejects_null_crit(monkeypatch):
    monkeypatch.setattr(
        jwt,
        "get_unverified_header",
        lambda x: {"alg": "RS256", "crit": None},
    )
    monkeypatch.setattr("app.auth._get_jwks", _empty_jwks)

    with pytest.raises(HTTPException) as excinfo:
        await _decode_verified_oidc_token("dummy_token")

    assert excinfo.value.status_code == 401
    assert excinfo.value.detail == "critical header must be a list"


@pytest.mark.asyncio
async def test_decode_verified_oidc_token_rejects_empty_crit(monkeypatch):
    monkeypatch.setattr(
        jwt,
        "get_unverified_header",
        lambda x: {"alg": "RS256", "crit": []},
    )
    monkeypatch.setattr("app.auth._get_jwks", _empty_jwks)

    with pytest.raises(HTTPException) as excinfo:
        await _decode_verified_oidc_token("dummy_token")

    assert excinfo.value.status_code == 401
    assert excinfo.value.detail == "critical header must not be empty"


@pytest.mark.asyncio
async def test_decode_verified_oidc_token_with_no_crit(monkeypatch):
    monkeypatch.setattr(jwt, "get_unverified_header", lambda x: {"alg": "RS256"})
    monkeypatch.setattr("app.auth._validate_jwt_header", lambda x: "RS256")
    monkeypatch.setattr("app.auth._get_jwks", _empty_jwks)

    with pytest.raises(HTTPException) as excinfo:
        await _decode_verified_oidc_token("dummy_token")

    assert excinfo.value.status_code == 401
    assert excinfo.value.detail == "unknown signing key"


@pytest.mark.asyncio
async def test_decode_verified_oidc_token_crit_not_list(monkeypatch):
    monkeypatch.setattr(
        jwt,
        "get_unverified_header",
        lambda x: {"alg": "RS256", "crit": "typ"},
    )
    with pytest.raises(HTTPException) as excinfo:
        await _decode_verified_oidc_token("dummy_token")
    assert excinfo.value.status_code == 401
    assert excinfo.value.detail == "critical header must be a list"


@pytest.mark.asyncio
async def test_decode_verified_oidc_token_crit_too_many(monkeypatch):
    monkeypatch.setattr(
        jwt,
        "get_unverified_header",
        lambda x: {"alg": "RS256", "crit": ["typ"] * 11},
    )
    with pytest.raises(HTTPException) as excinfo:
        await _decode_verified_oidc_token("dummy_token")
    assert excinfo.value.status_code == 401
    assert excinfo.value.detail == "too many critical headers"


@pytest.mark.asyncio
async def test_decode_verified_oidc_token_crit_not_string(monkeypatch):
    monkeypatch.setattr(
        jwt,
        "get_unverified_header",
        lambda x: {"alg": "RS256", "crit": [123]},
    )
    with pytest.raises(HTTPException) as excinfo:
        await _decode_verified_oidc_token("dummy_token")
    assert excinfo.value.status_code == 401
    assert excinfo.value.detail == "critical header must be a string"


@pytest.mark.asyncio
async def test_decode_verified_oidc_token_crit_too_long(monkeypatch):
    monkeypatch.setattr(
        jwt,
        "get_unverified_header",
        lambda x: {"alg": "RS256", "crit": ["a" * 51]},
    )
    with pytest.raises(HTTPException) as excinfo:
        await _decode_verified_oidc_token("dummy_token")
    assert excinfo.value.status_code == 401
    assert excinfo.value.detail == "critical header name too long"
