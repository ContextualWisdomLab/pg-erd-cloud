from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def _int_env(name: str, default: str) -> int:
    """Parse an integer environment variable with a safe fallback.

    Hypercorn config modules are imported at server startup. A bad env value
    should not crash the process with an unhelpful ValueError.
    """

    raw = os.getenv(name)
    value = (raw if raw is not None else default).strip()
    try:
        parsed = int(value)
    except ValueError as exc:
        try:
            parsed = int(str(default).strip())
        except ValueError as default_exc:
            parsed = 1
            logger.warning(
                "Invalid %s=%r and default=%r; falling back to 1 (%s)",
                name,
                raw,
                default,
                default_exc,
            )
        else:
            logger.warning(
                "Invalid %s=%r; falling back to default=%r (%s)",
                name,
                raw,
                default,
                exc,
            )

    return max(1, parsed)


# Prefer explicit hypercorn knob; fall back to a common convention.
workers = _int_env("HYPERCORN_WORKERS", os.getenv("WEB_CONCURRENCY", "1"))
