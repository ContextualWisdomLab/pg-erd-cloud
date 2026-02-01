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
from app.db import SessionLocal
from app.jobs.snapshot_job import handle_snapshot_job
from app.jobs.worker import run_worker_forever
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
async def healthz() -> dict:
    """Simple health-check endpoint."""
    return {"ok": True}


app.include_router(projects_router)
app.include_router(connections_router)
app.include_router(snapshots_router)
app.include_router(me_router)
app.include_router(share_router)
