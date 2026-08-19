"""Realistic Prisma identifier allocation regressions."""

from __future__ import annotations

import unicodedata

import pytest

from app.spec.orm_codegen import generate_prisma_schema
from app.spec.prisma_identifiers import (
    PRISMA_EXPORT_FAILURE_SCHEMA,
    PRISMA_IDENTIFIER_CONTRACT_VERSION,
    allocate_prisma_identifiers,
    build_prisma_manifest,
    is_prisma_identifier,
    is_reserved_prisma_name,
    preferred_prisma_name,
    quote_prisma_string,
)


def test_preferred_name_escapes_reserved_without_m_model_collision() -> None:
    """Reserved ``model`` must not consume the ``M_model`` source name."""
    assert preferred_prisma_name("model") == "model_"
    assert preferred_prisma_name("Model") == "Model_"
    assert preferred_prisma_name("MODEL") == "MODEL_"
    assert preferred_prisma_name("M_model") == "M_model"
    assert preferred_prisma_name("model") != preferred_prisma_name("M_model")


def test_punctuation_collisions_are_deterministic() -> None:
    """``order-item``, ``order item``, and ``order_item`` stay unique and stable."""
    sources = ["order-item", "order item", "order_item"]
    forward = allocate_prisma_identifiers(
        [
            {
                "key": f"k{index}",
                "kind": "model",
                "namespace": "models",
                "source": source,
            }
            for index, source in enumerate(sources)
        ]
    )
    reverse = allocate_prisma_identifiers(
        [
            {
                "key": f"k{index}",
                "kind": "model",
                "namespace": "models",
                "source": source,
            }
            for index, source in enumerate(reversed(sources))
        ]
    )
    assert forward["ok"] is True
    assert reverse["ok"] is True
    forward_by_source = {row["source"]: row["generated"] for row in forward["mappings"]}
    reverse_by_source = {row["source"]: row["generated"] for row in reverse["mappings"]}
    assert forward_by_source == reverse_by_source
    assert len(set(forward["names"].values())) == 3


def test_unicode_sources_use_codepoint_order() -> None:
    """Frontend and backend use the same order for non-ASCII collisions."""
    result = allocate_prisma_identifiers(
        [
            {"key": "accent", "kind": "model", "namespace": "models", "source": "é"},
            {"key": "sharp-s", "kind": "model", "namespace": "models", "source": "ß"},
        ]
    )
    assert result["names"]["sharp-s"] == "unnamed"
    assert result["names"]["accent"] == "unnamed_2"


def test_unicode_and_empty_sources_allocate_unique_identifiers() -> None:
    """Korean, emoji, and NFC/NFD Hangul remain traceable through unique names."""
    nfc = unicodedata.normalize("NFC", "가")
    nfd = unicodedata.normalize("NFD", "가")
    result = allocate_prisma_identifiers(
        [
            {"key": "ko", "kind": "model", "namespace": "models", "source": "사용자"},
            {"key": "emoji", "kind": "model", "namespace": "models", "source": "📦"},
            {"key": "nfc", "kind": "model", "namespace": "models", "source": nfc},
            {"key": "nfd", "kind": "model", "namespace": "models", "source": nfd},
        ]
    )
    assert result["ok"] is True
    generated = list(result["names"].values())
    assert len(set(generated)) == 4
    assert all(is_prisma_identifier(name) for name in generated)


def test_allocation_failure_is_closed_and_non_reflecting() -> None:
    """Exhausted bounds fail closed without inventing a colliding name."""
    result = allocate_prisma_identifiers(
        [
            {"key": "a", "kind": "field", "namespace": "fields:users", "source": "id"},
            {"key": "b", "kind": "field", "namespace": "fields:users", "source": "id"},
        ],
        max_attempts=0,
    )
    assert result["ok"] is False
    assert len(result["names"]) == 1


def test_manifest_records_pinned_contract_version() -> None:
    """The manifest names the reserved-word contract buyers can audit."""
    allocated = allocate_prisma_identifiers(
        [{"key": "users", "kind": "model", "namespace": "models", "source": "users"}]
    )
    manifest = build_prisma_manifest(allocated["mappings"])
    assert manifest["contractVersion"] == PRISMA_IDENTIFIER_CONTRACT_VERSION
    assert quote_prisma_string('quote "') == '"quote \\""'


