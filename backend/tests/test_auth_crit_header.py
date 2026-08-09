from __future__ import annotations

import pytest
from fastapi import HTTPException

from app import auth


def test_validate_jwt_header_accepts_absent_crit() -> None:
    """An ordinary supported header without ``crit`` remains valid."""

    assert auth._validate_jwt_header({"alg": "RS256"}) == "RS256"


@pytest.mark.parametrize(
    ("crit", "detail"),
    [
        (None, "invalid crit header"),
        ("b64", "invalid crit header"),
        ([], "invalid crit header"),
        (["b64", 1], "invalid crit header"),
        ([f"ext-{index}" for index in range(11)], "invalid crit header"),
        (["b64"], "unsupported critical extension"),
    ],
)
def test_validate_jwt_header_rejects_every_present_crit(
    crit: object,
    detail: str,
) -> None:
    """Any present ``crit`` is rejected because no extension is supported."""

    with pytest.raises(HTTPException) as exc_info:
        auth._validate_jwt_header({"alg": "RS256", "crit": crit})

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == detail
