from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.rate_limit import (
    InMemoryFixedWindowRateLimiter,
    RateLimitPolicy,
    make_rate_limit_middleware,
)


async def _no_subject(_: Request) -> str | None:
    return None


def test_rate_limit_applies_to_api_prefix_and_returns_429() -> None:
    limiter = InMemoryFixedWindowRateLimiter(max_keys=100)
    policy = RateLimitPolicy(
        enabled=True,
        requests=2,
        window_seconds=60.0,
        route_prefix="/api",
        trust_x_forwarded_for=False,
    )

    app = FastAPI()
    app.middleware("http")(
        make_rate_limit_middleware(
            limiter=limiter,
            policy=policy,
            get_subject=_no_subject,
        )
    )

    @app.get("/api/ping")
    def ping() -> dict[str, bool]:
        return {"ok": True}

    client = TestClient(app)
    assert client.get("/api/ping").status_code == 200
    assert client.get("/api/ping").status_code == 200

    r = client.get("/api/ping")
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) >= 0


def test_rate_limit_does_not_apply_outside_api_prefix() -> None:
    limiter = InMemoryFixedWindowRateLimiter(max_keys=100)
    policy = RateLimitPolicy(
        enabled=True,
        requests=1,
        window_seconds=60.0,
        route_prefix="/api",
        trust_x_forwarded_for=False,
    )

    app = FastAPI()
    app.middleware("http")(
        make_rate_limit_middleware(
            limiter=limiter,
            policy=policy,
            get_subject=_no_subject,
        )
    )

    @app.get("/healthz")
    def healthz() -> dict[str, bool]:
        return {"ok": True}

    client = TestClient(app)
    for _ in range(5):
        assert client.get("/healthz").status_code == 200


def test_rate_limit_separates_by_subject_when_provided() -> None:
    limiter = InMemoryFixedWindowRateLimiter(max_keys=100)
    policy = RateLimitPolicy(
        enabled=True,
        requests=1,
        window_seconds=60.0,
        route_prefix="/api",
        trust_x_forwarded_for=False,
    )

    async def get_subject(request: Request) -> str | None:
        return request.headers.get("X-Subject")

    app = FastAPI()
    app.middleware("http")(
        make_rate_limit_middleware(
            limiter=limiter,
            policy=policy,
            get_subject=get_subject,
        )
    )

    @app.get("/api/ping")
    def ping() -> dict[str, bool]:
        return {"ok": True}

    client = TestClient(app)

    # subject A: first ok, second blocked
    assert (
        client.get("/api/ping", headers={"X-Subject": "a"}).status_code == 200
    )
    assert (
        client.get("/api/ping", headers={"X-Subject": "a"}).status_code == 429
    )

    # subject B: independent key -> first ok
    assert (
        client.get("/api/ping", headers={"X-Subject": "b"}).status_code == 200
    )
    assert (
        client.get("/api/ping", headers={"X-Subject": "b"}).status_code == 429
    )


def test_rate_limit_disabled_allows_all_requests() -> None:
    limiter = InMemoryFixedWindowRateLimiter(max_keys=100)
    policy = RateLimitPolicy(
        enabled=False,
        requests=1,
        window_seconds=60.0,
        route_prefix="/api",
        trust_x_forwarded_for=False,
    )

    app = FastAPI()
    app.middleware("http")(
        make_rate_limit_middleware(
            limiter=limiter,
            policy=policy,
            get_subject=_no_subject,
        )
    )

    @app.get("/api/ping")
    def ping() -> dict[str, bool]:
        return {"ok": True}

    client = TestClient(app)
    for _ in range(5):
        assert client.get("/api/ping").status_code == 200


def test_rate_limit_trusts_x_forwarded_for_when_enabled() -> None:
    limiter = InMemoryFixedWindowRateLimiter(max_keys=100)
    policy = RateLimitPolicy(
        enabled=True,
        requests=1,
        window_seconds=60.0,
        route_prefix="/api",
        trust_x_forwarded_for=True,
    )

    app = FastAPI()
    app.middleware("http")(
        make_rate_limit_middleware(
            limiter=limiter,
            policy=policy,
            get_subject=_no_subject,
        )
    )

    @app.get("/api/ping")
    def ping() -> dict[str, bool]:
        return {"ok": True}

    client = TestClient(app)
    assert (
        client.get(
            "/api/ping", headers={"X-Forwarded-For": "1.1.1.1"}
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/api/ping", headers={"X-Forwarded-For": "1.1.1.1"}
        ).status_code
        == 429
    )
    assert (
        client.get(
            "/api/ping", headers={"X-Forwarded-For": "2.2.2.2"}
        ).status_code
        == 200
    )


def test_share_prefix_can_have_tighter_public_limit() -> None:
    general_limiter = InMemoryFixedWindowRateLimiter(max_keys=100)
    share_limiter = InMemoryFixedWindowRateLimiter(max_keys=100)
    general_policy = RateLimitPolicy(
        enabled=True,
        requests=10,
        window_seconds=60.0,
        route_prefix="/api",
        trust_x_forwarded_for=False,
    )
    share_policy = RateLimitPolicy(
        enabled=True,
        requests=1,
        window_seconds=60.0,
        route_prefix="/api/share",
        trust_x_forwarded_for=False,
    )

    app = FastAPI()
    app.middleware("http")(
        make_rate_limit_middleware(
            limiter=general_limiter,
            policy=general_policy,
            get_subject=_no_subject,
        )
    )
    app.middleware("http")(
        make_rate_limit_middleware(
            limiter=share_limiter,
            policy=share_policy,
        )
    )

    @app.get("/api/share/{share_link_uuid}")
    def share(share_link_uuid: str) -> dict[str, bool]:
        return {"ok": bool(share_link_uuid)}

    @app.get("/api/projects")
    def projects() -> dict[str, bool]:
        return {"ok": True}

    client = TestClient(app)
    assert client.get("/api/share/abc").status_code == 200
    assert client.get("/api/share/abc").status_code == 429
    assert client.get("/api/projects").status_code == 200