def test_reserved_name_predicates() -> None:
    """Client, scalar, and schema keywords stay reserved."""
    assert is_reserved_prisma_name("class") is True
    assert is_reserved_prisma_name("PrismaClient") is True
    assert is_reserved_prisma_name("String") is True
    assert is_reserved_prisma_name("users") is False


def test_generate_prisma_schema_maps_colliding_tables() -> None:
    """Snapshot export preserves source names when generated identifiers differ."""
    snap = {
        "relations": [
            {"relation_oid": 1, "relation_kind": "r", "schema_name": "public", "relation_name": "model"},
            {"relation_oid": 2, "relation_kind": "r", "schema_name": "public", "relation_name": "M_model"},
            {"relation_oid": 3, "relation_kind": "r", "schema_name": "public", "relation_name": "order-item"},
            {"relation_oid": 4, "relation_kind": "r", "schema_name": "public", "relation_name": "order item"},
        ],
        "columns": [
            {"relation_oid": 1, "column_name": "id", "column_position": 1, "data_type": "int", "is_not_null": True},
            {"relation_oid": 2, "column_name": "id", "column_position": 1, "data_type": "int", "is_not_null": True},
            {"relation_oid": 3, "column_name": "id", "column_position": 1, "data_type": "int", "is_not_null": True},
            {"relation_oid": 4, "column_name": "id", "column_position": 1, "data_type": "int", "is_not_null": True},
        ],
        "pk_columns": [
            {"relation_oid": 1, "column_name": "id"},
            {"relation_oid": 2, "column_name": "id"},
            {"relation_oid": 3, "column_name": "id"},
            {"relation_oid": 4, "column_name": "id"},
        ],
        "fk_edges": [],
    }
    schema = generate_prisma_schema(snap)
    assert '@@map("model")' in schema
    assert '@@map("M_model")' in schema
    assert '@@map("order-item")' in schema
    assert '@@map("order item")' in schema
    assert schema.count("model ") == 4


def test_generate_prisma_schema_failure_does_not_echo_source_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Allocation failure returns the fixed comment, not table names."""
    from app.spec import orm_codegen

    def _fail(
        _requests: list[dict[str, str]],
        max_attempts: int = 10_000,
    ) -> dict[str, object]:
        return {"ok": False, "names": {}, "mappings": []}

    monkeypatch.setattr(orm_codegen, "allocate_prisma_identifiers", _fail)
    schema = generate_prisma_schema(
        {
            "relations": [
                {
                    "relation_oid": 1,
                    "relation_kind": "r",
                    "schema_name": "public",
                    "relation_name": "secret_table",
                }
            ],
            "columns": [],
            "pk_columns": [],
            "fk_edges": [],
        }
    )
    assert schema == PRISMA_EXPORT_FAILURE_SCHEMA
    assert "secret_table" not in schema


def test_generate_prisma_schema_field_allocation_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A later field-allocation failure also stays non-reflecting."""
    from app.spec import orm_codegen
    from app.spec.prisma_identifiers import allocate_prisma_identifiers as real_alloc

    calls = {"count": 0}

    def _maybe_fail(
        requests: list[dict[str, str]],
        max_attempts: int = 10_000,
    ) -> dict[str, object]:
        calls["count"] += 1
        if calls["count"] == 1:
            return real_alloc(requests, max_attempts)
        return {"ok": False, "names": {}, "mappings": []}

    monkeypatch.setattr(orm_codegen, "allocate_prisma_identifiers", _maybe_fail)
    schema = generate_prisma_schema(
        {
            "relations": [
                {
                    "relation_oid": 1,
                    "relation_kind": "r",
                    "schema_name": "public",
                    "relation_name": "secret_table",
                }
            ],
            "columns": [
                {
                    "relation_oid": 1,
                    "column_name": "secret_col",
                    "column_position": 1,
                    "data_type": "int",
                    "is_not_null": True,
                }
            ],
            "pk_columns": [],
            "fk_edges": [],
        }
    )
    assert schema == PRISMA_EXPORT_FAILURE_SCHEMA
    assert "secret_col" not in schema
