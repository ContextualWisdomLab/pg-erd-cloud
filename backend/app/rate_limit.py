from __future__ import annotations

import asyncio
import logging
import math
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

SubjectGetter = Callable[[Request], Awaitable[str | None]]


_logger = logging.getLogger(__name__)
_UNKNOWN_IP_LOG_THROTTLE_SECONDS = 60.0
_last_unknown_ip_log_at = 0.0


@dataclass(frozen=True)
class RateLimitPolicy:
    """A small, dependency-free fixed-window rate limit policy.

    Notes:
    - This is intentionally in-memory (per-process).
    - In multi-worker/multi-instance deployments, limits are enforced per worker
      unless an external shared store (Redis/Valkey) is introduced.
    """

    enabled: bool
    requests: int
    window_seconds: float
    route_prefix: str = "/api"
    trust_x_forwarded_for: bool = False


def _get_client_ip(request: Request, *, trust_x_forwarded_for: bool) -> str:
    global _last_unknown_ip_log_at

    if trust_x_forwarded_for:
        xff = request.headers.get("X-Forwarded-For")
        if xff:
            # Use the right-most value (nearest trusted proxy), trimming whitespace.
            # This is safer than the left-most which can be spoofed by the client.
            ip = xff.split(",")[-1].strip()
            if ip:
                return ip

    client = request.client
    if client is None:
        ip = "unknown"
    else:
        ip = client.host or "unknown"

    # Avoid silently aggregating many callers under an "unknown" key.
    if ip == "unknown":
        now = time.monotonic()
        if now - _last_unknown_ip_log_at >= _UNKNOWN_IP_LOG_THROTTLE_SECONDS:
            _last_unknown_ip_log_at = now
            _logger.warning(
                "rate_limit: unable to resolve client IP; falling back to 'unknown'"
                " (path=%s, x_forwarded_for_present=%s)",
                request.url.path,
                bool(request.headers.get("X-Forwarded-For")),
            )
    return ip


class InMemoryFixedWindowRateLimiter:
    """A minimal in-memory fixed-window rate limiter."""

    def __init__(self, *, max_keys: int = 10_000) -> None:
        if max_keys <= 0:
            raise ValueError("max_keys must be positive")
        self._max_keys = max_keys
        self._lock = asyncio.Lock()
        # key -> (window_id, count)
        self._buckets: dict[str, tuple[int, int]] = {}

    async def hit(self, *, key: str, policy: RateLimitPolicy) -> tuple[bool, int]:
        """Record a hit and return (allowed, retry_after_seconds)."""
        if policy.window_seconds <= 0:
            # Treat as disabled to avoid division by zero.
            return True, 0
        if policy.requests <= 0:
            # Always reject when configured to 0.
            return False, math.ceil(policy.window_seconds)

        now = time.monotonic()
        window_id = int(now // policy.window_seconds)
        retry_after = int(
            max(0.0, math.ceil((window_id + 1) * policy.window_seconds - now))
        )

        async with self._lock:
            # Best-effort eviction to cap memory.
            # Prefer removing expired windows first, then evict oldest entries.
            if key not in self._buckets and len(self._buckets) >= self._max_keys:
                expired_keys = [
                    k for k, (wid, _) in self._buckets.items() if wid != window_id
                ]
                for k in expired_keys:
                    self._buckets.pop(k, None)

                while key not in self._buckets and len(self._buckets) >= self._max_keys:
                    oldest_key = next(iter(self._buckets))
                    self._buckets.pop(oldest_key, None)

            prev = self._buckets.get(key)
            if prev is None or prev[0] != window_id:
                count = 1
            else:
                count = prev[1] + 1

            # Move key to the end to approximate LRU behavior.
            self._buckets.pop(key, None)
            self._buckets[key] = (window_id, count)
            allowed = count <= policy.requests
            return allowed, retry_after


def make_rate_limit_middleware(
    *,
    limiter: InMemoryFixedWindowRateLimiter,
    policy: RateLimitPolicy,
    get_subject: SubjectGetter | None = None,
) -> Callable[[Request, Callable[[Request], Awaitable[Response]]], Awaitable[Response]]:
    """Create a FastAPI/Starlette http middleware implementing rate limiting."""

    async def middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Apply the configured fixed-window limit to matching requests."""
        if not policy.enabled:
            return await call_next(request)

        path = request.url.path
        if not path.startswith(policy.route_prefix):
            return await call_next(request)

        subject: str | None = None
        if get_subject is not None:
            try:
                subject = await get_subject(request)
            except Exception:  # noqa: BLE001
                # Never fail requests due to key derivation.
                subject = None

        ip = _get_client_ip(request, trust_x_forwarded_for=policy.trust_x_forwarded_for)
        key = f"ip:{ip}"
        if subject:
            key = f"{key}|sub:{subject}"

        allowed, retry_after = await limiter.hit(key=key, policy=policy)
        if allowed:
            return await call_next(request)

        return JSONResponse(
            {"detail": "rate limit exceeded"},
            status_code=429,
            headers={"Retry-After": str(retry_after)},
        )

    return middleware
