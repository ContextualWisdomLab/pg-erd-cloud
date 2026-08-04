"""Focused branch-coverage contracts for security-critical backend helpers."""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import Response

from app.permissions import require_project_member
from app.pooler import build_admin_console_dsn
from app.security_headers import apply_security_headers


class _ScalarResult:
    """Minimal SQLAlchemy-result substitute exposing one scalar role."""

    def __init__(self, role: str | None) -> None:
        self._role = role

    def scalar_one_or_none(self) -> str | None:
        """Return the configured role exactly once per authorization call."""

        return self._role


class _RoleSession:
    """Minimal async-session substitute used by membership unit tests."""

    def __init__(self, role: str | None) -> None:
        self._role = role

    async def execute(self, _statement: object) -> _ScalarResult:
        """Return a deterministic role result without a database dependency."""

        return _ScalarResult(self._role)


def _request(*, scheme: str = "https", path: str = "/api/coverage") -> Request:
    """Build a complete Starlette request for direct header tests."""

    return Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": scheme,
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 443 if scheme == "https" else 80),
            "root_path": "",
        }
    )


@pytest.mark.asyncio
async def test_project_role_requirement_accepts_sufficient_membership() -> None:
    """Return a member's role when it meets the requested minimum rank."""

    role = await require_project_member(
        _RoleSession("editor"),  # type: ignore[arg-type]
        uuid.uuid4(),
        uuid.uuid4(),
        minimum_role="editor",
    )

    assert role == "editor"


@pytest.mark.asyncio
async def test_project_role_requirement_rejects_insufficient_membership() -> None:
    """Reject a valid member whose role is below the requested minimum."""

    with pytest.raises(HTTPException) as exc_info:
        await require_project_member(
            _RoleSession("viewer"),  # type: ignore[arg-type]
            uuid.uuid4(),
            uuid.uuid4(),
            minimum_role="editor",
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "insufficient project role"


@pytest.mark.asyncio
async def test_project_membership_without_minimum_returns_known_role() -> None:
    """Allow any known membership when no minimum role is requested."""

    role = await require_project_member(
        _RoleSession("viewer"),  # type: ignore[arg-type]
        uuid.uuid4(),
        uuid.uuid4(),
    )

    assert role == "viewer"


def test_admin_console_dsn_preserves_already_sync_driver() -> None:
    """Keep an existing synchronous PostgreSQL scheme while removing secrets."""

    dsn, password = build_admin_console_dsn(
        "postgresql://operator:fixture-secret@db.example.test:5432/app_db",
        "pooler_admin",
    )

    assert dsn.startswith("postgresql://operator@db.example.test:5432/pooler_admin")
    assert "fixture-secret" not in dsn
    assert password == "fixture-secret"


def test_security_headers_preserve_an_explicit_upstream_header() -> None:
    """Do not overwrite a stricter header selected by an upstream component."""

    response = Response(headers={"X-Frame-Options": "SAMEORIGIN"})

    apply_security_headers(_request(), response)

    assert response.headers["X-Frame-Options"] == "SAMEORIGIN"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Strict-Transport-Security"].startswith("max-age=")
