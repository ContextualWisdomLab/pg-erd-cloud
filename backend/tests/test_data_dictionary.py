from __future__ import annotations

from app.spec.data_dictionary import col_or_q, snapshot_to_data_dictionary_md


def test_col_or_q() -> None:
    """Render missing values explicitly and preserve deterministic scalar text."""

    assert col_or_q("value") == "value"
    assert col_or_q(123) == "123"
    assert col_or_q(True) == "True"
    assert col_or_q(None) == "?"


def test_col_or_q() -> None:
    """Render missing values explicitly and preserve deterministic scalar text."""

    assert col_or_q("value") == "value"
    assert col_or_q(123) == "123"
    assert col_or_q(True) == "True"
    assert col_or_q(None) == "?"


def _snapshot() -> dict[str, object]:
    """Return one representative PostgreSQL snapshot for dictionary tests."""

    return {
        "captured_at": "2026-07-05T00:00:00Z",
        "server_version": "16.2",
        "relations": [
            {
                "relation_oid": 1,
                "schema_name": "public",
                "relation_name": "member",
                "relation_kind": "r",
                "relation_comment": "회원 마스터",
            },
            {
                "relation_oid": 2,
                "schema_name": "public",
                "relation_name": "orders",
                "relation_kind": "r",
            },
            {
                "relation_oid": 3,
                "schema_name": "public",
                "relation_name": "active_members",
                "relation_kind": "v",
            },
        ],
        "columns": [
            {
                "relation_oid": 1,
                "column_position": 1,
                "column_name": "member_id",
                "data_type": "bigint",
                "is_not_null": True,
                "example_value": "1001",
            },
            {
                "relation_oid": 1,
                "column_position": 2,
                "column_name": "email",
                "data_type": "varchar(100)",
                "is_not_null": False,
                "has_default": True,
                "default_expr": "''::varchar",
                "column_comment": "a|b",
            },
            {
                "relation_oid": 2,
                "column_position": 1,
                "column_name": "order_id",
                "data_type": "bigint",
                "is_not_null": True,
            },
            {
                "relation_oid": 2,
                "column_position": 2,
                "column_name": "member_id",
                "data_type": "bigint",
                "is_not_null": True,
            },
        ],
        "pk_columns": [
            {"relation_oid": 1, "column_name": "member_id", "column_ordinal": 1},
            {"relation_oid": 2, "column_name": "order_id", "column_ordinal": 1},
        ],
        "fk_edges": [
            {
                "fk_constraint_name": "fk_orders_member",
                "child_relation_oid": 2,
                "parent_relation_oid": 1,
                "child_column_name": "member_id",
                "parent_column_name": "member_id",
                "column_ordinal": 1,
            }
        ],
        "indexes": [
            {
                "relation_oid": 1,
                "index_name": "member_pkey",
                "is_unique": True,
                "is_primary": True,
            },
            {
                "relation_oid": 1,
                "index_name": "ix_member_email",
                "is_unique": True,
                "is_primary": False,
            },
        ],
    }


def test_renders_tables_columns_keys_and_metadata() -> None:
    """Render relation metadata, column properties, defaults, and escaped text."""

    md = snapshot_to_data_dictionary_md(_snapshot())
    assert md.startswith("# Data Dictionary")
    assert "Captured: 2026-07-05T00:00:00Z" in md
    assert "## public.member" in md
    assert "회원 마스터" in md
    assert "| member_id | bigint | NOT NULL |" in md
    assert "| PK |" in md or " PK " in md
    assert "1001" in md
    assert "''::varchar" in md
    assert "a\\|b" in md


def test_renders_foreign_keys_and_non_primary_indexes() -> None:
    """Render foreign-key evidence and omit primary indexes from index details."""

    md = snapshot_to_data_dictionary_md(_snapshot())
    assert "**Foreign keys:**" in md
    assert "`member_id` → `public.member.member_id`" in md
    assert "(fk_orders_member)" in md
    assert "**Indexes:**" in md
    assert "UNIQUE `ix_member_email`" in md
    assert "member_pkey" not in md.split("**Indexes:**", 1)[-1]


def test_merges_project_annotations() -> None:
    """Merge project-owned table annotations into generated Markdown."""

    md = snapshot_to_data_dictionary_md(
        _snapshot(),
        annotations=[
            {
                "schema_name": "public",
                "relation_name": "orders",
                "body": "주문 트랜잭션 테이블",
            }
        ],
    )
    assert "> 📝 주문 트랜잭션 테이블" in md


def test_labels_views_and_handles_empty_snapshot() -> None:
    """Label views and return an explicit message for an empty snapshot."""

    md = snapshot_to_data_dictionary_md(_snapshot())
    assert "## public.active_members" in md
    assert "_view_" in md
    empty = snapshot_to_data_dictionary_md({})
    assert "No tables in this snapshot" in empty
