from __future__ import annotations

from typing import Literal

import pytest

from app.pg_introspect import snapshot_collect


CitusMode = Literal["absent", "present", "missing_catalog"]


class MissingCitusCatalogError(Exception):
    """Test-only stand-in for asyncpg.UndefinedTableError."""


class FakeConnection:
    """Return deterministic catalog results for the shared snapshot collector."""

    def __init__(self, citus_mode: CitusMode) -> None:
        self.citus_mode = citus_mode
        self.fetch_count = 0

    async def fetchval(self, query: str, *_args: object) -> object:
        if query == "SHOW server_version":
            return "17.10"
        return self.citus_mode != "absent"

    async def fetch(self, *_args: object) -> list[dict[str, object]]:
        self.fetch_count += 1
        if self.fetch_count == 8:
            if self.citus_mode == "missing_catalog":
                raise MissingCitusCatalogError
            return [{"logicalrelid": "public.orders"}]
        return []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("citus_mode", "expected_citus", "expected_fetch_count"),
    [
        ("absent", [], 7),
        ("present", [{"logicalrelid": "public.orders"}], 8),
        ("missing_catalog", [], 8),
    ],
)
async def test_collect_postgres_snapshot_handles_each_citus_state(
    monkeypatch: pytest.MonkeyPatch,
    citus_mode: CitusMode,
    expected_citus: list[dict[str, object]],
    expected_fetch_count: int,
) -> None:
    monkeypatch.setattr(
        snapshot_collect.asyncpg,
        "UndefinedTableError",
        MissingCitusCatalogError,
    )
    connection = FakeConnection(citus_mode)

    result = await snapshot_collect.collect_postgres_snapshot(connection, "public")

    assert result["server_version"] == "17.10"
    assert result["schema_filter"] == "public"
    assert result["schemas"] == []
    assert result["relations"] == []
    assert result["columns"] == []
    assert result["constraints"] == []
    assert result["indexes"] == []
    assert result["pk_columns"] == []
    assert result["fk_edges"] == []
    assert result["citus_distributed_tables"] == expected_citus
    assert isinstance(result["captured_at"], str)
    assert connection.fetch_count == expected_fetch_count
