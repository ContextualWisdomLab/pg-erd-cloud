import pytest
import time
from app.rate_limit import RateLimitPolicy, ValkeyFixedWindowRateLimiter, _get_client_ip, make_rate_limit_middleware
from starlette.responses import Response
from unittest.mock import AsyncMock, patch
from starlette.requests import Request

@pytest.mark.asyncio
async def test_valkey_rate_limiter_positive():
    limiter = ValkeyFixedWindowRateLimiter(key_prefix="test_rl:")
    policy = RateLimitPolicy(
        enabled=True,
        requests=2,
        window_seconds=1.0,
    )

    mock_client = AsyncMock()
    mock_client.incr.return_value = 1

    with patch("app.rate_limit._client", return_value=mock_client), \
         patch("app.rate_limit._close_client") as mock_close:
        allowed, retry = await limiter.hit(key="test1", policy=policy)
        assert allowed
        mock_client.incr.assert_called_once()
        mock_client.expire.assert_called_once()
        mock_close.assert_called_once_with(mock_client)

@pytest.mark.asyncio
async def test_valkey_rate_limiter_limit_exceeded():
    limiter = ValkeyFixedWindowRateLimiter(key_prefix="test_rl:")
    policy = RateLimitPolicy(
        enabled=True,
        requests=2,
        window_seconds=1.0,
    )

    mock_client = AsyncMock()
    mock_client.incr.return_value = 3

    with patch("app.rate_limit._client", return_value=mock_client):
        allowed, retry = await limiter.hit(key="test1", policy=policy)
        assert not allowed

@pytest.mark.asyncio
async def test_valkey_rate_limiter_disabled():
    limiter = ValkeyFixedWindowRateLimiter(key_prefix="test_rl:")
    policy = RateLimitPolicy(enabled=True, requests=2, window_seconds=0.0)
    allowed, retry = await limiter.hit(key="test1", policy=policy)
    assert allowed
    assert retry == 0

    policy2 = RateLimitPolicy(enabled=True, requests=0, window_seconds=1.0)
    allowed2, retry2 = await limiter.hit(key="test1", policy=policy2)
    assert not allowed2
    assert retry2 == 1

@pytest.mark.asyncio
async def test_valkey_rate_limiter_client_failure():
    limiter = ValkeyFixedWindowRateLimiter(key_prefix="test_rl:")
    policy = RateLimitPolicy(enabled=True, requests=2, window_seconds=1.0)

    # test connection failure
    with patch("app.rate_limit._client", side_effect=Exception("Failed to connect")):
        allowed, retry = await limiter.hit(key="test1", policy=policy)
        assert allowed
        assert retry == 0

    # test command failure
    mock_client = AsyncMock()
    mock_client.incr.side_effect = Exception("Command failed")
    with patch("app.rate_limit._client", return_value=mock_client):
        allowed, retry = await limiter.hit(key="test1", policy=policy)
        assert allowed
        assert retry == 0

def test_get_client_ip_with_trusted_proxy():
    scope = {
        "type": "http",
        "headers": [(b"x-forwarded-for", b"1.1.1.1, 2.2.2.2, 3.3.3.3")],
        "client": ("10.0.0.1", 1234),
    }
    request = Request(scope)

    # Proxy is trusted
    ip = _get_client_ip(
        request,
        trust_x_forwarded_for=True,
        trusted_proxies=["10.0.0.1", "10.0.0.2"],
    )
    assert ip == "3.3.3.3"

    # Proxy is NOT trusted
    ip_not_trusted = _get_client_ip(
        request,
        trust_x_forwarded_for=True,
        trusted_proxies=["192.168.1.1"],
    )
    assert ip_not_trusted == "10.0.0.1"

    # Missing proxy info but trust_x_forwarded_for is true
    scope2 = {
        "type": "http",
        "headers": [(b"x-forwarded-for", b"1.1.1.1")],
        "client": None, "path": "/hello",
    }
    ip2 = _get_client_ip(
        Request(scope2),
        trust_x_forwarded_for=True,
        trusted_proxies=["10.0.0.1"],
    )
    # Since client is None, client_host is "unknown", which is not in trusted_proxies.
    # Therefore, it will not trust the proxy and fall back to "unknown".
    assert ip2 == "unknown"

