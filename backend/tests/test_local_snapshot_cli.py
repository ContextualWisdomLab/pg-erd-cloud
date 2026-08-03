from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pytest

from app import local_snapshot_cli


class FakeConnection:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


def test_socket_directory_requires_existing_absolute_directory(tmp_path: Path) -> None:
    assert local_snapshot_cli._socket_directory(str(tmp_path)) == str(tmp_path)
    with pytest.raises(argparse.ArgumentTypeError):
        local_snapshot_cli._socket_directory("relative/socket")
    with pytest.raises(argparse.ArgumentTypeError):
        local_snapshot_cli._socket_directory(str(tmp_path / "missing"))


def test_environment_host_default_cannot_bypass_socket_boundary(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("PGDATABASE", "catalog")
    monkeypatch.setenv("PGHOST", "db.example.com")

    with pytest.raises(SystemExit) as exc_info:
        local_snapshot_cli.build_parser().parse_args([])

    assert exc_info.value.code == 2
    assert "absolute PostgreSQL Unix socket directory" in capsys.readouterr().err


def test_parser_requires_explicit_host_without_pghost(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("PGDATABASE", "catalog")
    monkeypatch.delenv("PGHOST", raising=False)

    with pytest.raises(SystemExit) as exc_info:
        local_snapshot_cli.build_parser().parse_args([])

    assert exc_info.value.code == 2
    assert "--host" in capsys.readouterr().err


@pytest.mark.parametrize("value", ["not-a-port", "0", "65536"])
def test_port_rejects_invalid_values(value: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        local_snapshot_cli._port(value)


def test_schema_name_rejects_sql_fragments() -> None:
    assert local_snapshot_cli._schema_name("catalog_v2") == "catalog_v2"
    with pytest.raises(argparse.ArgumentTypeError):
        local_snapshot_cli._schema_name("public; DROP SCHEMA public")


@pytest.mark.asyncio
async def test_capture_uses_local_connection_without_password_or_dsn(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, Any] = {}
    connection = FakeConnection()

    async def fake_connect(**kwargs: object) -> FakeConnection:
        captured.update(kwargs)
        return connection

    async def fake_collect(conn: FakeConnection, schema: str | None) -> dict:
        assert conn is connection
        return {"schema_filter": schema, "relations": []}

    monkeypatch.setattr(local_snapshot_cli.asyncpg, "connect", fake_connect)
    monkeypatch.setattr(
        local_snapshot_cli,
        "collect_postgres_snapshot",
        fake_collect,
    )
    args = argparse.Namespace(
        database="catalog",
        host=str(tmp_path),
        port=5432,
        user="operator",
        schema="public",
        pretty=False,
    )

    snapshot = await local_snapshot_cli.capture_local_snapshot(args)

    assert snapshot == {"schema_filter": "public", "relations": []}
    assert captured == {
        "database": "catalog",
        "host": str(tmp_path),
        "port": 5432,
        "timeout": 10,
        "user": "operator",
    }
    assert "dsn" not in captured
    assert "password" not in captured
    assert connection.closed is True


@pytest.mark.parametrize(
    ("error", "error_name"),
    [
        (OSError("socket denied"), "OSError"),
        (local_snapshot_cli.asyncpg.PostgresError("database denied"), "PostgresError"),
    ],
)
def test_main_redacts_connection_errors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    error: Exception,
    error_name: str,
) -> None:
    async def fail_capture(_args: argparse.Namespace) -> dict:
        raise error

    monkeypatch.setattr(local_snapshot_cli, "capture_local_snapshot", fail_capture)

    status = local_snapshot_cli.main(
        ["--database", "catalog", "--host", str(tmp_path)]
    )

    assert status == 1
    assert capsys.readouterr().err == f"pg-erd-snapshot failed: {error_name}\n"
