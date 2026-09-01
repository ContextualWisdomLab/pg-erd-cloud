"""Deterministic, anonymized workload generators for capacity profiling.

Issue #951 requires a reproducible workload model *before* any SLO number is
claimed. This module produces schema snapshots in the common introspection
JSON shape (the same shape :mod:`app.pg_introspect.introspect` emits), at three
named sizes plus a set of skew cases.

Guarantees:

* **Deterministic** -- every generator takes a ``seed`` (a per-profile default
  is used when omitted) and returns byte-for-byte identical output for the
  same seed.
* **Anonymized** -- identifiers are built from a fixed synthetic vocabulary;
  no real customer, person, or organization names, and no production data
  values (no ``example_value`` hints are populated).
* **Shape-accurate** -- the named profiles hit the exact schema / relation /
  column / foreign-key / index counts from the issue's table.
* **No thresholds** -- this module contains generators only. Latency,
  throughput, and memory targets are set from measured baseline runs
  elsewhere, never invented here.

DB object names follow the project rule: two-or-more-word ``snake_case``.
"""

from __future__ import annotations

import datetime as dt
import random
from dataclasses import dataclass
from typing import Any

#: Synthetic, meaning-free noun stems combined pairwise into object names.
_NOUN_STEMS = (
    "order",
    "invoice",
    "account",
    "ledger",
    "shipment",
    "product",
    "catalog",
    "contact",
    "region",
    "channel",
    "tariff",
    "batch",
    "reading",
    "sensor",
    "asset",
    "policy",
    "claim",
    "route",
    "segment",
    "session",
)

#: Synthetic column-attribute stems (paired with a type-hint word).
_ATTR_STEMS = (
    "total",
    "net",
    "gross",
    "unit",
    "line",
    "effective",
    "recorded",
    "source",
    "target",
    "primary",
    "secondary",
    "external",
    "internal",
    "display",
    "sort",
    "status",
    "kind",
    "scope",
    "weight",
    "score",
)

#: (data_type, name-suffix) pairs used to give columns a realistic spread.
_COLUMN_TYPES = (
    ("bigint", "id"),
    ("text", "code"),
    ("text", "label"),
    ("numeric(18,4)", "amount"),
    ("integer", "count"),
    ("boolean", "flag"),
    ("timestamp with time zone", "at"),
    ("date", "on"),
    ("jsonb", "payload"),
    ("uuid", "reference"),
)


@dataclass(frozen=True)
class ProfileSpec:
    """Target object counts for one named workload profile.

    Attributes:
        name: Profile name (``small`` / ``medium`` / ``large``).
        schemas: Number of distinct schemas.
        relations: Number of tables/views.
        columns: Total number of columns across all relations.
        fk_edges: Number of foreign-key edges.
        indexes: Number of secondary indexes (excludes primary-key indexes).
        snapshots_per_project: Snapshots retained per project (context only;
            not part of the generated snapshot itself).
        default_seed: Seed used when a caller passes ``seed=None``.
    """

    name: str
    schemas: int
    relations: int
    columns: int
    fk_edges: int
    indexes: int
    snapshots_per_project: int
    default_seed: int


#: The three named profiles, matching the table in issue #951 exactly.
PROFILE_SPECS: dict[str, ProfileSpec] = {
    "small": ProfileSpec("small", 5, 100, 2_000, 200, 300, 20, 95_101),
    "medium": ProfileSpec("medium", 25, 1_000, 25_000, 3_000, 5_000, 100, 95_102),
    "large": ProfileSpec("large", 100, 10_000, 250_000, 30_000, 50_000, 500, 95_103),
}


def list_profiles() -> list[str]:
    """Return the named profile keys in ascending size order."""

    return ["small", "medium", "large"]


def _rng(seed: int) -> random.Random:
    """Return a fresh, isolated PRNG for one generation run."""

    return random.Random(seed)


