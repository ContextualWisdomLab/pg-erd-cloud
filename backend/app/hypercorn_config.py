from __future__ import annotations

import os


def _int_env(name: str, default: str) -> int:
    value = os.getenv(name, default).strip()
    return int(value)


# Prefer explicit hypercorn knob; fall back to a common convention.
workers = _int_env("HYPERCORN_WORKERS", os.getenv("WEB_CONCURRENCY", "1"))
