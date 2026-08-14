"""Secret-safe request validation response contracts."""

import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

from app.request_validation import request_validation_exception_handler
from app.schemas import ApplySqlIn


def _validation_app() -> FastAPI:
    app = FastAPI()
    app.add_exception_handler(
        RequestValidationError,
        request_validation_exception_handler,
    )

    @app.post(
        "/api/connections/00000000-0000-4000-8000-000000000001/apply-sql"
    )
    async def accept_sql(_: ApplySqlIn) -> dict[str, bool]:
        return {"ok": True}

    return app


def test_validation_response_omits_hostile_sql_input(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Never echo rejected SQL or secret-like literals in a 422 response."""

    secret = "password=do-not-reflect"
    response = TestClient(_validation_app()).post(
        "/api/connections/00000000-0000-4000-8000-000000000001/apply-sql",
        json={"sql": f"CREATE\x00TABLE sample (note text DEFAULT '{secret}')"},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "request validation failed"}
    assert secret not in response.text
    assert "CREATE" not in response.text
    assert secret not in caplog.text


def test_production_app_registers_secret_safe_validation_handler() -> None:
    """Keep the sensitive-body response handler active in production wiring."""

    from app.main import app as production_app

    assert (
        production_app.exception_handlers[RequestValidationError]
        is request_validation_exception_handler
    )
