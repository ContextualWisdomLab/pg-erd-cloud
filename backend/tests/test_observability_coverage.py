"""Behavioral coverage for observability logging, middleware, and metric priming."""

from __future__ import annotations

import json
import logging
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import Response

from app import observability
from app.settings import settings


class _Metric:
    """Prometheus-like metric double recording labels and values."""

    def __init__(self) -> None:
        self.label_calls: list[dict[str, str]] = []
        self.increment_calls = 0
        self.observations: list[float] = []

    def labels(self, **labels: str) -> "_Metric":
        """Record labels and return the bound metric."""
        self.label_calls.append(labels)
        return self

    def inc(self) -> None:
        """Record one counter increment."""
        self.increment_calls += 1

    def observe(self, value: float) -> None:
        """Record one duration observation."""
        self.observations.append(value)


def _request(
    *,
    path: str = "/api/items",
    request_id: str | None = None,
    route_path: object = "/api/items",
) -> Request:
    """Construct a minimal HTTP request with optional route and request identity."""
    headers: list[tuple[bytes, bytes]] = []
    if request_id is not None:
        headers.append((b"x-request-id", request_id.encode()))
    scope: dict[str, object] = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "https",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": headers,
        "client": ("192.0.2.10", 12345),
        "server": ("testserver", 443),
        "root_path": "",
    }
    if route_path is not None:
        scope["route"] = SimpleNamespace(path=route_path)
    return Request(scope)


def test_utc_now_iso_is_timezone_aware() -> None:
    """Emit an ISO timestamp carrying the UTC offset."""
    value = observability._utc_now_iso()

    assert value.endswith("+00:00")


def test_log_json_serializes_bounded_event_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Emit compact JSON at the requested log severity."""
    records: list[tuple[int, str]] = []

    def log(level: int, message: str) -> None:
        records.append((level, message))

    monkeypatch.setattr(observability._logger, "log", log)

    observability._log_json(
        "buyer_event",
        {"request_id": "request-1", "status": 200},
        level=logging.INFO,
    )

    assert len(records) == 1
    level, message = records[0]
    payload = json.loads(message)
    assert level == logging.INFO
    assert payload["event"] == "buyer_event"
    assert payload["request_id"] == "request-1"
    assert payload["status"] == 200
    assert payload["ts"].endswith("+00:00")


@pytest.mark.parametrize(
    ("status", "expected_level"),
    [(200, logging.INFO), (404, logging.WARNING), (503, logging.ERROR)],
)
def test_record_metrics_and_logs_maps_status_levels(
    monkeypatch: pytest.MonkeyPatch,
    status: int,
    expected_level: int,
) -> None:
    """Publish low-cardinality metrics and severity-aware request logs."""
    request_counter = _Metric()
    duration_metric = _Metric()
    logs: list[tuple[str, dict[str, object], int]] = []
    monkeypatch.setattr(settings, "observability_metrics_enabled", True)
    monkeypatch.setattr(settings, "observability_request_logging_enabled", True)
    monkeypatch.setattr(observability, "HTTP_REQUESTS_TOTAL", request_counter)
    monkeypatch.setattr(observability, "HTTP_REQUEST_DURATION_SECONDS", duration_metric)

    def record_log(
        event: str,
        fields: dict[str, object],
        *,
        level: int,
    ) -> None:
        logs.append((event, fields, level))

    monkeypatch.setattr(observability, "_log_json", record_log)

    observability._record_metrics_and_logs(
        _request(),
        "request-1",
        status,
        0.125,
        False,
    )

    assert request_counter.label_calls == [
        {"method": "GET", "route": "/api/items", "status": str(status)}
    ]
    assert request_counter.increment_calls == 1
    assert duration_metric.label_calls == [
        {"method": "GET", "route": "/api/items"}
    ]
    assert duration_metric.observations == [0.125]
    assert logs[0][0] == "http_request"
    assert logs[0][1]["duration_ms"] == 125.0
    assert logs[0][1]["client_ip"] == "192.0.2.10"
    assert logs[0][2] == expected_level


def test_record_metrics_and_logs_suppresses_metrics_path_and_disabled_sinks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Avoid recursive telemetry and respect independently disabled sinks."""
    request_counter = _Metric()
    duration_metric = _Metric()
    monkeypatch.setattr(observability, "HTTP_REQUESTS_TOTAL", request_counter)
    monkeypatch.setattr(observability, "HTTP_REQUEST_DURATION_SECONDS", duration_metric)
    monkeypatch.setattr(settings, "observability_metrics_enabled", True)
    monkeypatch.setattr(settings, "observability_request_logging_enabled", True)
    logs: list[object] = []
    monkeypatch.setattr(
        observability,
        "_log_json",
        lambda *args, **kwargs: logs.append((args, kwargs)),
    )

    observability._record_metrics_and_logs(
        _request(path="/metrics", route_path="/metrics"),
        "request-metrics",
        200,
        0.01,
        True,
    )
    assert request_counter.increment_calls == 0
    assert duration_metric.observations == []
    assert logs == []

    monkeypatch.setattr(settings, "observability_metrics_enabled", False)
    monkeypatch.setattr(settings, "observability_request_logging_enabled", False)
    observability._record_metrics_and_logs(
        _request(),
        "request-disabled",
        200,
        0.01,
        False,
    )
    assert request_counter.increment_calls == 0
    assert logs == []


