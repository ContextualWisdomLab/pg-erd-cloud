from __future__ import annotations

import pytest

from app.forward.schema_model import SchemaModelValidationError
from app.forward.snapshot_adapter import snapshot_to_schema_model


def _snapshot() -> dict:
    return {
        "snapshot_contract_version": 1,
        "server_version_num": 180002,
        "schemas": [{"schema_oid": 11, "schema_name": "Sales Data"}],
        "relations": [
            {
                "relation_oid": 42,
                "schema_name": "Sales Data",
                "relation_name": 'Order "Item"',
                "relation_kind": "r",
                "relation_comment": "Line items",
            }
        ],
        "columns": [
            {
                "relation_oid": 42,
                "column_name": "Description",
                "data_type": "text",
                "is_not_null": False,
                "column_position": 2,
            },
            {
                "relation_oid": 42,
                "column_name": "Item ID",
                "data_type": "bigint",
                "is_not_null": True,
                "column_position": 1,
            },
        ],
        "pk_columns": [
            {
                "constraint_oid": 700,
                "relation_oid": 42,
                "constraint_name": 'Order "Item" pkey',
                "column_name": "Item ID",
                "column_ordinal": 1,
                "is_deferrable": False,
                "is_initially_deferred": False,
            }
        ],
        "constraints": [],
        "fk_edges": [],
        "indexes": [],
    }


def test_snapshot_adapter_requires_current_capability_contract() -> None:
    snapshot = _snapshot()
    snapshot.pop("snapshot_contract_version")

    with pytest.raises(SchemaModelValidationError, match=r"recapture|required"):
        snapshot_to_schema_model(snapshot)


def test_snapshot_adapter_removes_oids_and_preserves_supported_semantics() -> None:
    model = snapshot_to_schema_model(_snapshot())

    assert model["postgresql_major"] == 18
    table = model["schemas"][0]["tables"][0]
    assert table["table_name"] == 'Order "Item"'
    assert [column["column_name"] for column in table["columns"]] == [
        "Item ID",
        "Description",
    ]
    assert table["primary_key"]["constraint_name"] == 'Order "Item" pkey'
    assert "relation_oid" not in table


def test_snapshot_adapter_accepts_server_version_text_and_table_without_pk() -> None:
    snapshot = _snapshot()
    snapshot.pop("server_version_num")
    snapshot["server_version"] = " 17.9 (Ubuntu)"
    snapshot["pk_columns"] = []

    model = snapshot_to_schema_model(snapshot)

    assert model["postgresql_major"] == 17
    assert model["schemas"][0]["tables"][0]["primary_key"] is None


@pytest.mark.parametrize(
    "default_metadata",
    [
        {"has_default": True, "default_expr": "0"},
        {"has_default": False, "default_expr": "nextval('items_id_seq')"},
    ],
)
def test_snapshot_adapter_rejects_actual_default_metadata(
    default_metadata: dict[str, object],
) -> None:
    snapshot = _snapshot()
    snapshot["columns"][0].update(default_metadata)

    with pytest.raises(SchemaModelValidationError, match="default"):
        snapshot_to_schema_model(snapshot)


def test_snapshot_adapter_preserves_primary_key_deferral_metadata() -> None:
    snapshot = _snapshot()
    snapshot["pk_columns"][0]["is_deferrable"] = True
    snapshot["pk_columns"][0]["is_initially_deferred"] = True

    model = snapshot_to_schema_model(snapshot)

    primary_key = model["schemas"][0]["tables"][0]["primary_key"]
    assert primary_key["deferrable"] is True
    assert primary_key["initially_deferred"] is True


@pytest.mark.parametrize(
    "generated_metadata",
    [{"identity": "a"}, {"identity": "d"}, {"generated": "s"}],
)
def test_snapshot_adapter_rejects_identity_and_generated_catalog_metadata(
    generated_metadata: dict[str, object],
) -> None:
    snapshot = _snapshot()
    snapshot["columns"][0].update(generated_metadata)

    with pytest.raises(SchemaModelValidationError, match=r"identity|generated"):
        snapshot_to_schema_model(snapshot)


def test_snapshot_adapter_preserves_empty_schema_names() -> None:
    snapshot = _snapshot()
    snapshot["schemas"].append({"schema_oid": 12, "schema_name": "empty_schema"})

    model = snapshot_to_schema_model(snapshot)

    schema_tables = {
        schema["schema_name"]: schema["tables"] for schema in model["schemas"]
    }
    assert schema_tables["empty_schema"] == []


