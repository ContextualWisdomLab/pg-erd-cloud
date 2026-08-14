"""API contracts for authenticated DBML conversion."""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.api.dbml import convert_dbml
from app.auth import CurrentUser
from app.schemas import DbmlConvertIn


def _user() -> CurrentUser:
    """Return an authenticated user for the pure conversion endpoint."""
    return CurrentUser(
        user_account_uuid=uuid.uuid4(), subject="dbml-test", display_name=None
    )


@pytest.mark.asyncio
async def test_dbml_identifier_error_returns_fixed_non_reflecting_422() -> None:
    """Malformed identifiers fail as fixed client errors without echoing input."""
    secret = "sensitive-identifier-value"
    body = DbmlConvertIn(dbml=f'Table "{secret}\x00" {{\n  id integer\n}}')

    with pytest.raises(HTTPException) as exc_info:
        await convert_dbml(body=body, user=_user())

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "invalid DBML identifier"
    assert secret not in str(exc_info.value.detail)