def _object_name(rng: random.Random, index: int) -> str:
    """Build a deterministic two-word ``snake_case`` object name."""

    a = _NOUN_STEMS[rng.randrange(len(_NOUN_STEMS))]
    b = _NOUN_STEMS[rng.randrange(len(_NOUN_STEMS))]
    return f"{a}_{b}_{index:05d}"


def _column_name(rng: random.Random, position: int, suffix: str) -> str:
    """Build a deterministic two-word ``snake_case`` column name."""

    stem = _ATTR_STEMS[rng.randrange(len(_ATTR_STEMS))]
    return f"{stem}_{suffix}_{position:04d}"


def _empty_snapshot(schema_names: list[str]) -> dict[str, Any]:
    """Return a snapshot skeleton with fixed metadata and the schema list."""

    return {
        "captured_at": dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc).isoformat(),
        "server_version": "17.0 (synthetic workload profile)",
        "schema_filter": None,
        "schemas": [{"schema_name": name} for name in schema_names],
        "relations": [],
        "columns": [],
        "constraints": [],
        "indexes": [],
        "pk_columns": [],
        "fk_edges": [],
        "citus_distributed_tables": [],
    }


def _distribute(total: int, buckets: int) -> list[int]:
    """Split ``total`` across ``buckets`` as evenly as possible (sum preserved)."""

    if buckets <= 0:
        return []
    base, extra = divmod(total, buckets)
    return [base + (1 if i < extra else 0) for i in range(buckets)]


def _build_relations(
    spec_relations: int,
    spec_columns: int,
    schema_names: list[str],
    rng: random.Random,
    snapshot: dict[str, Any],
) -> None:
    """Populate relations, columns, primary keys, and PK indexes in place."""

    per_relation = _distribute(max(spec_columns, spec_relations), spec_relations)
    for oid in range(1, spec_relations + 1):
        schema_name = schema_names[(oid - 1) % len(schema_names)]
        relation_name = _object_name(rng, oid)
        snapshot["relations"].append(
            {
                "relation_oid": oid,
                "schema_name": schema_name,
                "relation_name": relation_name,
                "relation_kind": "r",
                "relation_comment": None,
                "is_partition": False,
                "partition_key": None,
            }
        )
        column_count = max(1, per_relation[oid - 1])
        # Column 1 is always the surrogate primary key.
        snapshot["columns"].append(
            {
                "relation_oid": oid,
                "column_position": 1,
                "column_name": f"{relation_name}_id",
                "data_type": "bigint",
                "is_not_null": True,
                "has_default": True,
                "default_expr": f"nextval('{relation_name}_id_seq'::regclass)",
                "type_category": "N",
                "array_dimensions": 0,
            }
        )
        for position in range(2, column_count + 1):
            data_type, suffix = _COLUMN_TYPES[
                rng.randrange(len(_COLUMN_TYPES))
            ]
            snapshot["columns"].append(
                {
                    "relation_oid": oid,
                    "column_position": position,
                    "column_name": _column_name(rng, position, suffix),
                    "data_type": data_type,
                    "is_not_null": rng.random() < 0.4,
                    "has_default": False,
                    "default_expr": None,
                    "type_category": "A" if data_type.endswith("[]") else "S",
                    "array_dimensions": 0,
                }
            )
        snapshot["pk_columns"].append(
            {
                "relation_oid": oid,
                "column_name": f"{relation_name}_id",
                "column_ordinal": 1,
            }
        )
        snapshot["constraints"].append(
            {
                "relation_oid": oid,
                "constraint_type": "p",
                "constraint_name": f"{relation_name}_pkey",
                "constrained_attnums": [1],
                "constraint_def": f"PRIMARY KEY ({relation_name}_id)",
            }
        )


def _trim_columns_to_target(snapshot: dict[str, Any], target: int) -> None:
    """Drop trailing non-key columns so the total column count equals ``target``."""

    columns = snapshot["columns"]
    if len(columns) <= target:
        return
    keep: list[dict[str, Any]] = []
    surplus = len(columns) - target
    for column in reversed(columns):
        if surplus > 0 and column["column_position"] != 1:
            surplus -= 1
            continue
        keep.append(column)
    keep.reverse()
    snapshot["columns"] = keep


