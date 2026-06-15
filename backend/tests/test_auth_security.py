from __future__ import annotations

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app import auth
from app.settings import settings


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("RS256", ["RS256"]),
        ("rs256, ES256", ["RS256", "ES256"]),
        ("RS256, rs256", ["RS256"]),
        ("none, RS256", ["RS256"]),
        ("none", ["RS256"]),
        (", , ", ["RS256"]),
    ],
)
def test_parse_oidc_algorithms(raw: str, expected: list[str]) -> None:
    assert auth._parse_oidc_algorithms(raw) == expected


def make_request(headers: dict[str, str] | None = None) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/me",
            "headers": [
                (name.lower().encode("latin1"), value.encode("latin1"))
                for name, value in (headers or {}).items()
            ],
        }
    )


def exp_claim() -> int:
    return int(auth.dt.datetime.now(auth.dt.timezone.utc).timestamp()) + 300


@pytest.mark.asyncio
async def test_oidc_rejects_header_selected_algorithm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(auth, "OIDC_ALLOWED_ALGORITHMS", ("RS256",))
    monkeypatch.setattr(settings, "oidc_issuer", "https://issuer.example")
    monkeypatch.setattr(settings, "oidc_audience", "pg-erd")
    monkeypatch.setattr(
        auth.jwt, "get_unverified_header", lambda _: {"kid": "key-1", "alg": "HS256"}
    )

    async def fake_jwks() -> dict:
        return {"keys": [{"kid": "key-1", "kty": "RSA"}]}

    monkeypatch.setattr(auth, "_get_jwks", fake_jwks)

    def fail_decode(*_: object, **__: object) -> dict:
        raise AssertionError("jwt.decode must not run for unsupported algorithms")

    monkeypatch.setattr(auth.jwt, "decode", fail_decode)

    with pytest.raises(HTTPException) as exc_info:
        await auth._get_subject_from_request(
            make_request({"Authorization": "Bearer token"})
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "unsupported token algorithm"


@pytest.mark.asyncio
async def test_oidc_decode_uses_fixed_algorithm_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(auth, "OIDC_ALLOWED_ALGORITHMS", ("RS256",))
    monkeypatch.setattr(settings, "oidc_issuer", "https://issuer.example")
    monkeypatch.setattr(settings, "oidc_audience", "pg-erd")
    monkeypatch.setattr(
        auth.jwt, "get_unverified_header", lambda _: {"kid": "key-1", "alg": "RS256"}
    )

    async def fake_jwks() -> dict:
        return {"keys": [{"kid": "key-1", "kty": "RSA"}]}

    observed: dict[str, object] = {}

    def fake_decode(*args: object, **kwargs: object) -> dict:
        observed["args"] = args
        observed["kwargs"] = kwargs
        return {"sub": "user-1", "name": "User One", "jti": "jwt-1", "exp": exp_claim()}

    monkeypatch.setattr(auth, "_get_jwks", fake_jwks)
    monkeypatch.setattr(auth.jwt, "decode", fake_decode)

    subject, display_name = await auth._get_subject_from_request(
        make_request({"Authorization": "Bearer token"})
    )

    assert subject == "user-1"
    assert display_name == "User One"
    assert observed["kwargs"] == {
        "algorithms": ["RS256"],
        "audience": "pg-erd",
        "issuer": "https://issuer.example",
        "options": {"verify_aud": True, "require_exp": True, "require_jti": True},
    }


@pytest.mark.asyncio
async def test_oidc_requires_jti_claim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "oidc_issuer", "https://issuer.example")
    monkeypatch.setattr(settings, "oidc_audience", "pg-erd")
    monkeypatch.setattr(
        auth.jwt, "get_unverified_header", lambda _: {"kid": "key-1", "alg": "RS256"}
    )

    async def fake_jwks() -> dict:
        return {"keys": [{"kid": "key-1", "kty": "RSA"}]}

    monkeypatch.setattr(auth, "_get_jwks", fake_jwks)
    monkeypatch.setattr(
        auth.jwt,
        "decode",
        lambda *_args, **_kwargs: {"sub": "user-1", "exp": exp_claim()},
    )

    with pytest.raises(HTTPException) as exc_info:
        await auth._get_subject_from_request(
            make_request({"Authorization": "Bearer token"})
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "token missing jti"


@pytest.mark.asyncio
async def test_oidc_rejects_revoked_jti(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "oidc_issuer", "https://issuer.example")
    monkeypatch.setattr(settings, "oidc_audience", "pg-erd")
    monkeypatch.setattr(
        auth.jwt, "get_unverified_header", lambda _: {"kid": "key-1", "alg": "RS256"}
    )

    async def fake_jwks() -> dict:
        return {"keys": [{"kid": "key-1", "kty": "RSA"}]}

    expires_at = auth.dt.datetime.now(auth.dt.timezone.utc) + auth.dt.timedelta(
        minutes=5
    )
    monkeypatch.setattr(auth, "_get_jwks", fake_jwks)
    monkeypatch.setattr(
        auth.jwt,
        "decode",
        lambda *_args, **_kwargs: {
            "sub": "user-1",
            "jti": "revoked-jwt",
            "exp": int(expires_at.timestamp()),
        },
    )
    auth.revoke_token_jti("revoked-jwt", expires_at)

    with pytest.raises(HTTPException) as exc_info:
        await auth._get_subject_from_request(
            make_request({"Authorization": "Bearer token"})
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "token revoked"


@pytest.mark.asyncio
async def test_auth_fails_closed_without_oidc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "oidc_issuer", None)

    with pytest.raises(HTTPException) as exc_info:
        await auth._get_subject_from_request(make_request({"X-Dev-User": "local"}))

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "OIDC configuration required"
