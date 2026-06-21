from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.connections import router as connections_router
from app.api.auth_routes import router as auth_router
from app.api.me import router as me_router
from app.api.projects import router as projects_router
from app.api.share import router as share_router
from app.api.snapshots import router as snapshots_router
from app.auth import try_get_subject_for_rate_limit
from app.csrf import CSRF_HEADER_NAME, make_csrf_middleware
from app.db import SessionLocal, get_pooler_detection
from app.jobs.snapshot_job import handle_snapshot_job
from app.jobs.worker import run_worker_forever
from app.observability import setup_observability
from app.rate_limit import (
    InMemoryFixedWindowRateLimiter,
    RateLimitPolicy,
    make_rate_limit_middleware,
)
from app.security_headers import make_security_headers_middleware
from app.settings import settings


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Run application startup/shutdown hooks.

    Starts a background job worker on startup and ensures it is cancelled and
    awaited on shutdown.
    """

    handlers = {"snapshot": handle_snapshot_job}
    task = asyncio.create_task(run_worker_forever(SessionLocal, handlers))
    try:
        # Best-effort pooler detection (log once for ops visibility).
        try:
            detection = await get_pooler_detection()
            logging.getLogger(__name__).info(
                "db_pooler_detection: kind=%s detected=%s",
                detection.kind.value,
                detection.detected,
            )
        except Exception:
            logging.getLogger(__name__).exception("db_pooler_detection failed")
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="pg-erd-cloud backend", lifespan=lifespan)

CORS_ALLOW_HEADERS = [
    "Authorization",
    "Content-Type",
    "X-Dev-User",
    CSRF_HEADER_NAME,
]

_rate_limiter = InMemoryFixedWindowRateLimiter(
    max_keys=settings.api_rate_limit_max_keys
)
_rate_limit_policy = RateLimitPolicy(
    enabled=settings.api_rate_limit_enabled,
    requests=settings.api_rate_limit_requests,
    window_seconds=settings.api_rate_limit_window_seconds,
    route_prefix="/api",
    trust_x_forwarded_for=settings.api_rate_limit_trust_x_forwarded_for,
)
_share_link_rate_limiter = InMemoryFixedWindowRateLimiter(
    max_keys=settings.share_link_rate_limit_max_keys
)
_share_link_rate_limit_policy = RateLimitPolicy(
    enabled=settings.share_link_rate_limit_enabled,
    requests=settings.share_link_rate_limit_requests,
    window_seconds=settings.share_link_rate_limit_window_seconds,
    route_prefix="/api/share",
    trust_x_forwarded_for=settings.api_rate_limit_trust_x_forwarded_for,
)

app.middleware("http")(
    make_rate_limit_middleware(
        limiter=_rate_limiter,
        policy=_rate_limit_policy,
        get_subject=try_get_subject_for_rate_limit,
    )
)
app.middleware("http")(
    make_rate_limit_middleware(
        limiter=_share_link_rate_limiter,
        policy=_share_link_rate_limit_policy,
    )
)

app.middleware("http")(make_csrf_middleware())

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    # Default to the strictest safe setting. Enable credentials only when you
    # actually need cookie-based auth.
    allow_credentials=False,
    # Explicit allowlist (avoid "*") so CORS behavior is reviewable.
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=CORS_ALLOW_HEADERS,
)

# Observability should be registered after other middleware so it can capture
# early returns (e.g. 429, CORS preflight).
#
# Note: security headers are registered last (outermost) so headers are attached
# even when another middleware returns early.
setup_observability(app)

# Apply response security headers.
#
# Starlette middleware order: the **last** registered middleware wraps earlier
# ones (i.e., it becomes the outermost).
#
# We register security headers last so headers are attached even when another
# middleware returns early (e.g., CORS preflight, 429 rate-limit responses).
# See: backend/tests/test_security_headers.py
app.middleware("http")(make_security_headers_middleware())


@app.get("/healthz")
async def healthz() -> dict:
    """Simple health-check endpoint."""
    return {"ok": True}


app.include_router(projects_router)
app.include_router(connections_router)
app.include_router(snapshots_router)
app.include_router(me_router)
app.include_router(share_router)
app.include_router(auth_router)
