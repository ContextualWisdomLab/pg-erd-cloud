"""Secret-safe request validation response contracts."""

import uuid
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

from app.api.connections import router as connections_router
from app.auth import CurrentUser, get_current_user
from app.db import get_session
from app.request_validation import request_validation_exception_handler
from app.schemas import ApplySqlIn, DbmlConvertIn


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CONTROL_BOUNDARY_DOC = (
    REPOSITORY_ROOT / "docs/doctoring/multiline-sql-request-controls.md"
)


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

    @app.post("/api/dbml/convert")
    async def accept_dbml(_: DbmlConvertIn) -> dict[str, bool]:
        return {"ok": True}

    return app


def test_validation_response_omits_hostile_sql_input(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Never echo rejected SQL or secret-like literals in a 422 response."""

    sensitive_marker = "password=do-not-reflect"
    response = TestClient(_validation_app()).post(
        "/api/connections/00000000-0000-4000-8000-000000000001/apply-sql",
        json={"sql": f"CREATE\x00TABLE sample (note text DEFAULT '{sensitive_marker}')"},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "request validation failed"}
    assert sensitive_marker not in response.text
    assert "CREATE" not in response.text
    assert sensitive_marker not in caplog.text


def test_invalid_legacy_apply_body_stops_before_auth_or_session() -> None:
    """Reject forbidden SQL transport controls before protected dependencies."""

    dependency_calls: list[str] = []

    def current_user() -> CurrentUser:
        dependency_calls.append("auth")
        return CurrentUser(
            user_account_uuid=uuid.uuid4(),
            subject="must-not-run",
            display_name=None,
        )

    def session() -> object:
        dependency_calls.append("session")
        return object()

    app = FastAPI()
    app.add_exception_handler(
        RequestValidationError,
        request_validation_exception_handler,
    )
    app.include_router(connections_router)
    app.dependency_overrides[get_current_user] = current_user
    app.dependency_overrides[get_session] = session

    response = TestClient(app).post(
        f"/api/connections/{uuid.uuid4()}/apply-sql",
        json={"sql": "CREATE\x00TABLE secret_data (id bigint)"},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "request validation failed"}
    assert dependency_calls == []


def test_production_app_registers_secret_safe_validation_handler() -> None:
    """Keep the sensitive-body response handler active in production wiring."""

    from app.main import app as production_app

    assert (
        production_app.exception_handlers[RequestValidationError]
        is request_validation_exception_handler
    )


def test_legacy_apply_control_boundary_is_documented_without_overclaim() -> None:
    """Keep request ordering, non-reflection, and parser authority explicit."""

    document = CONTROL_BOUNDARY_DOC.read_text(encoding="utf-8")
    normalized = " ".join(document.split())

    for term in (
        "SecretSafeLegacyApplyRoute",
        "before `get_current_user` and `get_session`",
        "RequestValidationError.body",
        "does not authorize SQL",
        "Towards Secure Logging",
        "https://arxiv.org/abs/2604.20211",
    ):
        assert term in normalized


def test_validation_response_omits_oversized_dbml_input(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Never echo rejected DBML from the bounded conversion endpoint."""

    sensitive_marker = "dbml-secret-do-not-reflect"
    response = TestClient(_validation_app()).post(
        "/api/dbml/convert",
        json={"dbml": secret + ("x" * 524_288)},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "request validation failed"}
    assert sensitive_marker not in response.text
    assert sensitive_marker not in caplog.text
