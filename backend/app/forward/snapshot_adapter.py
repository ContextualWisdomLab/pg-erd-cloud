"""Convert reverse-engineering snapshots to the editable model contract.

This adapter is deliberately loss-intolerant.  It removes volatile PostgreSQL
OIDs only after resolving them within the same snapshot, and rejects any object
class compiler v1 cannot yet preserve and execute.  That makes an unsupported
database an explicit planning blocker instead of a deceptively incomplete
target model.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Mapping
from typing import Any

from app.forward.schema_model import (
    SchemaModelValidationError,
    canonicalize_schema_model,
)
from app.pg_introspect.snapshot_contract import (
    CURRENT_POSTGRES_SNAPSHOT_CONTRACT_VERSION,
)


def _postgresql_major(snapshot: Mapping[str, Any]) -> int:
    numeric = snapshot.get("server_version_num")
    if isinstance(numeric, int) and not isinstance(numeric, bool):
        major = numeric // 10_000
    else:
        match = re.match(r"\s*(\d+)", str(snapshot.get("server_version") or ""))
        major = int(match.group(1)) if match else 0
    if major < 14 or major > 18:
        raise SchemaModelValidationError(
            "snapshot PostgreSQL major version is missing or unsupported"
        )
    return major


def snapshot_to_schema_model(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Return canonical v1 model JSON for a supported PostgreSQL snapshot."""

    if (
        snapshot.get("snapshot_contract_version")
        != CURRENT_POSTGRES_SNAPSHOT_CONTRACT_VERSION
    ):
        raise SchemaModelValidationError(
            "snapshot capability contract is outdated; recapture is required"
        )
    if snapshot.get("fk_edges"):
        raise SchemaModelValidationError(
            "snapshot foreign keys are not supported by compiler v1"
        )
    if snapshot.get("citus_distributed_tables"):
        raise SchemaModelValidationError(
            "snapshot distributed tables are not supported by compiler v1"
        )

    relations = snapshot.get("relations")
    columns = snapshot.get("columns")
    raw_schemas = snapshot.get("schemas")
    primary_keys = snapshot.get("pk_columns") or []
    constraints = snapshot.get("constraints") or []
    indexes = snapshot.get("indexes") or []
    if not isinstance(relations, list) or not isinstance(columns, list):
        raise SchemaModelValidationError(
            "snapshot relations and columns must be lists"
        )
    if raw_schemas is not None and not isinstance(raw_schemas, list):
        raise SchemaModelValidationError("snapshot schemas must be a list")
    if not isinstance(constraints, list):
        raise SchemaModelValidationError("snapshot constraints must be a list")
    if not isinstance(indexes, list):
        raise SchemaModelValidationError("snapshot indexes must be a list")

    oid_to_relation: dict[object, Mapping[str, Any]] = {}
    for relation in relations:
        if not isinstance(relation, Mapping):
            raise SchemaModelValidationError("snapshot relation must be an object")
        if relation.get("relation_kind") != "r":
            raise SchemaModelValidationError(
                "snapshot relation kind is not supported by compiler v1"
            )
        if relation.get("has_dropped_columns") not in {None, False}:
            raise SchemaModelValidationError(
                "snapshot relations with dropped columns are not supported by compiler v1"
            )
        if relation.get("is_partition") not in {None, False} or any(
            relation.get(field) is not None
            for field in (
                "partition_key",
                "partition_bound",
                "partition_parent_oid",
                "partition_parent_schema",
                "partition_parent_name",
            )
        ):
            raise SchemaModelValidationError(
                "snapshot partition metadata is not supported by compiler v1"
            )
        if relation.get("tablespace_name") is not None:
            raise SchemaModelValidationError(
                "snapshot tablespace metadata is not supported by compiler v1"
            )
        relation_oid = relation.get("relation_oid")
        if relation_oid is None:
            raise SchemaModelValidationError("snapshot relation OID is missing")
        if relation_oid in oid_to_relation:
            raise SchemaModelValidationError(
                "snapshot contains a duplicate relation OID"
            )
        oid_to_relation[relation_oid] = relation

    columns_by_oid: dict[object, list[dict[str, Any]]] = defaultdict(list)
    for column in columns:
        if not isinstance(column, Mapping):
            raise SchemaModelValidationError("snapshot column must be an object")
        oid = column.get("relation_oid")
        if oid not in oid_to_relation:
            raise SchemaModelValidationError("snapshot column references unknown relation")
        if (
            column.get("has_default") not in {None, False}
            or column.get("default_expr") is not None
            or any(
                column.get(field) is not None
                for field in ("column_default",)
            )
            or any(
                column.get(field) not in {None, ""}
                for field in ("identity", "generated")
            )
        ):
            raise SchemaModelValidationError(
                "snapshot default, identity, or generated columns are not supported by compiler v1"
            )
        columns_by_oid[oid].append(
            {
                "column_name": column.get("column_name"),
                "data_type": column.get("data_type"),
                "nullable": not bool(column.get("is_not_null")),
                "ordinal_position": column.get("column_position")
                or column.get("ordinal_position"),
                "comment": column.get("column_comment"),
            }
        )

    pk_by_oid: dict[object, list[Mapping[str, Any]]] = defaultdict(list)
    for primary_key_row in primary_keys:
        if not isinstance(primary_key_row, Mapping):
            raise SchemaModelValidationError("snapshot primary key must be an object")
        oid = primary_key_row.get("relation_oid")
        if oid not in oid_to_relation:
            raise SchemaModelValidationError(
                "snapshot primary key references unknown relation"
            )
        pk_by_oid[oid].append(primary_key_row)

    for constraint_row in constraints:
        if not isinstance(constraint_row, Mapping):
            raise SchemaModelValidationError("snapshot constraint must be an object")
        if constraint_row.get("constraint_type") != "p":
            raise SchemaModelValidationError(
                "snapshot constraints other than primary keys are not supported by compiler v1"
            )
        relation_oid = constraint_row.get("relation_oid")
        matching_key_rows = pk_by_oid.get(relation_oid, [])
        constraint_name = constraint_row.get("constraint_name")
        constraint_oid = constraint_row.get("constraint_oid")
        represented = any(
            key_row.get("constraint_name") == constraint_name
            and (
                constraint_oid is None
                or key_row.get("constraint_oid") is None
                or key_row.get("constraint_oid") == constraint_oid
            )
            for key_row in matching_key_rows
        )
        if not represented:
            raise SchemaModelValidationError(
                "snapshot primary key constraint is not represented by pk_columns"
            )

    for index_row in indexes:
        if not isinstance(index_row, Mapping):
            raise SchemaModelValidationError("snapshot index must be an object")
        relation_oid = index_row.get("relation_oid", index_row.get("table_oid"))
        if index_row.get("is_primary") is not True or not pk_by_oid.get(relation_oid):
            raise SchemaModelValidationError(
                "snapshot indexes other than primary-key backing indexes are not supported by compiler v1"
            )

    schemas: dict[str, list[dict[str, Any]]] = defaultdict(list)
    declared_schema_names: set[str] | None = None
    if isinstance(raw_schemas, list):
        declared_schema_names = set()
        for schema_row in raw_schemas:
            if not isinstance(schema_row, Mapping):
                raise SchemaModelValidationError("snapshot schema must be an object")
            schema_name = str(schema_row.get("schema_name") or "")
            if schema_name in declared_schema_names:
                raise SchemaModelValidationError("snapshot contains a duplicate schema")
            declared_schema_names.add(schema_name)
            schemas[schema_name]
    for oid, relation in oid_to_relation.items():
        key_parts = sorted(
            pk_by_oid.get(oid, []), key=lambda item: int(item.get("column_ordinal") or 0)
        )
        primary_key: dict[str, Any] | None = None
        if key_parts:
            names = {str(item.get("constraint_name") or "") for item in key_parts}
            if len(names) != 1 or "" in names:
                raise SchemaModelValidationError(
                    "snapshot primary key has ambiguous constraint names"
                )
            primary_key = {
                "constraint_name": next(iter(names)),
                "columns": [str(item.get("column_name") or "") for item in key_parts],
                "deferrable": bool(key_parts[0].get("is_deferrable")),
                "initially_deferred": bool(
                    key_parts[0].get("is_initially_deferred")
                ),
            }
        schema_name = str(relation.get("schema_name") or "")
        if declared_schema_names is not None and schema_name not in declared_schema_names:
            raise SchemaModelValidationError(
                "snapshot relation references an undeclared schema"
            )
        schemas[schema_name].append(
            {
                "table_name": relation.get("relation_name"),
                "comment": relation.get("relation_comment"),
                "columns": columns_by_oid.get(oid, []),
                "primary_key": primary_key,
                "unique_constraints": [],
                "foreign_keys": [],
                "indexes": [],
                "unsupported_features": [],
            }
        )

    model = {
        "format_version": 1,
        "postgresql_major": _postgresql_major(snapshot),
        "schemas": [
            {"schema_name": schema_name, "tables": tables}
            for schema_name, tables in schemas.items()
        ],
    }
    return canonicalize_schema_model(model)
