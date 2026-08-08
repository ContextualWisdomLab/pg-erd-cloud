"""Focused regressions for fail-closed JOSE ``crit`` header handling."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app import auth


def test_validate_jwt_header_rejects_explicit_null_crit() -> None:
    """Reject an explicitly present null ``crit`` value instead of treating it as absent."""

    with pytest.raises(HTTPException) as exc_info:
        auth._validate_jwt_header({"alg": "RS256", "crit": None})

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "invalid crit header"