def _add_foreign_keys(
    fk_edges: int, relation_count: int, rng: random.Random, snapshot: dict[str, Any]
) -> None:
    """Add ``fk_edges`` unique child->parent edges (no self references)."""

    if relation_count < 2:
        return
    seen: set[tuple[int, int]] = set()
    attempts = 0
    max_attempts = fk_edges * 20 + 50
    while len(seen) < fk_edges and attempts < max_attempts:
        attempts += 1
        child = rng.randint(1, relation_count)
        parent = rng.randint(1, relation_count)
        if child == parent or (child, parent) in seen:
            continue
        seen.add((child, parent))
        child_name = snapshot["relations"][child - 1]["relation_name"]
        parent_name = snapshot["relations"][parent - 1]["relation_name"]
        column_name = f"{parent_name}_id"
        snapshot["columns"].append(
            {
                "relation_oid": child,
                "column_position": 1_000_000 + len(seen),
                "column_name": column_name,
                "data_type": "bigint",
                "is_not_null": True,
                "has_default": False,
                "default_expr": None,
                "type_category": "N",
                "array_dimensions": 0,
            }
        )
        snapshot["fk_edges"].append(
            {
                "child_relation_oid": child,
                "parent_relation_oid": parent,
                "child_column_name": column_name,
                "parent_column_name": f"{parent_name}_id",
            }
        )


def _add_indexes(
    index_count: int, relation_count: int, rng: random.Random, snapshot: dict[str, Any]
) -> None:
    """Add ``index_count`` secondary (non-PK) index records."""

    columns_by_oid: dict[int, list[str]] = {}
    for column in snapshot["columns"]:
        columns_by_oid.setdefault(column["relation_oid"], []).append(
            column["column_name"]
        )
    for i in range(1, index_count + 1):
        oid = rng.randint(1, relation_count)
        candidates = columns_by_oid.get(oid) or [f"col_{i}"]
        picked = candidates[rng.randrange(len(candidates))]
        relation_name = snapshot["relations"][oid - 1]["relation_name"]
        snapshot["indexes"].append(
            {
                "relation_oid": oid,
                "index_name": f"{relation_name}_secondary_{i:05d}_idx",
                "is_unique": rng.random() < 0.15,
                "is_primary": False,
                "is_valid": True,
                "access_method": "btree",
                "predicate_expr": None,
                "index_def": (
                    f"CREATE INDEX {relation_name}_secondary_{i:05d}_idx "
                    f"ON {relation_name} USING btree ({picked})"
                ),
            }
        )


def generate_workload_snapshot(
    profile: str, *, seed: int | None = None
) -> dict[str, Any]:
    """Generate a deterministic anonymized schema snapshot for a named profile.

    Args:
        profile: One of :func:`list_profiles` (``small`` / ``medium`` /
            ``large``).
        seed: PRNG seed. ``None`` uses the profile's ``default_seed`` so the
            call is still fully deterministic.

    Returns:
        A schema snapshot in the common introspection JSON shape. The number
        of ``schemas``, ``relations``, ``columns``, ``fk_edges``, and
        ``indexes`` matches the profile spec exactly.

    Raises:
        KeyError: If ``profile`` is not a known profile name.
    """

    spec = PROFILE_SPECS[profile]
    rng = _rng(spec.default_seed if seed is None else seed)
    schema_names = [f"tenant_schema_{i:04d}" for i in range(1, spec.schemas + 1)]
    snapshot = _empty_snapshot(schema_names)
    _build_relations(spec.relations, spec.columns, schema_names, rng, snapshot)
    # Reserve one column slot per foreign key so the final column total (base
    # columns + FK columns) lands exactly on the profile target.
    _trim_columns_to_target(snapshot, spec.columns - spec.fk_edges)
    _add_foreign_keys(spec.fk_edges, spec.relations, rng, snapshot)
    _add_indexes(spec.indexes, spec.relations, rng, snapshot)
    snapshot["workload_profile"] = {
        "name": spec.name,
        "seed": spec.default_seed if seed is None else seed,
        "snapshots_per_project": spec.snapshots_per_project,
    }
    return snapshot


