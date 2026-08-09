from __future__ import annotations

import pytest
from fastapi import HTTPException

from app import auth


@pytest.mark.parametrize(
    ("critical_header", "detail"),
    [
        (None, "invalid crit header"),
        ([], "invalid crit header"),
        ("b64", "invalid crit header"),
        (["b64", 1], "invalid crit header"),
        ([f"ext-{index}" for index in range(11)], "invalid crit header"),
        ([f"ext-{index}" for index in range(10)], "critical headers are not supported"),
        (["b64"], "critical headers are not supported"),
    ],
)
def test_rejects_every_declared_critical_header(
    critical_header: object,
    detail: str,
) -> None:
    """Reject malformed, excessive, and unsupported JWS critical headers."""

    with pytest.raises(HTTPException) as exc_info:
        auth._validate_jwt_header({"alg": "RS256", "crit": critical_header})

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == detail


def test_accepts_header_without_critical_extensions() -> None:
    """Preserve the configured algorithm when no critical extension is declared."""

    assert auth._validate_jwt_header({"alg": "RS256"}) == "RS256"
