"""Observability: structured logs + metrics.

MVP goals (issue #49):
- Emit JSON structured request logs suitable for central ingestion.
- Expose basic Prometheus metrics (/metrics) for API + job queue.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Response
from starlette.requests import Request

from app.metrics import (
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_TOTAL,
    render_metrics,
)
from app.settings import settings

_logger = logging.getLogger("app.observability")


def _utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _get_route_template(request: Request) -> str:
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    if isinstance(path, str) and path:
        return path
    return request.url.path


def _get_client_ip(request: Request) -> str:
    if settings.api_rate_limit_trust_x_forwarded_for:
        xff = request.headers.get("X-Forwarded-For")
        if xff:
            ip = xff.split(",", 1)[0].strip()
            if ip:
                return ip

    client = request.client
    if client is None:
        return "unknown"
    return client.host or "unknown"


def _log_json(event: str, fields: dict[str, object], *, level: int) -> None:
    payload: dict[str, object] = {
        "ts": _utc_now_iso(),
        "event": event,
        **fields,
    }
    _logger.log(
        level, json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    )


def make_request_observability_middleware() -> (
    Callable[
        [Request, Callable[[Request], Awaitable[Response]]], Awaitable[Response]
    ]
):
    async def middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if not settings.observability_request_logging_enabled:
            return await call_next(request)

        # Avoid recursive noise.
        if request.url.path == "/metrics":
            return await call_next(request)

        request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        start = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            duration_s = time.perf_counter() - start
            _log_json(
                "http_request",
                {
                    "request_id": request_id,
                    "method": request.method,
                    "route": _get_route_template(request),
                    "status": 500,
                    "duration_ms": round(duration_s * 1000.0, 3),
                    "client_ip": _get_client_ip(request),
                },
                level=logging.ERROR,
            )
            raise

        duration_s = time.perf_counter() - start
        status = int(response.status_code)
        route = _get_route_template(request)

        response.headers["X-Request-Id"] = request_id

        if settings.observability_metrics_enabled:
            HTTP_REQUESTS_TOTAL.labels(
                method=request.method,
                route=route,
                status=str(status),
            ).inc()
            HTTP_REQUEST_DURATION_SECONDS.labels(
                method=request.method,
                route=route,
            ).observe(duration_s)

        level = logging.INFO
        if status >= 500:
            level = logging.ERROR
        elif status >= 400:
            level = logging.WARNING

        _log_json(
            "http_request",
            {
                "request_id": request_id,
                "method": request.method,
                "route": route,
                "status": status,
                "duration_ms": round(duration_s * 1000.0, 3),
                "client_ip": _get_client_ip(request),
            },
            level=level,
        )
        return response

    return middleware


def setup_observability(app: FastAPI) -> None:
    """Register observability hooks on the given FastAPI app."""
    app.middleware("http")(make_request_observability_middleware())

    if settings.observability_metrics_enabled:

        @app.get("/metrics", include_in_schema=False)
        async def metrics() -> Response:
            content, content_type = render_metrics()
            return Response(content=content, media_type=content_type)
