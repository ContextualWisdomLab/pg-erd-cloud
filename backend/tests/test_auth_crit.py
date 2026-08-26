import pytest
from fastapi import HTTPException
from app.auth import _validate_jwt_header

def test_crit_validates_as_list():
    with pytest.raises(HTTPException) as exc_info:
        _validate_jwt_header({"alg": "RS256", "crit": "not-a-list"})
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "invalid token"

def test_crit_rejects_empty_list():
    with pytest.raises(HTTPException) as exc_info:
        _validate_jwt_header({"alg": "RS256", "crit": []})
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "invalid token"

def test_crit_rejects_long_list():
    with pytest.raises(HTTPException) as exc_info:
        _validate_jwt_header({"alg": "RS256", "crit": ["item"] * 11})
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "invalid token"

def test_crit_rejects_non_string_items():
    with pytest.raises(HTTPException) as exc_info:
        _validate_jwt_header({"alg": "RS256", "crit": [123]})
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "invalid token"

def test_crit_rejects_unrecognized_items():
    with pytest.raises(HTTPException) as exc_info:
        _validate_jwt_header({"alg": "RS256", "crit": ["b64"]})
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "invalid token"