def test_snapshot_adapter_allows_realistic_primary_constraint_and_backing_index() -> None:
    snapshot = _snapshot()
    snapshot["constraints"] = [
        {
            "constraint_oid": 700,
            "constraint_name": 'Order "Item" pkey',
            "constraint_type": "p",
            "relation_oid": 42,
        }
    ]
    snapshot["indexes"] = [
        {
            "index_oid": 701,
            "index_name": 'Order "Item" pkey',
            "relation_oid": None,
            "table_oid": 42,
            "is_primary": True,
        }
    ]

    model = snapshot_to_schema_model(snapshot)

    primary_key = model["schemas"][0]["tables"][0]["primary_key"]
    assert primary_key["constraint_name"] == 'Order "Item" pkey'


@pytest.mark.parametrize("constraint_type", ["u", "c", "f"])
def test_snapshot_adapter_rejects_unsupported_constraint_types(
    constraint_type: str,
) -> None:
    snapshot = _snapshot()
    snapshot["constraints"] = [
        {
            "constraint_oid": 800,
            "constraint_name": "unsupported_constraint",
            "constraint_type": constraint_type,
            "relation_oid": 42,
        }
    ]

    with pytest.raises(SchemaModelValidationError, match="constraints"):
        snapshot_to_schema_model(snapshot)


def test_snapshot_adapter_rejects_unrepresented_primary_constraint() -> None:
    snapshot = _snapshot()
    snapshot["constraints"] = [
        {
            "constraint_oid": 800,
            "constraint_name": "different_pkey",
            "constraint_type": "p",
            "relation_oid": 42,
        }
    ]

    with pytest.raises(
        SchemaModelValidationError, match="not represented by pk_columns"
    ):
        snapshot_to_schema_model(snapshot)


@pytest.mark.parametrize(
    "relation_metadata",
    [
        {"relation_kind": "p"},
        {"is_partition": True},
        {"partition_key": "RANGE (created_at)"},
        {"partition_bound": "FOR VALUES FROM ('2026-01-01') TO ('2027-01-01')"},
        {"partition_parent_oid": 7},
        {"partition_parent_schema": "public"},
        {"partition_parent_name": "orders"},
        {"tablespace_name": "fast_storage"},
    ],
)
def test_snapshot_adapter_rejects_partition_and_tablespace_metadata(
    relation_metadata: dict[str, object],
) -> None:
    snapshot = _snapshot()
    snapshot["relations"][0].update(relation_metadata)

    with pytest.raises(
        SchemaModelValidationError, match=r"partition|tablespace|relation kind"
    ):
        snapshot_to_schema_model(snapshot)


def test_snapshot_adapter_rejects_relations_with_dropped_column_slots() -> None:
    snapshot = _snapshot()
    snapshot["relations"][0]["has_dropped_columns"] = True

    with pytest.raises(SchemaModelValidationError, match="dropped columns"):
        snapshot_to_schema_model(snapshot)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda snapshot: snapshot["relations"][0].update({"relation_kind": "v"}),
            "relation kind",
        ),
        (
            lambda snapshot: snapshot.update({"fk_edges": [{"fk_constraint_oid": 1}]}),
            "foreign keys",
        ),
        (
            lambda snapshot: snapshot.update({"indexes": [{"index_oid": 1}]}),
            "indexes",
        ),
        (
            lambda snapshot: snapshot.update({"server_version_num": 190000}),
            "PostgreSQL major version",
        ),
        (
            lambda snapshot: snapshot.update({"citus_distributed_tables": [{}]}),
            "distributed tables",
        ),
        (
            lambda snapshot: snapshot.update({"relations": {}}),
            "relations and columns",
        ),
        (
            lambda snapshot: snapshot.update({"columns": {}}),
            "relations and columns",
        ),
        (
            lambda snapshot: snapshot.update({"relations": [1]}),
            "relation must be an object",
        ),
        (
            lambda snapshot: snapshot["relations"].append(
                {**snapshot["relations"][0], "relation_name": "duplicate_oid"}
            ),
            "duplicate relation OID",
        ),
        (
            lambda snapshot: snapshot.update({"columns": [1]}),
            "column must be an object",
        ),
        (
            lambda snapshot: snapshot["columns"][0].update({"relation_oid": 999}),
            "unknown relation",
        ),
        (
            lambda snapshot: snapshot["columns"][0].update({"column_default": "0"}),
            "default, identity, or generated",
        ),
        (
            lambda snapshot: snapshot.update({"pk_columns": [1]}),
            "primary key must be an object",
        ),
        (
            lambda snapshot: snapshot["pk_columns"][0].update({"relation_oid": 999}),
            "primary key references unknown",
        ),
        (
            lambda snapshot: snapshot["pk_columns"].append(
                {
                    **snapshot["pk_columns"][0],
                    "constraint_name": "different_pkey",
                    "column_ordinal": 2,
                }
            ),
            "ambiguous constraint names",
        ),
    ],
)
def test_snapshot_adapter_fails_closed_for_uncompiled_features(mutate, message: str) -> None:
    snapshot = _snapshot()
    mutate(snapshot)

    with pytest.raises(SchemaModelValidationError, match=message):
        snapshot_to_schema_model(snapshot)