def wide_relation_snapshot(
    *, column_count: int = 5_000, seed: int = 95_201
) -> dict[str, Any]:
    """One relation with ``column_count`` columns (default 5,000)."""

    rng = _rng(seed)
    snapshot = _empty_snapshot(["tenant_schema_0001"])
    _build_relations(1, column_count, ["tenant_schema_0001"], rng, snapshot)
    _trim_columns_to_target(snapshot, column_count)
    snapshot["workload_profile"] = {"name": "wide_relation", "seed": seed}
    return snapshot


def dense_fk_cluster_snapshot(
    *, relation_count: int = 40, seed: int = 95_202
) -> dict[str, Any]:
    """A near-complete foreign-key graph among ``relation_count`` relations."""

    rng = _rng(seed)
    schema_names = ["tenant_schema_0001"]
    snapshot = _empty_snapshot(schema_names)
    _build_relations(relation_count, relation_count * 4, schema_names, rng, snapshot)
    edge_target = relation_count * (relation_count - 1)
    _add_foreign_keys(edge_target, relation_count, rng, snapshot)
    snapshot["workload_profile"] = {"name": "dense_fk_cluster", "seed": seed}
    return snapshot


def deep_dependency_chain_snapshot(
    *, depth: int = 200, seed: int = 95_203
) -> dict[str, Any]:
    """A linear FK chain ``r1 <- r2 <- ... <- r{depth}``."""

    rng = _rng(seed)
    schema_names = ["tenant_schema_0001"]
    snapshot = _empty_snapshot(schema_names)
    _build_relations(depth, depth * 3, schema_names, rng, snapshot)
    for child in range(2, depth + 1):
        parent = child - 1
        parent_name = snapshot["relations"][parent - 1]["relation_name"]
        column_name = f"{parent_name}_id"
        snapshot["columns"].append(
            {
                "relation_oid": child,
                "column_position": 2_000_000 + child,
                "column_name": column_name,
                "data_type": "bigint",
                "is_not_null": True,
                "has_default": False,
                "default_expr": None,
                "type_category": "N",
                "array_dimensions": 0,
            }
        )
        snapshot["fk_edges"].append(
            {
                "child_relation_oid": child,
                "parent_relation_oid": parent,
                "child_column_name": column_name,
                "parent_column_name": f"{parent_name}_id",
            }
        )
    snapshot["workload_profile"] = {"name": "deep_dependency_chain", "seed": seed}
    return snapshot


def disconnected_components_snapshot(
    *, component_count: int = 12, per_component: int = 8, seed: int = 95_204
) -> dict[str, Any]:
    """``component_count`` independent FK-connected clusters that never link."""

    rng = _rng(seed)
    schema_names = ["tenant_schema_0001"]
    total = component_count * per_component
    snapshot = _empty_snapshot(schema_names)
    _build_relations(total, total * 3, schema_names, rng, snapshot)
    for component in range(component_count):
        base = component * per_component + 1
        for offset in range(1, per_component):
            child = base + offset
            parent = base
            parent_name = snapshot["relations"][parent - 1]["relation_name"]
            column_name = f"{parent_name}_id"
            snapshot["columns"].append(
                {
                    "relation_oid": child,
                    "column_position": 3_000_000 + child,
                    "column_name": column_name,
                    "data_type": "bigint",
                    "is_not_null": True,
                    "has_default": False,
                    "default_expr": None,
                    "type_category": "N",
                    "array_dimensions": 0,
                }
            )
            snapshot["fk_edges"].append(
                {
                    "child_relation_oid": child,
                    "parent_relation_oid": parent,
                    "child_column_name": column_name,
                    "parent_column_name": f"{parent_name}_id",
                }
            )
    snapshot["workload_profile"] = {
        "name": "disconnected_components",
        "seed": seed,
    }
    return snapshot


