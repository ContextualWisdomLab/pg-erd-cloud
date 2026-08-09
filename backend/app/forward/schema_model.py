"""Validate and canonicalize editable PostgreSQL schema models.

The browser supplies an untrusted model, never executable SQL.  This module is
the first server-owned authority boundary: it rejects ambiguous or lossy
objects, removes explicitly volatile capture metadata, and produces stable JSON
whose SHA-256 digest can bind revisions, plans, approvals, dry runs and applies.

Only the deliberately small v1 contract is accepted.  Unknown fields inside
authoritative objects fail closed so a newer client cannot silently lose a
schema feature when an older server compiles it.  PostgreSQL identifiers are
preserved exactly (including Unicode, whitespace, reserved words and quotes);
the SQL renderer is responsible for dialect-correct quoting later.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any


class SchemaModelValidationError(ValueError):
    """Raised when an editable model cannot be represented without ambiguity."""


_MODEL_FIELDS = {"format_version", "postgresql_major", "schemas"}
_SCHEMA_FIELDS = {"schema_name", "tables"}
_TABLE_FIELDS = {
    "table_name",
    "comment",
    "columns",
    "primary_key",
    "unique_constraints",
    "foreign_keys",
    "indexes",
    "unsupported_features",
}
_COLUMN_FIELDS = {
    "column_name",
    "data_type",
    "nullable",
    "ordinal_position",
    "default",
    "identity",
    "generated",
    "comment",
}
_PRIMARY_KEY_FIELDS = {
    "constraint_name",
    "columns",
    "deferrable",
    "initially_deferred",
}
_VOLATILE_MODEL_FIELDS = {"capture_id", "captured_at", "source_snapshot_uuid"}
_VOLATILE_TABLE_FIELDS = {"relation_oid", "captured_at"}
_CANONICAL_DATA_TYPE_RE = re.compile(
    r"(?:"
    r"smallint|integer|bigint|"
    r"real|double\s+precision|money|boolean|"
    r"text|bytea|uuid|json|jsonb|xml|inet|cidr|macaddr|macaddr8|"
    r"tsvector|tsquery|date|"
    r"character\s+varying(?:\(\d+\))?|character\(\d+\)|"
    r"numeric(?:\(\d+(?:,\d+)?\))?|"
    r"(?:timestamp|time)(?:\(\d+\))?\s+(?:with|without)\s+time\s+zone"
    r")(?:\[\])?",
)
_SERIAL_PSEUDO_TYPES = {"smallserial", "serial", "bigserial"}


def _object(value: object, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SchemaModelValidationError(f"{path} must be an object")
    return value


def _list(value: object, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise SchemaModelValidationError(f"{path} must be a list")
    return value


def _check_fields(
    value: Mapping[str, Any], allowed: set[str], path: str, volatile: set[str] | None = None
) -> None:
    unknown = set(value) - allowed - (volatile or set())
    if unknown:
        field = sorted(unknown)[0]
        raise SchemaModelValidationError(f"{path} contains unrecognized field {field!r}")


def _text(value: object, path: str) -> str:
    if not isinstance(value, str):
        raise SchemaModelValidationError(f"{path} must be text")
    if "\x00" in value:
        raise SchemaModelValidationError(f"{path} must not contain NUL")
    if not value:
        raise SchemaModelValidationError(f"{path} must not be empty")
    if len(value.encode("utf-8")) > 63:
        raise SchemaModelValidationError(
            f"{path} exceeds PostgreSQL's 63-byte identifier limit"
        )
    return value


def _optional_text(value: object, path: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise SchemaModelValidationError(f"{path} must be text or null")
    if "\x00" in value:
        raise SchemaModelValidationError(f"{path} must not contain NUL")
    return value


def _boolean(value: object, path: str) -> bool:
    if not isinstance(value, bool):
        raise SchemaModelValidationError(f"{path} must be boolean")
    return value


def _canonical_data_type(value: object, path: str) -> str:
    """Normalize safe SQL type syntax to ``pg_catalog.format_type`` spelling."""

    if not isinstance(value, str):
        raise SchemaModelValidationError(f"{path} must be text")
    if "\x00" in value:
        raise SchemaModelValidationError(f"{path} must not contain NUL")
    normalized = re.sub(r"\s+", " ", value.strip().lower())
    normalized = re.sub(r"\s*\(\s*", "(", normalized)
    normalized = re.sub(r"\s*,\s*", ",", normalized)
    normalized = re.sub(r"\s*\)", ")", normalized)
    if not normalized:
        raise SchemaModelValidationError(f"{path} must not be empty")

    array_suffix = ""
    if normalized.endswith("[]"):
        array_suffix = "[]"
        normalized = normalized[:-2].rstrip()
    if normalized in _SERIAL_PSEUDO_TYPES:
        raise SchemaModelValidationError(
            f"{path} contains unsupported serial pseudo-type"
        )

    aliases = {"int": "integer", "bool": "boolean"}
    normalized = aliases.get(normalized, normalized)
    for alias, canonical in (
        ("varchar", "character varying"),
        ("char", "character"),
        ("decimal", "numeric"),
    ):
        match = re.fullmatch(rf"{alias}(\(\d+(?:,\d+)?\))?", normalized)
        if match:
            normalized = canonical + (match.group(1) or "")
            break
    if normalized == "character":
        normalized = "character(1)"
    for temporal in ("timestamp", "time"):
        if re.fullmatch(rf"{temporal}(?:\(\d+\))?", normalized):
            normalized += " without time zone"
            break

    canonical = normalized + array_suffix
    if _CANONICAL_DATA_TYPE_RE.fullmatch(canonical) is None:
        raise SchemaModelValidationError(f"{path} contains unsupported data type")
    return canonical


def _string_list(value: object, path: str) -> list[str]:
    return [_text(item, f"{path}[{index}]") for index, item in enumerate(_list(value, path))]


def _canonical_primary_key(
    value: object, columns: set[str], path: str
) -> dict[str, Any] | None:
    if value is None:
        return None
    primary_key = _object(value, path)
    _check_fields(primary_key, _PRIMARY_KEY_FIELDS, path)
    key_columns = _string_list(primary_key.get("columns"), f"{path}.columns")
    if not key_columns:
        raise SchemaModelValidationError(f"{path}.columns must not be empty")
    if len(set(key_columns)) != len(key_columns):
        raise SchemaModelValidationError(f"{path}.columns contains a duplicate column")
    unknown = [column for column in key_columns if column not in columns]
    if unknown:
        raise SchemaModelValidationError(
            f"{path}.columns references unknown column {unknown[0]!r}"
        )
    deferrable = _boolean(primary_key.get("deferrable"), f"{path}.deferrable")
    initially_deferred = _boolean(
        primary_key.get("initially_deferred"), f"{path}.initially_deferred"
    )
    if initially_deferred and not deferrable:
        raise SchemaModelValidationError(
            f"{path}.initially_deferred requires deferrable to be true"
        )
    return {
        "constraint_name": _text(
            primary_key.get("constraint_name"), f"{path}.constraint_name"
        ),
        "columns": key_columns,
        "deferrable": deferrable,
        "initially_deferred": initially_deferred,
    }


def _canonical_column(value: object, path: str) -> dict[str, Any]:
    column = _object(value, path)
    _check_fields(column, _COLUMN_FIELDS, path)
    ordinal = column.get("ordinal_position")
    if not isinstance(ordinal, int) or isinstance(ordinal, bool) or ordinal < 1:
        raise SchemaModelValidationError(f"{path}.ordinal_position must be a positive integer")
    data_type = _canonical_data_type(column.get("data_type"), f"{path}.data_type")
    for field, label in (
        ("default", "default expressions"),
        ("identity", "identity columns"),
        ("generated", "generated columns"),
    ):
        if column.get(field) is not None:
            raise SchemaModelValidationError(
                f"{path} contains unsupported feature {label}"
            )
    result: dict[str, Any] = {
        "column_name": _text(column.get("column_name"), f"{path}.column_name"),
        "data_type": data_type,
        "nullable": _boolean(column.get("nullable"), f"{path}.nullable"),
        "ordinal_position": ordinal,
        "comment": _optional_text(column.get("comment"), f"{path}.comment"),
    }
    return result


def _canonical_table(value: object, path: str) -> dict[str, Any]:
    table = _object(value, path)
    _check_fields(table, _TABLE_FIELDS, path, _VOLATILE_TABLE_FIELDS)
    unsupported = _string_list(
        table.get("unsupported_features", []), f"{path}.unsupported_features"
    )
    if unsupported:
        raise SchemaModelValidationError(
            f"{path} contains unsupported feature {unsupported[0]!r}"
        )
    columns = [
        _canonical_column(column, f"{path}.columns[{index}]")
        for index, column in enumerate(_list(table.get("columns"), f"{path}.columns"))
    ]
    columns.sort(key=lambda column: (column["ordinal_position"], column["column_name"]))
    column_names = [str(column["column_name"]) for column in columns]
    if len(set(column_names)) != len(column_names):
        raise SchemaModelValidationError(f"{path} contains a duplicate column")
    ordinals = [int(column["ordinal_position"]) for column in columns]
    if len(set(ordinals)) != len(ordinals):
        raise SchemaModelValidationError(f"{path} contains a duplicate column ordinal")

    # These collections are retained in the v1 wire contract but must remain
    # empty until their lossless validators and structured compilers land.
    for field in ("unique_constraints", "foreign_keys", "indexes"):
        entries = _list(table.get(field, []), f"{path}.{field}")
        if entries:
            raise SchemaModelValidationError(
                f"{path}.{field} contains unsupported feature {field!r}"
            )

    primary_key = _canonical_primary_key(
        table.get("primary_key"), set(column_names), f"{path}.primary_key"
    )
    if primary_key is not None:
        nullable_columns = {
            str(column["column_name"])
            for column in columns
            if bool(column["nullable"])
        }
        nullable_key_columns = [
            column
            for column in primary_key["columns"]
            if column in nullable_columns
        ]
        if nullable_key_columns:
            raise SchemaModelValidationError(
                f"{path}.primary_key column {nullable_key_columns[0]!r} "
                "must be explicitly not nullable"
            )

    result: dict[str, Any] = {
        "table_name": _text(table.get("table_name"), f"{path}.table_name"),
        "comment": _optional_text(table.get("comment"), f"{path}.comment"),
        "columns": columns,
        "primary_key": primary_key,
        "unique_constraints": [],
        "foreign_keys": [],
        "indexes": [],
        "unsupported_features": [],
    }
    return result


def canonicalize_schema_model(model: Mapping[str, Any]) -> dict[str, Any]:
    """Return deterministic, validated JSON for a v1 editable schema model.

    Volatile reverse-engineering metadata is discarded.  All compiler-relevant
    fields are preserved and normalized in a deterministic order.  Unsupported
    or unrecognized content raises :class:`SchemaModelValidationError` instead
    of being silently omitted.
    """

    root = _object(model, "model")
    _check_fields(root, _MODEL_FIELDS, "model", _VOLATILE_MODEL_FIELDS)
    if root.get("format_version") != 1:
        raise SchemaModelValidationError("model.format_version must be 1")
    postgresql_major = root.get("postgresql_major")
    if (
        not isinstance(postgresql_major, int)
        or isinstance(postgresql_major, bool)
        or postgresql_major < 14
        or postgresql_major > 18
    ):
        raise SchemaModelValidationError(
            "model.postgresql_major must be a supported version from 14 through 18"
        )

    schemas: list[dict[str, Any]] = []
    schema_names: set[str] = set()
    for schema_index, raw_schema in enumerate(_list(root.get("schemas"), "model.schemas")):
        path = f"model.schemas[{schema_index}]"
        schema = _object(raw_schema, path)
        _check_fields(schema, _SCHEMA_FIELDS, path)
        schema_name = _text(schema.get("schema_name"), f"{path}.schema_name")
        if schema_name in schema_names:
            raise SchemaModelValidationError(f"model contains duplicate schema {schema_name!r}")
        schema_names.add(schema_name)
        tables = [
            _canonical_table(table, f"{path}.tables[{table_index}]")
            for table_index, table in enumerate(
                _list(schema.get("tables"), f"{path}.tables")
            )
        ]
        table_names = [str(table["table_name"]) for table in tables]
        if len(set(table_names)) != len(table_names):
            raise SchemaModelValidationError(
                f"{path} contains a duplicate table"
            )
        tables.sort(key=lambda table: table["table_name"])
        schemas.append({"schema_name": schema_name, "tables": tables})
    schemas.sort(key=lambda schema: schema["schema_name"])
    return {
        "format_version": 1,
        "postgresql_major": postgresql_major,
        "schemas": schemas,
    }


def schema_model_digest(model: Mapping[str, Any]) -> str:
    """Return a lowercase SHA-256 hex digest of canonical model JSON."""

    canonical = canonicalize_schema_model(model)
    encoded = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
