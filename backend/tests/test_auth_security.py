from __future__ import annotations

import asyncio
import uuid

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
        ("HS256, RS256", ["RS256"]),
        ("RS256, hs256", ["RS256"]),
        ("HS256, HS384, HS512", ["RS256"]),
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


class _FakeHttpResponse:
    def __init__(self, payload: dict[str, object], is_redirect: bool = False) -> None:
        self._payload = payload
        self.is_redirect = is_redirect
        self.raise_for_status_called = False

    def raise_for_status(self) -> None:
        self.raise_for_status_called = True

    def json(self) -> dict[str, object]:
        return self._payload


@pytest.mark.asyncio
async def test_oidc_config_fetch_disables_redirects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = _FakeHttpResponse({"jwks_uri": "https://issuer.example/jwks"})
    observed: dict[str, object] = {}

    class FakeAsyncClient:
        def __init__(self, **kwargs: object) -> None:
            observed.update(kwargs)

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def get(self, url: str) -> _FakeHttpResponse:
            observed["url"] = url
            return response

    monkeypatch.setattr(settings, "oidc_issuer", "https://issuer.example/")
    monkeypatch.setattr(auth.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(auth, "_oidc_config", None)
    monkeypatch.setattr(
        auth,
        "_oidc_config_expires_at",
        auth.dt.datetime.fromtimestamp(0, tz=auth.dt.timezone.utc),
    )

    config = await auth._get_oidc_config()

    assert config == {"jwks_uri": "https://issuer.example/jwks"}
    assert observed["timeout"] == 5
    assert observed["follow_redirects"] is False
    assert observed["url"] == "https://issuer.example/.well-known/openid-configuration"
    assert response.raise_for_status_called is True


@pytest.mark.asyncio
async def test_oidc_config_rejects_redirect_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = _FakeHttpResponse({"jwks_uri": "https://issuer.example/jwks"}, True)

    class FakeAsyncClient:
        def __init__(self, **_kwargs: object) -> None:
            return None

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def get(self, _url: str) -> _FakeHttpResponse:
            return response

    monkeypatch.setattr(settings, "oidc_issuer", "https://issuer.example")
    monkeypatch.setattr(auth.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(auth, "_oidc_config", None)
    monkeypatch.setattr(
        auth,
        "_oidc_config_expires_at",
        auth.dt.datetime.fromtimestamp(0, tz=auth.dt.timezone.utc),
    )

    with pytest.raises(RuntimeError, match="must not redirect"):
        await auth._get_oidc_config()

    assert response.raise_for_status_called is False


@pytest.mark.asyncio
async def test_jwks_fetch_disables_redirects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = _FakeHttpResponse({"keys": []})
    observed: dict[str, object] = {}

    async def fake_config() -> dict[str, object]:
        return {"jwks_uri": "https://issuer.example/jwks"}

    class FakeAsyncClient:
        def __init__(self, **kwargs: object) -> None:
            observed.update(kwargs)

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def get(self, url: str) -> _FakeHttpResponse:
            observed["url"] = url
            return response

    monkeypatch.setattr(auth, "_get_oidc_config", fake_config)
    monkeypatch.setattr(auth.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(auth, "_oidc_jwks", None)
    monkeypatch.setattr(
        auth,
        "_oidc_jwks_expires_at",
        auth.dt.datetime.fromtimestamp(0, tz=auth.dt.timezone.utc),
    )

    jwks = await auth._get_jwks()

    assert jwks == {"keys": []}
    assert observed["timeout"] == 5
    assert observed["follow_redirects"] is False
    assert observed["url"] == "https://issuer.example/jwks"
    assert response.raise_for_status_called is True


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

    async def mock_is_token_revoked2(jti):
        return jti == "revoked-jwt"

    monkeypatch.setattr(auth, "is_token_jti_revoked", mock_is_token_revoked2)

    def fail_decode(*_: object, **__: object) -> dict:
        raise AssertionError("jwt.decode must not run for unsupported algorithms")

    monkeypatch.setattr(auth.jwt, "decode", fail_decode)
    monkeypatch.setattr(auth.jwt, "PyJWK", lambda _: type("DummyKey", (), {"key": "dummy"})())


    with pytest.raises(HTTPException) as exc_info:
        await auth._get_subject_from_request(
            make_request({"Authorization": "Bearer token"})
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "unsupported token algorithm"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "jwk",
    [
        {"kid": "key-1", "kty": "EC"},
        {"kid": "key-1", "kty": "oct"},
        {"kid": "key-1"},
    ],
)
async def test_oidc_decode_rejects_kty_mismatch(
    monkeypatch: pytest.MonkeyPatch,
    jwk: dict[str, object],
) -> None:
    monkeypatch.setattr(auth, "OIDC_ALLOWED_ALGORITHMS", ("RS256",))
    monkeypatch.setattr(settings, "oidc_issuer", "https://issuer.example")
    monkeypatch.setattr(settings, "oidc_audience", "pg-erd")
    monkeypatch.setattr(
        auth.jwt, "get_unverified_header", lambda _: {"kid": "key-1", "alg": "RS256"}
    )

    async def fake_jwks() -> dict:
        return {"keys": [jwk]}

    monkeypatch.setattr(auth, "_get_jwks", fake_jwks)

    def fail_decode(*_: object, **__: object) -> dict:
        raise AssertionError("jwt.decode must not run for mismatched key types")

    monkeypatch.setattr(auth.jwt, "decode", fail_decode)
    monkeypatch.setattr(auth.jwt, "PyJWK", lambda _: type("DummyKey", (), {"key": "dummy"})())


    with pytest.raises(HTTPException) as exc_info:
        await auth._decode_verified_oidc_token("ey...fake...")

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "algorithm/key type mismatch"


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

    async def mock_is_token_revoked2(jti):
        return jti == "revoked-jwt"

    monkeypatch.setattr(auth, "is_token_jti_revoked", mock_is_token_revoked2)
    monkeypatch.setattr(auth.jwt, "decode", fake_decode)

    def dummy_pyjwk(jwk):
        observed["jwk"] = jwk
        return type("DummyKey", (), {"key": "dummy"})()
    monkeypatch.setattr(auth.jwt, "PyJWK", dummy_pyjwk)



    async def mock_is_token_revoked(jti):
        return jti == "revoked-jwt"

    monkeypatch.setattr(auth, "is_token_jti_revoked", mock_is_token_revoked)

    subject, display_name = await auth._get_subject_from_request(
        make_request({"Authorization": "Bearer token"})
    )

    assert subject == "user-1"
    assert display_name == "User One"
    assert observed["kwargs"] == {
        "algorithms": ["RS256"],
        "audience": "pg-erd",
        "issuer": "https://issuer.example",
        "leeway": auth.OIDC_JWT_LEEWAY_SECONDS,
        "options": {
            "verify_aud": True,
            "verify_iss": True,
            "verify_exp": True,
            "verify_jti": True,
            "require": ["exp", "iss", "jti", "aud"],
        },
    }


@pytest.mark.parametrize(
    ("header", "detail"),
    [
        (
            {"kid": "key-1", "alg": "RS256", "typ": "nested+jwt"},
            "unsupported token type",
        ),
        (
            {"kid": "key-1", "alg": "RS256", "cty": "JWT"},
            "unsupported token content type",
        ),
    ],
)
@pytest.mark.asyncio
async def test_oidc_rejects_unsupported_header_types(
    monkeypatch: pytest.MonkeyPatch, header: dict[str, str], detail: str
) -> None:
    monkeypatch.setattr(settings, "oidc_issuer", "https://issuer.example")
    monkeypatch.setattr(settings, "oidc_audience", "pg-erd")
    monkeypatch.setattr(auth.jwt, "get_unverified_header", lambda _: header)

    async def fail_jwks() -> dict:
        raise AssertionError("JWKS must not load for unsupported token headers")

    monkeypatch.setattr(auth, "_get_jwks", fail_jwks)

    with pytest.raises(HTTPException) as exc_info:
        await auth._get_subject_from_request(
            make_request({"Authorization": "Bearer token"})
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == detail


@pytest.mark.asyncio
async def test_oidc_refreshes_jwks_when_kid_is_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(auth, "OIDC_ALLOWED_ALGORITHMS", ("RS256",))
    monkeypatch.setattr(settings, "oidc_issuer", "https://issuer.example")
    monkeypatch.setattr(settings, "oidc_audience", "pg-erd")
    monkeypatch.setattr(
        auth.jwt, "get_unverified_header", lambda _: {"kid": "new-key", "alg": "RS256"}
    )

    refresh_calls: list[bool] = []

    async def fake_jwks(force_refresh: bool = False) -> dict:
        refresh_calls.append(force_refresh)
        if force_refresh:
            return {"keys": [{"kid": "new-key", "kty": "RSA"}]}
        return {"keys": [{"kid": "old-key", "kty": "RSA"}]}

    observed: dict[str, object] = {}

    def fake_decode(*args: object, **kwargs: object) -> dict:
        observed["key"] = args[1]
        observed["kwargs"] = kwargs
        return {"sub": "user-1", "name": "User One", "jti": "jwt-1", "exp": exp_claim()}

    monkeypatch.setattr(auth, "_get_jwks", fake_jwks)

    async def mock_is_token_revoked2(jti):
        return jti == "revoked-jwt"

    monkeypatch.setattr(auth, "is_token_jti_revoked", mock_is_token_revoked2)
    monkeypatch.setattr(auth.jwt, "decode", fake_decode)
    def dummy_pyjwk(jwk):
        observed["jwk"] = jwk
        return type("DummyKey", (), {"key": "dummy"})()
    monkeypatch.setattr(auth.jwt, "PyJWK", dummy_pyjwk)


    async def mock_is_token_revoked(jti):
        return jti == "revoked-jwt"

    monkeypatch.setattr(auth, "is_token_jti_revoked", mock_is_token_revoked)

    subject, display_name = await auth._get_subject_from_request(
        make_request({"Authorization": "Bearer token"})
    )

    assert subject == "user-1"
    assert display_name == "User One"
    assert refresh_calls == [False, True]
    assert observed["jwk"] == {"kid": "new-key", "kty": "RSA"}


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

    async def mock_is_token_revoked2(jti):
        return jti == "revoked-jwt"

    monkeypatch.setattr(auth, "is_token_jti_revoked", mock_is_token_revoked2)
    monkeypatch.setattr(
        auth.jwt,
        "decode",
        lambda *_args, **_kwargs: {"sub": "user-1", "exp": exp_claim()},
    )
    monkeypatch.setattr(auth.jwt, "PyJWK", lambda _: type("DummyKey", (), {"key": "dummy"})())

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

    async def mock_is_token_revoked2(jti):
        return jti == "revoked-jwt"

    monkeypatch.setattr(auth, "is_token_jti_revoked", mock_is_token_revoked2)
    monkeypatch.setattr(
        auth.jwt,
        "decode",
        lambda *_args, **_kwargs: {
            "sub": "user-1",
            "jti": "revoked-jwt",
            "exp": int(expires_at.timestamp()),
        },
    )
    monkeypatch.setattr(auth.jwt, "PyJWK", lambda _: type("DummyKey", (), {"key": "dummy"})())

    async def mock_revoke(jti, ext):
        pass

    monkeypatch.setattr(auth, "revoke_token_jti", mock_revoke)
    await auth.revoke_token_jti("revoked-jwt", expires_at)

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


class _FakeScalarResult:
    def __init__(self, user: object | None) -> None:
        self._user = user

    def first(self) -> object | None:
        return self._user


class _FakeExecuteResult:
    def __init__(self, user: object | None) -> None:
        self._user = user

    def scalars(self) -> _FakeScalarResult:
        return _FakeScalarResult(self._user)


class _FakeSession:
    def __init__(self, user: object | None) -> None:
        self._user = user
        self.execute_calls = 0
        self.added: list[object] = []
        self.flush_calls = 0

    async def execute(self, _statement: object) -> _FakeExecuteResult:
        self.execute_calls += 1
        return _FakeExecuteResult(self._user)

    def add(self, value: object) -> None:
        self.added.append(value)

    async def flush(self) -> None:
        self.flush_calls += 1


class _ExistingUser:
    def __init__(self) -> None:
        self.user_account_uuid = uuid.uuid4()
        self.oidc_subject = "subject-1"
        self.display_name = "User One"


@pytest.mark.asyncio
async def test_ensure_user_reuses_short_lived_cache() -> None:
    auth._user_cache.clear()
    try:
        session = _FakeSession(_ExistingUser())

        first = await auth._ensure_user(session, "subject-1", "User One")
        second = await auth._ensure_user(session, "subject-1", "Changed")

        assert first == second
        assert session.execute_calls == 1
        assert session.added == []
        assert session.flush_calls == 0
    finally:
        auth._user_cache.clear()


@pytest.mark.asyncio
async def test_try_get_subject_for_rate_limit_error_path():
    """Verify try_get_subject_for_rate_limit returns None on auth failure."""
    req = make_request()  # No Authorization header

    # We should get None because of the Missing Bearer Token HTTPException
    subject = await auth.try_get_subject_for_rate_limit(req)
    assert subject is None


async def test_oidc_decode_rejects_invalid_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def mock_get_unverified_header(token):
        raise auth.jwt.PyJWTError("Invalid header")

    monkeypatch.setattr(auth.jwt, "get_unverified_header", mock_get_unverified_header)

    with pytest.raises(HTTPException) as excinfo:
        await auth._decode_verified_oidc_token("invalid_token")

    assert excinfo.value.status_code == 401
    assert excinfo.value.detail == "invalid token header"


@pytest.mark.asyncio
async def test_oidc_decode_rejects_jwt_decode_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "oidc_issuer", "https://issuer.example")
    monkeypatch.setattr(settings, "oidc_audience", "pg-erd")
    monkeypatch.setattr(auth, "OIDC_ALLOWED_ALGORITHMS", ("RS256",))
    monkeypatch.setattr(
        auth.jwt, "get_unverified_header", lambda _: {"kid": "key-1", "alg": "RS256"}
    )

    async def fake_jwks() -> dict:
        return {"keys": [{"kid": "key-1", "kty": "RSA"}]}

    def fail_decode(*_args: object, **_kwargs: object) -> dict:
        raise auth.jwt.PyJWTError("mocked decoding error")

    monkeypatch.setattr(auth, "_get_jwks", fake_jwks)

    async def mock_is_token_revoked2(jti):
        return jti == "revoked-jwt"

    monkeypatch.setattr(auth, "is_token_jti_revoked", mock_is_token_revoked2)
    monkeypatch.setattr(auth.jwt, "decode", fail_decode)
    monkeypatch.setattr(auth.jwt, "PyJWK", lambda _: type("DummyKey", (), {"key": "dummy"})())


    with pytest.raises(HTTPException) as exc_info:
        await auth._decode_verified_oidc_token("Bearer token")

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "token verification failed"

@pytest.mark.asyncio
async def test_oidc_rejects_algorithm_key_type_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(auth, "OIDC_ALLOWED_ALGORITHMS", ("HS256", "RS256"))
    monkeypatch.setattr(settings, "oidc_issuer", "https://issuer.example")
    monkeypatch.setattr(settings, "oidc_audience", "pg-erd")
    monkeypatch.setattr(
        auth.jwt, "get_unverified_header", lambda _: {"kid": "key-1", "alg": "HS256"}
    )

    async def fake_jwks() -> dict:
        # JWK says RSA, but header says HS256
        return {"keys": [{"kid": "key-1", "kty": "RSA"}]}

    monkeypatch.setattr(auth, "_get_jwks", fake_jwks)

    async def mock_is_token_revoked2(jti):
        return jti == "revoked-jwt"

    monkeypatch.setattr(auth, "is_token_jti_revoked", mock_is_token_revoked2)

    def fail_decode(*_: object, **__: object) -> dict:
        raise AssertionError("jwt.decode must not run for mismatched algorithm/key type")

    monkeypatch.setattr(auth.jwt, "decode", fail_decode)
    monkeypatch.setattr(auth.jwt, "PyJWK", lambda _: type("DummyKey", (), {"key": "dummy"})())


    with pytest.raises(HTTPException) as exc_info:
        await auth._decode_verified_oidc_token("ey...")

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "algorithm/key type mismatch"
@pytest.mark.asyncio
async def test_oidc_jwks_refresh_rate_limiting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request_count = 0

    class FakeAsyncClient:
        def __init__(self, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def get(self, url: str) -> _FakeHttpResponse:
            nonlocal request_count
            request_count += 1
            if url.endswith("openid-configuration"):
                return _FakeHttpResponse({"jwks_uri": "https://issuer.example/jwks"})
            return _FakeHttpResponse({"keys": [{"kid": "new-key", "kty": "RSA"}]})

    monkeypatch.setattr(settings, "oidc_issuer", "https://issuer.example")
    monkeypatch.setattr(auth.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(auth, "_oidc_config", None)
    monkeypatch.setattr(auth, "_oidc_jwks", None)
    monkeypatch.setattr(
        auth,
        "_oidc_jwks_expires_at",
        auth.dt.datetime.fromtimestamp(0, tz=auth.dt.timezone.utc),
    )
    monkeypatch.setattr(
        auth,
        "_last_jwks_refresh_at",
        auth.dt.datetime.fromtimestamp(0, tz=auth.dt.timezone.utc),
    )

    jwks = await auth._get_jwks()
    assert jwks == {"keys": [{"kid": "new-key", "kty": "RSA"}]}
    assert request_count == 2

    before_second_refresh = request_count
    jwks2 = await auth._get_jwks(force_refresh=True)
    assert jwks2 == {"keys": [{"kid": "new-key", "kty": "RSA"}]}
    assert request_count == before_second_refresh


@pytest.mark.asyncio
async def test_oidc_jwks_force_refresh_is_serialized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request_count = 0

    class FakeAsyncClient:
        def __init__(self, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def get(self, url: str) -> _FakeHttpResponse:
            nonlocal request_count
            request_count += 1
            if url.endswith("openid-configuration"):
                return _FakeHttpResponse({"jwks_uri": "https://issuer.example/jwks"})
            await asyncio.sleep(0)
            return _FakeHttpResponse({"keys": [{"kid": "new-key", "kty": "RSA"}]})

    monkeypatch.setattr(settings, "oidc_issuer", "https://issuer.example")
    monkeypatch.setattr(auth.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(auth, "_oidc_config", None)
    monkeypatch.setattr(auth, "_oidc_jwks", None)
    monkeypatch.setattr(
        auth,
        "_oidc_jwks_expires_at",
        auth.dt.datetime.fromtimestamp(0, tz=auth.dt.timezone.utc),
    )
    monkeypatch.setattr(
        auth,
        "_last_jwks_refresh_at",
        auth.dt.datetime.fromtimestamp(0, tz=auth.dt.timezone.utc),
    )

    await auth._get_jwks()
    before_concurrent_refresh = request_count
    monkeypatch.setattr(
        auth,
        "_last_jwks_refresh_at",
        auth.dt.datetime.fromtimestamp(0, tz=auth.dt.timezone.utc),
    )

    refreshed = await asyncio.gather(
        *(auth._get_jwks(force_refresh=True) for _ in range(5))
    )

    assert refreshed == [
        {"keys": [{"kid": "new-key", "kty": "RSA"}]},
        {"keys": [{"kid": "new-key", "kty": "RSA"}]},
        {"keys": [{"kid": "new-key", "kty": "RSA"}]},
        {"keys": [{"kid": "new-key", "kty": "RSA"}]},
        {"keys": [{"kid": "new-key", "kty": "RSA"}]},
    ]
    assert request_count == before_concurrent_refresh + 1


@pytest.mark.asyncio
async def test_oidc_config_rejects_disabled_issuer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fail before network access when OIDC is disabled."""
    monkeypatch.setattr(settings, "oidc_issuer", None)

    with pytest.raises(RuntimeError, match="OIDC is disabled"):
        await auth._get_oidc_config()


@pytest.mark.asyncio
async def test_jwks_rejects_missing_uri(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reject discovery documents without a string JWKS URI."""

    async def config_without_jwks_uri() -> dict[str, object]:
        return {"jwks_uri": None}

    monkeypatch.setattr(auth, "_get_oidc_config", config_without_jwks_uri)

    with pytest.raises(RuntimeError, match="OIDC jwks_uri missing"):
        await auth._get_jwks()


@pytest.mark.asyncio
async def test_jwks_uses_fresh_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Return a fresh cached key set without opening an HTTP client."""

    async def config() -> dict[str, str]:
        return {"jwks_uri": "https://issuer.example/jwks"}

    monkeypatch.setattr(auth, "_get_oidc_config", config)
    monkeypatch.setattr(auth, "_oidc_jwks", {"keys": [{"kid": "cached"}]})
    monkeypatch.setattr(
        auth,
        "_oidc_jwks_expires_at",
        auth.dt.datetime.now(auth.dt.timezone.utc) + auth.dt.timedelta(minutes=1),
    )

    assert await auth._get_jwks() == {"keys": [{"kid": "cached"}]}


@pytest.mark.asyncio
async def test_jwks_rejects_redirect_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Do not follow redirects when retrieving signing keys."""

    async def config() -> dict[str, str]:
        return {"jwks_uri": "https://issuer.example/jwks"}

    class RedirectingClient:
        def __init__(self, **_kwargs: object) -> None:
            pass

        async def __aenter__(self) -> "RedirectingClient":
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def get(self, _url: str) -> _FakeHttpResponse:
            return _FakeHttpResponse({}, is_redirect=True)

    monkeypatch.setattr(auth, "_get_oidc_config", config)
    monkeypatch.setattr(auth, "_oidc_jwks", None)
    monkeypatch.setattr(auth.httpx, "AsyncClient", RedirectingClient)

    with pytest.raises(RuntimeError, match="OIDC JWKS endpoint must not redirect"):
        await auth._get_jwks()


def test_jwk_selection_and_claim_validation_edge_cases() -> None:
    """Cover malformed key sets and required JWT fields."""
    assert auth._pick_jwk({"keys": "not-a-list"}, "key-1") is None
    assert auth._pick_jwk({"keys": [None, {"kid": "key-1"}]}, "key-1") == {
        "kid": "key-1"
    }
    assert auth._pick_jwk({"keys": [{"kid": "first"}]}, None) == {"kid": "first"}

    with pytest.raises(HTTPException, match="token missing exp"):
        auth._jwt_expiry({})
    with pytest.raises(HTTPException, match="token missing alg"):
        auth._validate_jwt_header({"typ": "jwt"})
    assert auth._validate_jwt_header({"typ": "at+jwt", "alg": "rs256"}) == "RS256"
    with pytest.raises(HTTPException, match="missing bearer token"):
        auth._bearer_token_from_request(make_request())


class _RevocationResult:
    def __init__(self, value: object | None) -> None:
        self._value = value

    def scalar(self) -> object | None:
        return self._value


class _RevocationSession:
    def __init__(self, scalar_value: object | None = None) -> None:
        self.scalar_value = scalar_value
        self.statements: list[object] = []
        self.added: list[object] = []
        self.commits = 0

    async def __aenter__(self) -> "_RevocationSession":
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def execute(self, statement: object) -> _RevocationResult:
        self.statements.append(statement)
        return _RevocationResult(self.scalar_value)

    def add(self, value: object) -> None:
        self.added.append(value)

    async def commit(self) -> None:
        self.commits += 1


@pytest.mark.asyncio
async def test_revocation_store_writes_and_queries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise the durable revocation write and bounded lookup paths."""
    import app.db as db

    write_session = _RevocationSession()
    monkeypatch.setattr(db, "SessionLocal", lambda: write_session)
    expiry = auth.dt.datetime.now(auth.dt.timezone.utc) + auth.dt.timedelta(minutes=5)

    await auth.revoke_token_jti("jwt-1", expiry)

    assert len(write_session.statements) == 1
    assert len(write_session.added) == 1
    assert write_session.added[0].jwt_id == "jwt-1"
    assert write_session.commits == 1

    revoked_session = _RevocationSession("jwt-1")
    monkeypatch.setattr(db, "SessionLocal", lambda: revoked_session)
    assert await auth.is_token_jti_revoked("jwt-1") is True
    assert len(revoked_session.statements) == 1

    active_session = _RevocationSession()
    monkeypatch.setattr(db, "SessionLocal", lambda: active_session)
    assert await auth.is_token_jti_revoked("jwt-2") is False


@pytest.mark.asyncio
async def test_empty_jwt_id_does_not_open_revocation_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ignore an empty identifier without creating a database session."""
    import app.db as db

    def fail_session() -> None:
        raise AssertionError("SessionLocal must not be called")

    monkeypatch.setattr(db, "SessionLocal", fail_session)
    await auth.revoke_token_jti("", auth.dt.datetime.now(auth.dt.timezone.utc))


@pytest.mark.parametrize(
    ("jwk", "algorithm", "expected_detail"),
    [
        ({"kid": "key-1", "kty": "EC"}, "RS256", "algorithm/key type mismatch"),
        ({"kid": "key-1", "kty": "OKP"}, "RS256", "algorithm/key type mismatch"),
    ],
)
@pytest.mark.asyncio
async def test_oidc_rejects_additional_key_type_mismatches(
    monkeypatch: pytest.MonkeyPatch,
    jwk: dict[str, str],
    algorithm: str,
    expected_detail: str,
) -> None:
    """Fail closed for EC/algorithm mismatch and unsupported key types."""
    monkeypatch.setattr(auth, "OIDC_ALLOWED_ALGORITHMS", (algorithm,))
    monkeypatch.setattr(
        auth.jwt,
        "get_unverified_header",
        lambda _token: {"kid": "key-1", "alg": algorithm},
    )

    async def fake_jwks() -> dict[str, list[dict[str, str]]]:
        return {"keys": [jwk]}

    monkeypatch.setattr(auth, "_get_jwks", fake_jwks)

    with pytest.raises(HTTPException) as exc_info:
        await auth._decode_verified_oidc_token("token")

    assert exc_info.value.detail == expected_detail


@pytest.mark.asyncio
async def test_oidc_accepts_ec_key_for_es_algorithm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Allow an EC key only with an explicitly allowed ES algorithm."""
    monkeypatch.setattr(auth, "OIDC_ALLOWED_ALGORITHMS", ("ES256",))
    monkeypatch.setattr(settings, "oidc_audience", None)
    monkeypatch.setattr(settings, "oidc_issuer", "https://issuer.example")
    monkeypatch.setattr(
        auth.jwt,
        "get_unverified_header",
        lambda _token: {"kid": "key-1", "alg": "ES256"},
    )

    async def fake_jwks() -> dict[str, list[dict[str, str]]]:
        return {"keys": [{"kid": "key-1", "kty": "EC"}]}

    monkeypatch.setattr(auth, "_get_jwks", fake_jwks)
    monkeypatch.setattr(
        auth.jwt, "PyJWK", lambda _jwk: type("DummyKey", (), {"key": "dummy"})()
    )
    monkeypatch.setattr(
        auth.jwt,
        "decode",
        lambda *_args, **_kwargs: {
            "sub": "user-1",
            "jti": "jwt-1",
            "exp": exp_claim(),
        },
    )

    claims = await auth._decode_verified_oidc_token("token")

    assert claims["sub"] == "user-1"


@pytest.mark.asyncio
async def test_verified_claims_require_subject_and_rate_limit_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Require a subject and return it on the best-effort rate-limit path."""
    with pytest.raises(HTTPException, match="token missing sub"):
        await auth._verified_token_from_claims({"jti": "jwt-1", "exp": exp_claim()})

    async def verified_subject(
        _request: Request, verify_revocation: bool = True
    ) -> tuple[str, str | None]:
        assert verify_revocation is False
        return "subject-1", None

    monkeypatch.setattr(auth, "_get_subject_from_request", verified_subject)
    assert await auth.try_get_subject_for_rate_limit(make_request()) == "subject-1"


@pytest.mark.asyncio
async def test_ensure_user_replaces_expired_cache_and_creates_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Evict stale cache data, create a user, and bound cache growth."""
    auth._user_cache.clear()
    subject = "subject-new"
    expired_user = auth.CurrentUser(uuid.uuid4(), subject, None)
    auth._user_cache[subject] = (
        expired_user,
        auth.dt.datetime.now(auth.dt.timezone.utc) - auth.dt.timedelta(seconds=1),
    )
    auth._user_cache["other-subject"] = (
        auth.CurrentUser(uuid.uuid4(), "other-subject", None),
        auth.dt.datetime.now(auth.dt.timezone.utc) + auth.dt.timedelta(minutes=1),
    )
    monkeypatch.setattr(auth, "USER_CACHE_MAX_SIZE", 1)
    session = _FakeSession(None)

    user = await auth._ensure_user(session, subject, "New User")

    assert user.subject == subject
    assert user.display_name == "New User"
    assert len(session.added) == 1
    assert session.flush_calls == 1
    assert list(auth._user_cache) == [subject]
    auth._user_cache.clear()


class _BeginContext:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *_args: object) -> None:
        return None


class _CurrentUserSession:
    def begin(self) -> _BeginContext:
        return _BeginContext()


@pytest.mark.asyncio
async def test_current_user_supports_api_key_and_oidc_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dispatch API-key auth directly and provision verified OIDC users."""
    expected = auth.CurrentUser(uuid.uuid4(), "subject-1", "User One")

    async def api_key_user(_session: object, token: str) -> auth.CurrentUser:
        assert token == "pgerd_secret"
        return expected

    monkeypatch.setattr(auth, "_user_from_api_key", api_key_user)
    session = _CurrentUserSession()
    api_request = make_request({"Authorization": "Bearer pgerd_secret"})
    assert await auth.get_current_user(api_request, session) == expected

    async def oidc_subject(_request: Request) -> tuple[str, str | None]:
        return "subject-1", "User One"

    async def ensure_user(
        _session: object, subject: str, display_name: str | None
    ) -> auth.CurrentUser:
        assert (subject, display_name) == ("subject-1", "User One")
        return expected

    monkeypatch.setattr(auth, "_get_subject_from_request", oidc_subject)
    monkeypatch.setattr(auth, "_ensure_user", ensure_user)
    assert await auth.get_current_user(make_request(), session) == expected


@pytest.mark.asyncio
async def test_revoke_current_request_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Revoke the verified request token through the durable helper."""
    expiry = auth.dt.datetime.now(auth.dt.timezone.utc) + auth.dt.timedelta(minutes=5)
    verified = auth.VerifiedToken("subject-1", None, "jwt-1", expiry)
    observed: list[tuple[str, auth.dt.datetime]] = []

    async def get_verified(_request: Request) -> auth.VerifiedToken:
        return verified

    async def revoke(jwt_id: str, expires_at: auth.dt.datetime) -> None:
        observed.append((jwt_id, expires_at))

    monkeypatch.setattr(auth, "_get_verified_token_from_request", get_verified)
    monkeypatch.setattr(auth, "revoke_token_jti", revoke)

    await auth.revoke_current_request_token(make_request())

    assert observed == [("jwt-1", expiry)]