def multilingual_identifier_snapshot(*, seed: int = 95_205) -> dict[str, Any]:
    """Relations with long quoted / multilingual names and large comments.

    Identifiers here intentionally include non-ASCII text and spaces (they are
    quoted identifiers in PostgreSQL) so downstream code is exercised against
    Unicode and quoting, not just ``snake_case`` ASCII.
    """

    rng = _rng(seed)
    schema_names = ["보고서_스키마_0001", "schema_with_a_deliberately_long_name_0002"]
    snapshot = _empty_snapshot(schema_names)
    names = [
        "월별 매출 집계 테이블",
        "quoted identifier with spaces and a very long descriptive tail segment",
        "таблица_учёта_операций",
        "テーブル_売上_明細",
    ]
    for oid, relation_name in enumerate(names, start=1):
        schema_name = schema_names[(oid - 1) % len(schema_names)]
        snapshot["relations"].append(
            {
                "relation_oid": oid,
                "schema_name": schema_name,
                "relation_name": relation_name,
                "relation_kind": "r",
                "relation_comment": "설명 " * 400,
                "is_partition": False,
                "partition_key": None,
            }
        )
        for position in range(1, 6):
            data_type, suffix = _COLUMN_TYPES[rng.randrange(len(_COLUMN_TYPES))]
            snapshot["columns"].append(
                {
                    "relation_oid": oid,
                    "column_position": position,
                    "column_name": f"컬럼_{suffix}_{position:02d}",
                    "data_type": data_type,
                    "is_not_null": position == 1,
                    "has_default": False,
                    "default_expr": None,
                    "type_category": "S",
                    "array_dimensions": 0,
                    "column_comment": "コメント " * 300,
                }
            )
    snapshot["workload_profile"] = {"name": "multilingual_identifier", "seed": seed}
    return snapshot


def partition_hierarchy_snapshot(
    *, child_count: int = 64, seed: int = 95_206
) -> dict[str, Any]:
    """A RANGE-partitioned parent relation with ``child_count`` partitions."""

    rng = _rng(seed)
    schema_names = ["tenant_schema_0001"]
    snapshot = _empty_snapshot(schema_names)
    parent_name = "measurement_reading_00001"
    snapshot["relations"].append(
        {
            "relation_oid": 1,
            "schema_name": schema_names[0],
            "relation_name": parent_name,
            "relation_kind": "p",
            "relation_comment": None,
            "is_partition": False,
            "partition_key": "RANGE (recorded_at)",
        }
    )
    for name, data_type in (
        (f"{parent_name}_id", "bigint"),
        ("recorded_at", "timestamp with time zone"),
        ("reading_value", "numeric(18,4)"),
    ):
        snapshot["columns"].append(
            {
                "relation_oid": 1,
                "column_position": len(snapshot["columns"]) + 1,
                "column_name": name,
                "data_type": data_type,
                "is_not_null": True,
                "has_default": name.endswith("_id"),
                "default_expr": None,
                "type_category": "N",
                "array_dimensions": 0,
            }
        )
    snapshot["pk_columns"].extend(
        [
            {"relation_oid": 1, "column_name": f"{parent_name}_id", "column_ordinal": 1},
            {"relation_oid": 1, "column_name": "recorded_at", "column_ordinal": 2},
        ]
    )
    for i in range(1, child_count + 1):
        oid = 1 + i
        snapshot["relations"].append(
            {
                "relation_oid": oid,
                "schema_name": schema_names[0],
                "relation_name": f"{parent_name}_p{i:05d}",
                "relation_kind": "r",
                "relation_comment": None,
                "is_partition": True,
                "partition_key": None,
                "partition_parent_oid": 1,
                "partition_bound": f"FOR VALUES FROM ('2026-{i:02d}-01') TO ('2026-{i:02d}-28')",
            }
        )
    rng.random()  # keep the seed consumed consistently with the other builders
    snapshot["workload_profile"] = {"name": "partition_hierarchy", "seed": seed}
    return snapshot
