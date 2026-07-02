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

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder
from starlette.responses import JSONResponse

from app.metrics import (
    AUTHZ_FAILURES_TOTAL,
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_TOTAL,
    normalize_route_label,
    prime_http_metrics,
    render_metrics,
)
from app.settings import settings

_logger = logging.getLogger("app.observability")

_SAFE_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_AUTHZ_HTTP_STATUS = {401, 403}
_UNKNOWN_AUTHZ_REASON = "unknown"
_AUTHZ_DETAIL_REASON_MAP = {
    "missing bearer token": "missing_bearer_token",
    "invalid token header": "invalid_token_header",
    "unsupported token type": "unsupported_token_type",
    "unsupported token content type": "unsupported_token_content_type",
    "token missing alg": "missing_token_alg",
    "token missing exp": "token_missing_exp",
    "token missing sub": "token_missing_sub",
    "token missing jti": "token_missing_jti",
    "token revoked": "token_revoked",
    "unsupported token algorithm": "unsupported_token_algorithm",
    "unknown signing key": "unknown_signing_key",
    "algorithm/key type mismatch": "algorithm_key_type_mismatch",
    "token verification failed": "token_verification_failed",
    "owner role required": "owner_role_required",
    "share link LLM draft is disabled": "share_llm_draft_disabled",
    "license key is not configured for required mode": "license_key_not_configured",
    "invalid or missing license key": "license_key_invalid",
}


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
            ip = xff.split(",")[-1].strip()
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


def _record_authz_event(request: Request, request_id: str, status: int) -> None:
    if status not in _AUTHZ_HTTP_STATUS:
        return

    reason = _classify_authz_reason(None)
    if settings.observability_metrics_enabled:
        AUTHZ_FAILURES_TOTAL.labels(
            status=str(status),
            route=normalize_route_label(_get_route_template(request)),
            reason=reason,
        ).inc()

    if status in _AUTHZ_HTTP_STATUS:
        _log_json(
            "authz_failure",
            {
                "request_id": request_id,
                "method": request.method,
                "route": _get_route_template(request),
                "status": status,
                "reason": reason,
                "client_ip": _get_client_ip(request),
            },
            level=logging.WARNING,
        )


def _classify_authz_reason(detail: object) -> str:
    if not isinstance(detail, str):
        return _UNKNOWN_AUTHZ_REASON
    normalized = detail.strip().lower()
    if not normalized:
        return _UNKNOWN_AUTHZ_REASON
    return _AUTHZ_DETAIL_REASON_MAP.get(normalized, _UNKNOWN_AUTHZ_REASON)


def _make_http_exception_handler() -> Callable[[Request, Exception], Awaitable[Response]]:
    async def handler(request: Request, exc: Exception) -> Response:
        if not isinstance(exc, HTTPException):
            raise exc

        request_id = getattr(request.state, "request_id", None)
        if request_id is None:
            request_id = str(uuid.uuid4())
            request.state.request_id = request_id

        status = int(exc.status_code)
        if status in _AUTHZ_HTTP_STATUS and settings.observability_request_logging_enabled:
            reason = _classify_authz_reason(exc.detail)
            if settings.observability_metrics_enabled:
                AUTHZ_FAILURES_TOTAL.labels(
                    status=str(status),
                    route=normalize_route_label(_get_route_template(request)),
                    reason=reason,
                ).inc()
            _log_json(
                "authz_failure",
                {
                    "request_id": request_id,
                    "method": request.method,
                    "route": _get_route_template(request),
                    "status": status,
                    "reason": reason,
                    "detail": jsonable_encoder(exc.detail),
                    "client_ip": _get_client_ip(request),
                },
                level=logging.WARNING,
            )
            setattr(request.state, "authz_event_emitted", True)

        return JSONResponse(
            status_code=status,
            content={"detail": exc.detail},
            headers=exc.headers,
        )

    return handler


def make_request_observability_middleware() -> Callable[
    [Request, Callable[[Request], Awaitable[Response]]], Awaitable[Response]
]:
    """Create request logging, metrics, and request-id middleware."""

    async def middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Record one request and attach an X-Request-Id response header."""
        # Avoid recursive noise in logs/metrics.
        is_metrics_path = request.url.path == "/metrics"

        raw_request_id = (request.headers.get("X-Request-Id") or "").strip()
        if raw_request_id and _SAFE_REQUEST_ID_RE.fullmatch(raw_request_id):
            request_id = raw_request_id
        else:
            request_id = str(uuid.uuid4())
        request.state.request_id = request_id
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
        if (
            status in _AUTHZ_HTTP_STATUS
            and not getattr(request.state, "authz_event_emitted", False)
        ):
            _record_authz_event(request, request_id, status)
        return response

    return middleware


def setup_observability(app: FastAPI) -> None:
    """Register observability hooks on the given FastAPI app."""
    app.middleware("http")(make_request_observability_middleware())
    app.add_exception_handler(HTTPException, _make_http_exception_handler())

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
        """Return Prometheus metrics when the request presents the metrics token."""
        provided = request.headers.get("X-Metrics-Token") or ""
        if not secrets.compare_digest(provided, token):
            return Response(status_code=403)
        content, content_type = render_metrics()
        return Response(content=content, media_type=content_type)

    def _prime_metrics_on_startup() -> None:
        route_methods: dict[str, set[str]] = {}
        for r in app.routes:
            path = getattr(r, "path", None)
            if not isinstance(path, str) or not path or path == "/metrics":
                continue

            r_methods = getattr(r, "methods", None)
            if isinstance(r_methods, set):
                methods = {m for m in r_methods if m not in {"HEAD"}}
            else:
                methods = set()

            if not methods:
                methods.add("GET")

            if path in route_methods:
                route_methods[path].update(methods)
            else:
                route_methods[path] = methods

        prime_http_metrics(route_methods=route_methods)

    app.router.add_event_handler("startup", _prime_metrics_on_startup)
