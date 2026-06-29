"""Observability: structured logs + metrics.

MVP goals (issue #49):
- Emit JSON structured request logs suitable for central ingestion.
- Expose basic Prometheus metrics (/metrics) for API + job queue.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
import secrets
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Response
from starlette.requests import Request

from app.metrics import (
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_TOTAL,
    normalize_route_label,
    prime_http_metrics,
    render_metrics,
)
from app.settings import settings

_logger = logging.getLogger("app.observability")

_SAFE_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _get_route_template(request: Request) -> str:
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    if isinstance(path, str) and path:
        return path
    # Avoid high-cardinality labels for unmatched routes (e.g., 404 paths).
    return "unmatched"


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
    _logger.log(level, json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def _record_metrics_and_logs(
    request: Request,
    request_id: str,
    status: int,
    duration_s: float,
    is_metrics_path: bool,
) -> None:
    route = normalize_route_label(_get_route_template(request))

    if settings.observability_metrics_enabled and not is_metrics_path:
        HTTP_REQUESTS_TOTAL.labels(
            method=request.method,
            route=route,
            status=str(status),
        ).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(
            method=request.method,
            route=route,
        ).observe(duration_s)

    if settings.observability_request_logging_enabled and not is_metrics_path:
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


def make_request_observability_middleware() -> Callable[
    [Request, Callable[[Request], Awaitable[Response]]], Awaitable[Response]
]:
    async def middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # Avoid recursive noise in logs/metrics.
        is_metrics_path = request.url.path == "/metrics"

        raw_request_id = (request.headers.get("X-Request-Id") or "").strip()
        if raw_request_id and _SAFE_REQUEST_ID_RE.fullmatch(raw_request_id):
            request_id = raw_request_id
        else:
            request_id = str(uuid.uuid4())
        start = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            duration_s = time.perf_counter() - start
            _record_metrics_and_logs(
                request, request_id, 500, duration_s, is_metrics_path
            )

            # Ensure the request id is visible to clients even on 500.
            _logger.exception("unhandled request exception")
            error_response = Response(status_code=500)
            error_response.headers["X-Request-Id"] = request_id
            return error_response

        duration_s = time.perf_counter() - start
        status = int(response.status_code)

        response.headers["X-Request-Id"] = request_id

        _record_metrics_and_logs(
            request, request_id, status, duration_s, is_metrics_path
        )
        return response

    return middleware


def setup_observability(app: FastAPI) -> None:
    """Register observability hooks on the given FastAPI app."""
    app.middleware("http")(make_request_observability_middleware())

    if not settings.observability_metrics_enabled:
        return

    token = (settings.observability_metrics_token or "").strip()
    if not token:
        _logger.warning(
            "observability_metrics_enabled=true but token missing; "
            "skipping /metrics route registration"
        )
        return

    @app.get("/metrics", include_in_schema=False)
    async def metrics(request: Request) -> Response:
        provided = request.headers.get("X-Metrics-Token") or ""
        if not secrets.compare_digest(provided, token):
            return Response(status_code=403)
        content, content_type = render_metrics()
        return Response(content=content, media_type=content_type)

    def _prime_metrics_on_startup() -> None:
        methods: set[str] = set()
        routes: set[str] = set()
        for r in app.routes:
            path = getattr(r, "path", None)
            if isinstance(path, str) and path:
                routes.add(path)

            r_methods = getattr(r, "methods", None)
            if isinstance(r_methods, set):
                methods.update({m for m in r_methods if m not in {"HEAD"}})

        routes.discard("/metrics")
        if not methods:
            methods.add("GET")
        prime_http_metrics(methods=methods, routes=routes)

    app.router.add_event_handler("startup", _prime_metrics_on_startup)
