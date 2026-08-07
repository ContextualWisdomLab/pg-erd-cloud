"""Complete behavioral coverage for the in-memory API rate limiter."""

from __future__ import annotations

import pytest
from starlette.requests import Request
from starlette.responses import Response

from app import rate_limit


class _Clock:
    """Module-like deterministic monotonic clock."""

    def __init__(self, *values: float) -> None:
        self.values = list(values)

    def monotonic(self) -> float:
        """Return values in order and retain the final value thereafter."""
        if len(self.values) > 1:
            return self.values.pop(0)
        return self.values[0]


class _Limiter:
    """Middleware-facing limiter double with one configured decision."""

    def __init__(self, allowed: bool, retry_after: int = 0) -> None:
        self.allowed = allowed
        self.retry_after = retry_after
        self.calls: list[tuple[str, rate_limit.RateLimitPolicy]] = []

    async def hit(
        self,
        *,
        key: str,
        policy: rate_limit.RateLimitPolicy,
    ) -> tuple[bool, int]:
        """Record the rate-limit key and return the configured decision."""
        self.calls.append((key, policy))
        return self.allowed, self.retry_after


def _request(
    *,
    path: str = "/api/resource",
    client: tuple[str, int] | None = ("127.0.0.1", 12345),
    headers: list[tuple[bytes, bytes]] | None = None,
) -> Request:
    """Construct a minimal Starlette request for middleware tests."""
    return Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "https",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": headers or [],
            "client": client,
            "server": ("testserver", 443),
            "root_path": "",
        }
    )


def _policy(**overrides: object) -> rate_limit.RateLimitPolicy:
    """Return a normal API policy with selected fields overridden."""
    values: dict[str, object] = {
        "enabled": True,
        "requests": 2,
        "window_seconds": 10.0,
        "route_prefix": "/api",
        "trust_x_forwarded_for": False,
    }
    values.update(overrides)
    return rate_limit.RateLimitPolicy(**values)  # type: ignore[arg-type]


def test_client_ip_uses_trusted_nearest_proxy_and_falls_back_to_socket() -> None:
    """Use the right-most trusted proxy value and ignore empty terminal values."""
    forwarded = _request(
        headers=[(b"x-forwarded-for", b"198.51.100.1, 203.0.113.9")]
    )
    assert (
        rate_limit._get_client_ip(forwarded, trust_x_forwarded_for=True)
        == "203.0.113.9"
    )

    empty_terminal = _request(
        client=("192.0.2.44", 12345),
        headers=[(b"x-forwarded-for", b"198.51.100.1,   ")],
    )
    assert (
        rate_limit._get_client_ip(empty_terminal, trust_x_forwarded_for=True)
        == "192.0.2.44"
    )

    whitespace_only = _request(
        client=("192.0.2.45", 12345),
        headers=[(b"x-forwarded-for", b"   ")],
    )
    assert (
        rate_limit._get_client_ip(whitespace_only, trust_x_forwarded_for=True)
        == "192.0.2.45"
    )


def test_client_ip_unknown_logging_is_throttled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Warn once per throttle period when no request client identity exists."""
    warnings: list[tuple[object, ...]] = []

    def warning(*args: object, **_kwargs: object) -> None:
        warnings.append(args)

    monkeypatch.setattr(rate_limit, "_last_unknown_ip_log_at", 0.0)
    monkeypatch.setattr(rate_limit, "time", _Clock(100.0, 110.0))
    monkeypatch.setattr(rate_limit._logger, "warning", warning)
    request = _request(client=None)

    assert rate_limit._get_client_ip(request, trust_x_forwarded_for=False) == "unknown"
    assert rate_limit._get_client_ip(request, trust_x_forwarded_for=False) == "unknown"
    assert len(warnings) == 1


def test_client_ip_empty_socket_host_is_unknown_without_immediate_repeat_log(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Normalize an empty socket host to unknown and respect the existing throttle."""
    monkeypatch.setattr(rate_limit, "_last_unknown_ip_log_at", 95.0)
    monkeypatch.setattr(rate_limit, "time", _Clock(100.0))
    warnings: list[object] = []
    monkeypatch.setattr(
        rate_limit._logger,
        "warning",
        lambda *args, **_kwargs: warnings.append(args),
    )

    assert (
        rate_limit._get_client_ip(
            _request(client=("", 12345)),
            trust_x_forwarded_for=False,
        )
        == "unknown"
    )
    assert warnings == []


def test_limiter_rejects_nonpositive_capacity() -> None:
    """Require a positive bounded number of tracked identities."""
    with pytest.raises(ValueError, match="max_keys must be positive"):
        rate_limit.InMemoryFixedWindowRateLimiter(max_keys=0)


