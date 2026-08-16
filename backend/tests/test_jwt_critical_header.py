"""Regression contracts for fail-closed JOSE critical-header handling."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import HTTPException

from app import auth


def test_jwt_header_without_critical_extensions_remains_supported() -> None:
    """Return the normalized algorithm when no critical extension is declared."""

    assert auth._validate_jwt_header({"alg": "rs256"}) == "RS256"


@pytest.mark.parametrize(
    "critical_value",
    (
        None,
        "extension_name",
        [],
        [1],
        [""],
        ["extension_name", "extension_name"],
    ),
)
def test_jwt_header_rejects_malformed_critical_lists(
    critical_value: Any,
) -> None:
    """Reject null, non-array, empty, non-text, blank, and duplicate lists."""

    with pytest.raises(HTTPException) as error:
        auth._validate_jwt_header(
            {"alg": "RS256", "crit": critical_value},
        )

    assert error.value.status_code == 401
    assert error.value.detail == "invalid crit header"


@pytest.mark.parametrize("registered_name", ("alg", "typ", "cty", "crit"))
def test_jwt_header_rejects_registered_names_as_critical(
    registered_name: str,
) -> None:
    """Reject base JOSE parameters that RFC 7515 forbids in ``crit``."""

    header: dict[str, Any] = {
        "alg": "RS256",
        "crit": [registered_name],
    }
    if registered_name not in header:
        header[registered_name] = "extension_value"

    with pytest.raises(HTTPException) as error:
        auth._validate_jwt_header(header)

    assert error.value.status_code == 401
    assert error.value.detail == "invalid crit header"


def test_jwt_header_rejects_critical_name_missing_from_header() -> None:
    """Reject a critical extension name that has no matching header member."""

    with pytest.raises(HTTPException) as error:
        auth._validate_jwt_header(
            {"alg": "RS256", "crit": ["extension_name"]},
        )

    assert error.value.status_code == 401
    assert error.value.detail == "invalid crit header"


def test_jwt_header_rejects_structurally_valid_unsupported_extension() -> None:
    """Reject an extension that is present but unsupported by this profile."""

    with pytest.raises(HTTPException) as error:
        auth._validate_jwt_header(
            {
                "alg": "RS256",
                "crit": ["https://example.invalid/jose/extension"],
                "https://example.invalid/jose/extension": True,
            },
        )

    assert error.value.status_code == 401
    assert error.value.detail == "unsupported critical parameter"
