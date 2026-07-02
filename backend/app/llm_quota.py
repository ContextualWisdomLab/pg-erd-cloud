from __future__ import annotations

from fastapi import HTTPException

from app.rate_limit import InMemoryFixedWindowRateLimiter, RateLimitPolicy
from app.settings import settings


_LLM_DRAFT_LIMITER = InMemoryFixedWindowRateLimiter(max_keys=10_000)


def _llm_draft_policy() -> RateLimitPolicy:
    return RateLimitPolicy(
        enabled=settings.llm_draft_quota_enabled,
        requests=settings.llm_draft_quota_requests,
        window_seconds=settings.llm_draft_quota_window_seconds,
    )


async def enforce_llm_draft_quota(key: str) -> None:
    """Enforce a per-key live LLM draft quota before provider calls."""
    policy = _llm_draft_policy()
    if not policy.enabled:
        return

    allowed, retry_after = await _LLM_DRAFT_LIMITER.hit(
        key=f"llm-draft:{key}",
        policy=policy,
    )
    if allowed:
        return

    raise HTTPException(
        status_code=429,
        detail="LLM draft quota exceeded",
        headers={"Retry-After": str(retry_after)},
    )


def reset_llm_draft_quota_state() -> None:
    """Clear in-process quota state for tests and controlled local drills."""
    _LLM_DRAFT_LIMITER._buckets.clear()