def test_get_client_ip_empty_xff():
    scope = {
        "type": "http",
        "headers": [(b"x-forwarded-for", b" , , ")],
        "client": ("10.0.0.1", 1234),
    }
    request = Request(scope)
    ip = _get_client_ip(request, trust_x_forwarded_for=True, trusted_proxies=None)
    assert ip == "10.0.0.1"


@pytest.mark.asyncio
async def test_make_rate_limit_middleware_with_valkey():
    limiter = ValkeyFixedWindowRateLimiter(key_prefix="test_rl:")
    policy = RateLimitPolicy(enabled=True, requests=2, window_seconds=1.0)

    async def get_subject(request):
        return "user1"

    middleware = make_rate_limit_middleware(
        limiter=limiter,
        policy=policy,
        get_subject=get_subject
    )

    # Needs to run a mock request
    scope = {
        "type": "http",
        "headers": [(b"x-forwarded-for", b"1.1.1.1")],
        "client": ("10.0.0.1", 1234),
        "path": "/api/test",
    }
    request = Request(scope)

    async def call_next(req):
        return Response()

    mock_client = AsyncMock()
    mock_client.incr.return_value = 1

    with patch("app.rate_limit._client", return_value=mock_client):
        response = await middleware(request, call_next)
        assert response.status_code == 200

@pytest.mark.asyncio
async def test_make_rate_limit_middleware_with_subject_exception():
    limiter = ValkeyFixedWindowRateLimiter(key_prefix="test_rl:")
    policy = RateLimitPolicy(enabled=True, requests=2, window_seconds=1.0)

    async def get_subject(request):
        raise ValueError("Cannot derive subject")

    middleware = make_rate_limit_middleware(
        limiter=limiter,
        policy=policy,
        get_subject=get_subject
    )

    scope = {
        "type": "http",
        "headers": [],
        "client": ("10.0.0.1", 1234),
        "path": "/api/test",
    }
    request = Request(scope)

    async def call_next(req):
        return Response()

    mock_client = AsyncMock()
    mock_client.incr.return_value = 1

    with patch("app.rate_limit._client", return_value=mock_client):
        response = await middleware(request, call_next)
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_make_rate_limit_middleware_with_disabled():
    limiter = ValkeyFixedWindowRateLimiter(key_prefix="test_rl:")
    policy = RateLimitPolicy(enabled=False, requests=2, window_seconds=1.0)

    middleware = make_rate_limit_middleware(
        limiter=limiter,
        policy=policy,
    )

    scope = {
        "type": "http",
        "headers": [],
        "client": ("10.0.0.1", 1234),
        "path": "/api/test",
    }
    request = Request(scope)

    async def call_next(req):
        return Response()

    response = await middleware(request, call_next)
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_make_rate_limit_middleware_with_wrong_prefix():
    limiter = ValkeyFixedWindowRateLimiter(key_prefix="test_rl:")
    policy = RateLimitPolicy(enabled=True, requests=2, window_seconds=1.0, route_prefix="/api")

    middleware = make_rate_limit_middleware(
        limiter=limiter,
        policy=policy,
    )

    scope = {
        "type": "http",
        "headers": [],
        "client": ("10.0.0.1", 1234),
        "path": "/static/test",
    }
    request = Request(scope)

    async def call_next(req):
        return Response()

    response = await middleware(request, call_next)
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_in_memory_eviction():
    from app.rate_limit import InMemoryFixedWindowRateLimiter, RateLimitPolicy
    import time

    limiter = InMemoryFixedWindowRateLimiter(max_keys=2)
    policy = RateLimitPolicy(enabled=True, requests=2, window_seconds=1.0)

    await limiter.hit(key="k1", policy=policy)
    await limiter.hit(key="k2", policy=policy)
    # eviction should remove oldest key
    await limiter.hit(key="k3", policy=policy)

    assert "k3" in limiter._buckets


