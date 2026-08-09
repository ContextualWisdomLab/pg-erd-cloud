from __future__ import annotations

import pytest
from fastapi import HTTPException

from app import auth


def test_rejects_empty_critical_header_list() -> None:
    """Reject an empty RFC 7515 critical-header list before token verification."""

    with pytest.raises(HTTPException) as exc_info:
        auth._validate_jwt_header({"alg": "RS256", "crit": []})

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "critical headers are not supported"
