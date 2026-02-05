from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.connections import router as connections_router
from app.api.me import router as me_router
from app.api.projects import router as projects_router
from app.api.share import router as share_router
from app.api.snapshots import router as snapshots_router
from app.auth import try_get_subject_for_rate_limit
from app.db import SessionLocal
from app.jobs.snapshot_job import handle_snapshot_job
from app.jobs.worker import run_worker_forever
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
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="pg-erd-cloud backend", lifespan=lifespan)

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

app.middleware("http")(
    make_rate_limit_middleware(
        limiter=_rate_limiter,
        policy=_rate_limit_policy,
        get_subject=try_get_subject_for_rate_limit,
    )
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        o.strip() for o in settings.cors_origins.split(",") if o.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Apply response security headers.
#
# FastAPI/Starlette middleware order: the **last** middleware registration wraps
# earlier ones (i.e., it becomes the outermost).
#
# We register security headers after other middleware so headers are attached
# even when an inner middleware returns early (e.g., CORS preflight, 429, etc.).
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