@pytest.mark.asyncio
async def test_in_memory_eviction_expired():
    from app.rate_limit import InMemoryFixedWindowRateLimiter, RateLimitPolicy
    import time

    limiter = InMemoryFixedWindowRateLimiter(max_keys=2)
    policy = RateLimitPolicy(enabled=True, requests=2, window_seconds=0.1)

    await limiter.hit(key="k1", policy=policy)
    await limiter.hit(key="k2", policy=policy)

    time.sleep(0.15)

    # eviction should remove expired keys
    await limiter.hit(key="k3", policy=policy)

    assert "k1" not in limiter._buckets
    assert "k2" not in limiter._buckets

@pytest.mark.asyncio
async def test_in_memory_eviction_no_expired():
    from app.rate_limit import InMemoryFixedWindowRateLimiter, RateLimitPolicy
    import time

    limiter = InMemoryFixedWindowRateLimiter(max_keys=2)
    policy = RateLimitPolicy(enabled=True, requests=2, window_seconds=10.0)

    await limiter.hit(key="k1", policy=policy)
    await limiter.hit(key="k2", policy=policy)

    # eviction should remove oldest key (k1)
    await limiter.hit(key="k3", policy=policy)

    assert "k1" not in limiter._buckets
    assert "k2" in limiter._buckets
    assert "k3" in limiter._buckets

@pytest.mark.asyncio
async def test_in_memory_hit_disabled():
    from app.rate_limit import InMemoryFixedWindowRateLimiter, RateLimitPolicy

    limiter = InMemoryFixedWindowRateLimiter(max_keys=2)
    policy = RateLimitPolicy(enabled=True, requests=2, window_seconds=0.0)
    allowed, retry = await limiter.hit(key="k1", policy=policy)
    assert allowed

    policy2 = RateLimitPolicy(enabled=True, requests=0, window_seconds=1.0)
    allowed2, retry2 = await limiter.hit(key="k1", policy=policy2)
    assert not allowed2

@pytest.mark.asyncio
async def test_in_memory_hit_count_increment():
    from app.rate_limit import InMemoryFixedWindowRateLimiter, RateLimitPolicy

    limiter = InMemoryFixedWindowRateLimiter(max_keys=2)
    policy = RateLimitPolicy(enabled=True, requests=2, window_seconds=10.0)
    allowed, retry = await limiter.hit(key="k1", policy=policy)
    assert allowed

    allowed2, retry2 = await limiter.hit(key="k1", policy=policy)
    assert allowed2

    allowed3, retry3 = await limiter.hit(key="k1", policy=policy)
    assert not allowed3


def test_in_memory_constructor_error():
    from app.rate_limit import InMemoryFixedWindowRateLimiter
    with pytest.raises(ValueError):
        InMemoryFixedWindowRateLimiter(max_keys=0)


def test_get_client_ip_empty_xff_with_proxy():
    scope = {
        "type": "http",
        "headers": [(b"x-forwarded-for", b"")],
        "client": ("10.0.0.1", 1234),
    }
    request = Request(scope)
    ip = _get_client_ip(request, trust_x_forwarded_for=True, trusted_proxies=None)
    assert ip == "10.0.0.1"

def test_get_client_ip_unknown_logging():
    from unittest.mock import patch
    import time

    scope = {
        "type": "http",
        "headers": [],
        "client": None,
        "path": "/hello"
    }
    request = Request(scope)

    with patch("app.rate_limit.time.monotonic", return_value=time.monotonic() + 100):
        ip = _get_client_ip(request, trust_x_forwarded_for=False, trusted_proxies=None)
        assert ip == "unknown"


def test_get_client_ip_unknown_logging_throttle():
    from unittest.mock import patch
    import time

    scope = {
        "type": "http",
        "headers": [],
        "client": None,
        "path": "/hello"
    }
    request = Request(scope)

    # Should skip logging because not enough time has passed
    with patch("app.rate_limit.time.monotonic", return_value=0):
        ip = _get_client_ip(request, trust_x_forwarded_for=False, trusted_proxies=None)
        assert ip == "unknown"
