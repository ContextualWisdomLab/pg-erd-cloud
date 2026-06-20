from __future__ import annotations

import json

from app.spec.reversing import generate_reversing_spec


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
                "relation_comment": "Application users",
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
                "relation_oid": 1,
                "column_position": 1,
                "column_name": "id",
                "data_type": "integer",
                "is_not_null": True,
                "column_comment": "User id",
            },
            {
                "relation_oid": 1,
                "column_position": 2,
                "column_name": "email",
                "data_type": "text",
                "is_not_null": True,
            },
            {
                "relation_oid": 2,
                "column_position": 1,
                "column_name": "user_id",
                "data_type": "integer",
                "is_not_null": True,
            },
        ],
        "constraints": [
            {
                "relation_oid": 1,
                "constraint_name": "users_pkey",
                "constraint_type": "p",
                "constraint_def": "PRIMARY KEY (id)",
            }
        ],
        "indexes": [
            {
                "relation_oid": 1,
                "index_name": "users_email_idx",
                "access_method": "btree",
                "is_unique": True,
                "is_primary": False,
            }
        ],
        "fk_edges": [
            {
                "fk_constraint_name": "orders_user_id_fkey",
                "child_schema_name": "public",
                "child_relation_name": "orders",
                "child_column_name": "user_id",
                "parent_schema_name": "public",
                "parent_relation_name": "users",
                "parent_column_name": "id",
            }
        ],
    }


def test_generate_reversing_markdown_includes_entities_and_relationships() -> None:
    markdown = generate_reversing_spec(_snapshot())

    assert "# DB Reversing Specification" in markdown
    assert "### public.users" in markdown
    assert "| id | integer | yes | - | User id |" in markdown
    assert "users_pkey (p): PRIMARY KEY (id)" in markdown
    assert "users_email_idx [unique, method=btree]" in markdown
    assert "public.orders.user_id -> public.users.id" in markdown
    assert "/reversing-spec.md?mode=llm-prompt" in markdown


def test_generate_reversing_llm_prompt_contains_compact_json_summary() -> None:
    prompt = generate_reversing_spec(_snapshot(), mode="llm-prompt")

    assert "# DB Reversing Specification Prompt" in prompt
    assert "Do not invent facts" in prompt
    payload = prompt.split("```json\n", 1)[1].split("\n```", 1)[0]
    summary = json.loads(payload)
    assert summary["source_dialect"] == "postgresql"
    assert summary["objects"][0]["name"] == "public.users"
    assert summary["relationships"][0]["constraint"] == "orders_user_id_fkey"