@pytest.mark.asyncio
async def test_request_middleware_preserves_safe_request_id_and_records_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Preserve a safe caller request ID and record a successful response."""
    observations: list[tuple[str, int, bool]] = []
    clock = iter((10.0, 10.25))
    monkeypatch.setattr(observability.time, "perf_counter", lambda: next(clock))

    def record(
        _request_value: Request,
        request_id: str,
        status: int,
        _duration: float,
        is_metrics_path: bool,
    ) -> None:
        observations.append((request_id, status, is_metrics_path))

    monkeypatch.setattr(observability, "_record_metrics_and_logs", record)
    middleware = observability.make_request_observability_middleware()

    async def call_next(_request_value: Request) -> Response:
        return Response("ok", status_code=201)

    response = await middleware(_request(request_id="safe_id-1"), call_next)

    assert response.status_code == 201
    assert response.headers["X-Request-Id"] == "safe_id-1"
    assert observations == [("safe_id-1", 201, False)]


@pytest.mark.asyncio
async def test_request_middleware_replaces_unsafe_id_and_contains_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Generate a safe ID and return a bounded 500 when downstream code raises."""
    recorded: list[tuple[str, int, bool]] = []
    clock = iter((20.0, 20.5))
    monkeypatch.setattr(observability.time, "perf_counter", lambda: next(clock))
    monkeypatch.setattr(observability.uuid, "uuid4", lambda: "generated-request-id")
    monkeypatch.setattr(observability._logger, "exception", lambda *_args: None)

    def record(
        _request_value: Request,
        request_id: str,
        status: int,
        _duration: float,
        is_metrics_path: bool,
    ) -> None:
        recorded.append((request_id, status, is_metrics_path))

    monkeypatch.setattr(observability, "_record_metrics_and_logs", record)
    middleware = observability.make_request_observability_middleware()

    async def failing_next(_request_value: Request) -> Response:
        raise RuntimeError("private downstream detail")

    response = await middleware(
        _request(request_id="unsafe request id!"),
        failing_next,
    )

    assert response.status_code == 500
    assert response.headers["X-Request-Id"] == "generated-request-id"
    assert recorded == [("generated-request-id", 500, False)]


@pytest.mark.asyncio
async def test_request_middleware_marks_metrics_path_for_recursive_suppression(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tell the recorder that the metrics endpoint must not instrument itself."""
    recorded: list[bool] = []
    clock = iter((30.0, 30.1))
    monkeypatch.setattr(observability.time, "perf_counter", lambda: next(clock))

    def record(
        _request_value: Request,
        _request_id: str,
        _status: int,
        _duration: float,
        is_metrics_path: bool,
    ) -> None:
        recorded.append(is_metrics_path)

    monkeypatch.setattr(observability, "_record_metrics_and_logs", record)
    middleware = observability.make_request_observability_middleware()

    async def call_next(_request_value: Request) -> Response:
        return Response("metrics", status_code=200)

    await middleware(_request(path="/metrics", route_path="/metrics"), call_next)

    assert recorded == [True]


def test_setup_observability_returns_when_metrics_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Install middleware without registering a metrics route when disabled."""
    monkeypatch.setattr(settings, "observability_metrics_enabled", False)
    app = FastAPI()

    observability.setup_observability(app)

    assert all(getattr(route, "path", None) != "/metrics" for route in app.routes)


def test_setup_observability_warns_and_skips_metrics_without_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fail closed when metrics are enabled without an access token."""
    warnings: list[str] = []
    monkeypatch.setattr(settings, "observability_metrics_enabled", True)
    monkeypatch.setattr(settings, "observability_metrics_token", "   ")
    monkeypatch.setattr(
        observability._logger,
        "warning",
        lambda message: warnings.append(message),
    )
    app = FastAPI()

    observability.setup_observability(app)

    assert warnings == [
        "observability_metrics_enabled=true but token missing; "
        "skipping /metrics route registration"
    ]
    assert all(getattr(route, "path", None) != "/metrics" for route in app.routes)


@pytest.mark.asyncio
async def test_setup_observability_primes_route_methods_and_metrics_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prime merged route/method labels and serve authenticated rendered metrics."""
    monkeypatch.setattr(settings, "observability_metrics_enabled", True)
    monkeypatch.setattr(settings, "observability_metrics_token", "metrics-secret")
    primed: list[dict[str, set[str]]] = []
    monkeypatch.setattr(
        observability,
        "prime_http_metrics",
        lambda *, route_methods: primed.append(route_methods),
    )
    monkeypatch.setattr(
        observability,
        "render_metrics",
        lambda: (b"metric 1\n", "text/plain; version=0.0.4"),
    )
    app = FastAPI()

    @app.get("/buyer")
    async def get_buyer() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/buyer")
    async def post_buyer() -> dict[str, bool]:
        return {"ok": True}

    app.routes.append(SimpleNamespace(path="/default-method", methods=None))
    app.routes.append(SimpleNamespace(path="", methods={"GET"}))
    observability.setup_observability(app)

    startup_handler = app.router.on_startup[-1]
    startup_handler()

    assert primed
    assert primed[0]["/buyer"] == {"GET", "POST"}
    assert primed[0]["/default-method"] == {"GET"}
    assert "/metrics" not in primed[0]

    metrics_route = next(
        route for route in app.routes if getattr(route, "path", None) == "/metrics"
    )
    unauthorized = await metrics_route.endpoint(_request(path="/metrics"))
    assert unauthorized.status_code == 403

    authorized_request = _request(path="/metrics")
    authorized_request.scope["headers"] = [(b"x-metrics-token", b"metrics-secret")]
    authorized = await metrics_route.endpoint(authorized_request)
    assert authorized.status_code == 200
    assert authorized.body == b"metric 1\n"
