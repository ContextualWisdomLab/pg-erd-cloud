from pydantic import ValidationError
import pytest
from app.schemas import ApplySqlIn

def test_apply_sql_unicode_bypass():
    with pytest.raises(ValidationError):
        ApplySqlIn(sql="CREATE TABLE\u3000test (id INT；)")

    with pytest.raises(ValidationError):
        ApplySqlIn(sql="CREATE TABLE test (id INT);")
    with pytest.raises(ValidationError):
        ApplySqlIn(sql="CREATE TABLE\u3000\u3000test (id INT);")