@pytest.mark.asyncio
async def test_limiter_handles_disabled_window_and_zero_request_policy() -> None:
    """Avoid division by zero and give a bounded retry for an explicit zero quota."""
    limiter = rate_limit.InMemoryFixedWindowRateLimiter(max_keys=2)

    assert await limiter.hit(key="ip:a", policy=_policy(window_seconds=0.0)) == (
        True,
        0,
    )
    assert await limiter.hit(key="ip:a", policy=_policy(requests=0)) == (False, 10)


@pytest.mark.asyncio
async def test_limiter_counts_hits_and_resets_on_new_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject excess hits in one window and reset the identity in the next window."""
    limiter = rate_limit.InMemoryFixedWindowRateLimiter(max_keys=2)
    monkeypatch.setattr(rate_limit, "time", _Clock(1.0, 2.0, 11.0))
    policy = _policy(requests=1, window_seconds=10.0)

    assert await limiter.hit(key="ip:a", policy=policy) == (True, 9)
    allowed, retry_after = await limiter.hit(key="ip:a", policy=policy)
    assert allowed is False
    assert retry_after == 8
    assert await limiter.hit(key="ip:a", policy=policy) == (True, 9)


@pytest.mark.asyncio
async def test_limiter_evicts_expired_keys_before_current_window_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prefer removing stale windows when admitting a new identity at capacity."""
    limiter = rate_limit.InMemoryFixedWindowRateLimiter(max_keys=2)
    limiter._buckets = {"expired": (0, 1), "current": (1, 1)}
    monkeypatch.setattr(rate_limit, "time", _Clock(15.0))

    allowed, _ = await limiter.hit(key="new", policy=_policy(window_seconds=10.0))

    assert allowed is True
    assert "expired" not in limiter._buckets
    assert set(limiter._buckets) == {"current", "new"}


@pytest.mark.asyncio
async def test_limiter_evicts_oldest_current_key_when_all_entries_are_live(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bound memory with deterministic insertion-order eviction when no key is expired."""
    limiter = rate_limit.InMemoryFixedWindowRateLimiter(max_keys=2)
    limiter._buckets = {"oldest": (1, 1), "newer": (1, 1)}
    monkeypatch.setattr(rate_limit, "time", _Clock(15.0))

    await limiter.hit(key="new", policy=_policy(window_seconds=10.0))

    assert "oldest" not in limiter._buckets
    assert set(limiter._buckets) == {"newer", "new"}


@pytest.mark.asyncio
async def test_middleware_bypasses_disabled_and_out_of_scope_requests() -> None:
    """Avoid consuming limiter state when policy is disabled or path is outside scope."""
    calls: list[str] = []

    async def call_next(_request: Request) -> Response:
        calls.append("next")
        return Response("ok", status_code=204)

    disabled_limiter = _Limiter(False, 99)
    disabled = rate_limit.make_rate_limit_middleware(
        limiter=disabled_limiter,  # type: ignore[arg-type]
        policy=_policy(enabled=False),
    )
    assert (await disabled(_request(), call_next)).status_code == 204
    assert disabled_limiter.calls == []

    scoped_limiter = _Limiter(False, 99)
    scoped = rate_limit.make_rate_limit_middleware(
        limiter=scoped_limiter,  # type: ignore[arg-type]
        policy=_policy(route_prefix="/api"),
    )
    assert (
        await scoped(_request(path="/healthz"), call_next)
    ).status_code == 204
    assert scoped_limiter.calls == []
    assert calls == ["next", "next"]


@pytest.mark.asyncio
async def test_middleware_uses_subject_key_when_derivation_succeeds() -> None:
    """Combine network and authenticated-subject evidence for an allowed request."""
    limiter = _Limiter(True)

    async def subject(_request: Request) -> str:
        return "buyer-subject"

    async def call_next(_request: Request) -> Response:
        return Response("ok", status_code=200)

    middleware = rate_limit.make_rate_limit_middleware(
        limiter=limiter,  # type: ignore[arg-type]
        policy=_policy(),
        get_subject=subject,
    )
    response = await middleware(_request(client=("192.0.2.10", 12345)), call_next)

    assert response.status_code == 200
    assert limiter.calls[0][0] == "ip:192.0.2.10|sub:buyer-subject"


@pytest.mark.asyncio
async def test_middleware_contains_subject_failure_and_returns_rate_limit_response() -> None:
    """Fall back to the IP key when subject derivation fails and preserve Retry-After."""
    limiter = _Limiter(False, retry_after=7)

    async def failing_subject(_request: Request) -> str:
        raise RuntimeError("private token detail")

    async def call_next(_request: Request) -> Response:
        raise AssertionError("rejected requests must not reach the application")

    middleware = rate_limit.make_rate_limit_middleware(
        limiter=limiter,  # type: ignore[arg-type]
        policy=_policy(),
        get_subject=failing_subject,
    )
    response = await middleware(_request(client=("192.0.2.11", 12345)), call_next)

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "7"
    assert response.body == b'{"detail":"rate limit exceeded"}'
    assert limiter.calls[0][0] == "ip:192.0.2.11"
