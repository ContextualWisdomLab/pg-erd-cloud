from __future__ import annotations

import os


def _int_env(name: str, default: str) -> int:
    """Parse an integer environment variable with a safe fallback.

    Hypercorn config modules are imported at server startup. A bad env value
    should not crash the process with an unhelpful ValueError.
    """

    raw = os.getenv(name)
    value = (raw if raw is not None else default).strip()
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        try:
            parsed = int(str(default).strip())
        except (TypeError, ValueError):
            parsed = 1

    return max(1, parsed)


# Prefer explicit hypercorn knob; fall back to a common convention.
workers = _int_env("HYPERCORN_WORKERS", os.getenv("WEB_CONCURRENCY", "1"))
