import pytest
from unittest.mock import MagicMock
from app.mysql_introspect.introspect import _introspect_sync, MysqlDsnConfig, _SYSTEM_SCHEMAS

def test_mysql_introspect_sync_parameterization(monkeypatch):
    mock_connect = MagicMock()
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor

    # Mock _fetch_dicts to just return empty lists and record calls
    fetch_calls = []
    def mock_fetch(cursor, sql, params=()):
        fetch_calls.append((sql, params))
        # Return a fake version row for the first call
        if "SELECT VERSION()" in sql:
            return [{"v": "8.0.35"}]
        return []

    monkeypatch.setattr("app.mysql_introspect.introspect._connect", mock_connect)
    monkeypatch.setattr("app.mysql_introspect.introspect._fetch_dicts", mock_fetch)

    config = MysqlDsnConfig(host="127.0.0.1", server_hostname="localhost", port=3306, user="test", password="pw", database=None)

    # Test with a specific schema filter
    _introspect_sync(config, "mydb")

    # Check that parameters are exactly as expected
    assert len(fetch_calls) == 5 # version, tables, columns, key_usage, indexes

    # Check the tables query parameterization
    sql, params = fetch_calls[1]
    assert "WHERE (%s IS NULL AND TABLE_SCHEMA NOT IN (%s, %s, %s, %s)) OR TABLE_SCHEMA = %s " in sql
    assert params == ("mydb", *_SYSTEM_SCHEMAS, "mydb")

    fetch_calls.clear()

    # Test with no schema filter
    _introspect_sync(config, None)

    # Check the tables query parameterization for None
    sql, params = fetch_calls[1]
    assert params == (None, *_SYSTEM_SCHEMAS, None)
