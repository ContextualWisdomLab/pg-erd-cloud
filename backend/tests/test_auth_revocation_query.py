"""Direct contracts for the JWT revocation existence query."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from app import auth
from app import db as app_db


class _ScalarResult:
    """Minimal SQLAlchemy-like result exposing the scalar existence contract."""

    def __init__(self, value: object | None) -> None:
        self._value = value
        self.scalar_calls = 0

    def scalar(self) -> object | None:
        """Return the configured first-column scalar and record the call."""
        self.scalar_calls += 1
        return self._value


class _RevocationSession:
    """Async session double that records the exact statement under test."""

    def __init__(self, result: _ScalarResult) -> None:
        self.result = result
        self.statement: object | None = None

    async def __aenter__(self) -> "_RevocationSession":
        """Enter the fake database-session boundary."""
        return self

    async def __aexit__(self, *_args: object) -> None:
        """Exit without suppressing failures."""
        return None

    async def execute(self, statement: object) -> _ScalarResult:
        """Capture the statement and return the scalar-only result double."""
        self.statement = statement
        return self.result


@pytest.mark.asyncio
@pytest.mark.parametrize(("scalar_value", "expected"), [("jwt-1", True), (None, False)])
async def test_is_token_jti_revoked_uses_scalar_existence_result(
    monkeypatch: pytest.MonkeyPatch,
    scalar_value: object | None,
    expected: bool,
) -> None:
    """Treat a returned JWT ID as revoked and a missing scalar as not revoked."""
    result = _ScalarResult(scalar_value)
    session = _RevocationSession(result)
    session_factory: Callable[[], _RevocationSession] = lambda: session
    monkeypatch.setattr(app_db, "SessionLocal", session_factory)

    assert await auth.is_token_jti_revoked("jwt-1") is expected
    assert result.scalar_calls == 1
    assert session.statement is not None
    statement_text = str(session.statement)
    assert "revoked_tokens.jwt_id" in statement_text
    assert "LIMIT" in statement_text.upper()
