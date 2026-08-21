from __future__ import annotations

import json

import pytest

from app.settings import settings
from app.spec.index_design import generate_index_design_spec


def _snapshot() -> dict:
    return {
        "source_dialect": "postgresql",
        "server_version": "16.4",
        "captured_at": "2026-06-20T00:00:00+00:00",
        "relations": [
            {
                "schema_name": "public",
                "relation_name": "users",
                "relation_oid": 1,
                "relation_kind": "r",
            },
            {
                "schema_name": "public",
                "relation_name": "orders",
                "relation_oid": 2,
                "relation_kind": "r",
            },
        ],
        "columns": [
            {
                "relation_oid": 2,
                "column_position": 1,
                "column_name": "user_id",
                "data_type": "integer",
                "is_not_null": True,
            }
        ],
        "indexes": [],
        "fk_edges": [
            {
                "fk_constraint_name": "orders_user_id_fkey",
                "child_relation_oid": 2,
                "child_schema_name": "public",
                "child_relation_name": "orders",
                "child_column_name": "user_id",
                "parent_relation_oid": 1,
                "parent_schema_name": "public",
                "parent_relation_name": "users",
                "parent_column_name": "id",
                "column_ordinal": 1,
            }
        ],
        "citus_distributed_tables": [
            {
                "relation_oid": 2,
                "schema_name": "public",
                "relation_name": "orders",
                "distribution_method": "h",
                "distribution_key": "user_id",
                "colocation_id": 7,
                "shard_count": 32,
                "replication_factor": 2,
            }
        ],
        "explain_analyze": [
            {"query": "select * from orders where user_id = $1", "actual_ms": 42}
        ],
    }


def test_generate_index_design_markdown_includes_concurrent_index_and_citus(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "job_queue_backend", "valkey")
    monkeypatch.setattr(settings, "valkey_url", None)
    monkeypatch.setattr(settings, "valkey_sentinel_hosts", "s1.local:26379")
    monkeypatch.setattr(settings, "valkey_sentinel_master", "mymaster")

    markdown = generate_index_design_spec(_snapshot())

    assert "# ERD Index Design" in markdown
    assert "CREATE INDEX CONCURRENTLY" in markdown
    assert '"idx_orders_user_id" ON "public"."orders"' in markdown
    assert "orders_user_id_fkey" in markdown
    assert "| public.orders | h | user_id | 7 | 32 | 2 |" in markdown
    assert "- Mode: sentinel" in markdown
    assert "- Sentinel count: 1" in markdown
    assert "s1.local" not in markdown


def test_generate_index_design_llm_prompt_contains_compact_json_summary() -> None:
    prompt = generate_index_design_spec(_snapshot(), mode="llm-prompt")

    assert "# ERD Index Design Prompt" in prompt
    assert "CREATE INDEX CONCURRENTLY" in prompt
    payload = prompt.split("```json\n", 1)[1].split("\n```", 1)[0]
    summary = json.loads(payload)
    assert summary["tables"][0]["name"] == "public.orders"
    assert summary["candidate_indexes"][0]["index_name"] == "idx_orders_user_id"
    assert summary["workload_observations"][0]["actual_ms"] == 42
