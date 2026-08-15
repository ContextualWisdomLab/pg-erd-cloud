from pydantic import ValidationError
import pytest
from app.schemas import ApplySqlIn


def test_apply_sql_in_valid():
    ApplySqlIn(sql="CREATE TABLE test (id int)")
    ApplySqlIn(sql="ALTER TABLE test ADD COLUMN name text")
    ApplySqlIn(sql="DROP TABLE test")
    ApplySqlIn(sql="TRUNCATE TABLE test")
    ApplySqlIn(sql="COMMENT ON TABLE test IS 'A table'")

def test_apply_sql_in_invalid():
    with pytest.raises(ValidationError):
        ApplySqlIn(sql="")
    with pytest.raises(ValidationError):
        ApplySqlIn(sql=" ")
    with pytest.raises(ValidationError):
        ApplySqlIn(sql="CREATE TABLE test (id int);")
    with pytest.raises(ValidationError):
        ApplySqlIn(sql="CREATE TABLE test (id int) -- comment")
    with pytest.raises(ValidationError):
        ApplySqlIn(sql="CREATE TABLE test (id int) /* comment */")
    with pytest.raises(ValidationError):
        ApplySqlIn(sql="SELECT * FROM test")
    with pytest.raises(ValidationError):
        ApplySqlIn(sql="INSERT INTO test (id) VALUES (1)")
    with pytest.raises(ValidationError):
        ApplySqlIn(sql="UPDATE test SET id=1")
    with pytest.raises(ValidationError):
        ApplySqlIn(sql="DELETE FROM test")
