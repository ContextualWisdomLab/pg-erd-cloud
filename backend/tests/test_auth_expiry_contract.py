from __future__ import annotations

import pytest
from fastapi import HTTPException

from app import auth


def test_jwt_expiry_rejects_unrepresentable_numeric_timestamp() -> None:
    with pytest.raises(HTTPException) as exc_info:
        auth._jwt_expiry({"exp": 10**100})

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "invalid token"
