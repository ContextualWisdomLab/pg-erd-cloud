from __future__ import annotations

import asyncio

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


app = FastAPI(title="pg-erd-cloud backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
async def healthz() -> dict:
    return {"ok": True}


app.include_router(projects_router)
app.include_router(connections_router)
app.include_router(snapshots_router)
app.include_router(me_router)
app.include_router(share_router)


@app.on_event("startup")
async def start_worker() -> None:
    handlers = {"snapshot": handle_snapshot_job}
    # Background worker loop. For production, run as separate process.
    asyncio.create_task(run_worker_forever(SessionLocal, handlers))
