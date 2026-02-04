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
