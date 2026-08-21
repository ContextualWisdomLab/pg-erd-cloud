"""Generate deterministic, value-free schema workloads for capacity tests.

The generated names are synthetic and must never be loaded into production.
Profiles mirror the first capacity contract in issue #951 so benchmark results
can be compared across commits and machines without customer data.
"""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CapacityProfile:
    """Describe one deterministic schema-size workload."""

    schemas: int
    tables: int
    columns: int
    foreign_keys: int
    indexes: int
    snapshots_per_project: int


PROFILES: dict[str, CapacityProfile] = {
    "small": CapacityProfile(5, 100, 2_000, 200, 300, 20),
    "medium": CapacityProfile(25, 1_000, 25_000, 3_000, 5_000, 100),
    "large": CapacityProfile(100, 10_000, 250_000, 30_000, 50_000, 500),
}
VARIANTS = {"baseline", "dense_fk", "deep_chain", "disconnected", "long_names"}


def _distributed_counts(total: int, buckets: int) -> list[int]:
    """Distribute *total* items over *buckets* without losing remainder."""

    base, remainder = divmod(total, buckets)
    return [base + int(index < remainder) for index in range(buckets)]


def _schema_name(index: int, variant: str) -> str:
    """Return a stable, synthetic two-word schema name."""

    suffix = "_다국어" if variant == "long_names" else "_domain"
    return f"schema_{index:03d}{suffix}"


def _table_name(index: int, variant: str) -> str:
    """Return a stable, synthetic two-word table name."""

    suffix = "_顧客データ" if variant == "long_names" else "_entity"
    return f"table_{index:05d}{suffix}"


def _column_name(table_index: int, column_index: int, variant: str) -> str:
    """Return a stable, synthetic two-word column name."""

    suffix = "_значение" if variant == "long_names" else "_value"
    return f"column_{table_index:05d}_{column_index:03d}{suffix}"


def _edge_target(edge_index: int, tables: int, variant: str, rng: random.Random) -> int:
    """Choose a deterministic parent table for a foreign-key edge."""

    child = 1 + edge_index % tables
    if variant == "dense_fk":
        parent = 1 + edge_index % min(tables, 100)
    elif variant == "deep_chain":
        parent = max(1, child - 1)
    elif variant == "disconnected":
        component_size = max(1, tables // 10)
        start = ((child - 1) // component_size) * component_size + 1
        parent = start + rng.randrange(min(component_size, tables - start + 1))
    else:
        parent = 1 + rng.randrange(tables)
    return parent if parent != child else (parent % tables) + 1


def generate_snapshot(
    profile_name: str, *, seed: int = 0, variant: str = "baseline"
) -> dict[str, Any]:
    """Build one deterministic synthetic snapshot for a named profile.

    The result follows the backend snapshot shape closely enough for export and
    serialization benchmarks. It contains no customer values or credentials.
    """

    if profile_name not in PROFILES:
        raise ValueError(f"unknown capacity profile: {profile_name}")
    if variant not in VARIANTS:
        raise ValueError(f"unknown capacity variant: {variant}")

    profile = PROFILES[profile_name]
    rng = random.Random(seed)
    columns_per_table = _distributed_counts(profile.columns, profile.tables)
    schema_for_table = [index % profile.schemas for index in range(profile.tables)]
    schema_names = [_schema_name(index, variant) for index in range(profile.schemas)]
    table_names = [_table_name(index, variant) for index in range(profile.tables)]

    relations: list[dict[str, Any]] = []
    columns: list[dict[str, Any]] = []
    for table_index, column_count in enumerate(columns_per_table):
        oid = table_index + 1
        relations.append(
            {
                "schema_name": schema_names[schema_for_table[table_index]],
                "relation_name": table_names[table_index],
                "relation_oid": oid,
                "relation_kind": "r",
            }
        )
        for column_index in range(column_count):
            columns.append(
                {
                    "relation_oid": oid,
                    "column_position": column_index + 1,
                    "column_name": _column_name(table_index, column_index, variant),
                    "data_type": "integer" if column_index == 0 else "text",
                    "is_not_null": column_index == 0,
                }
            )

    constraints: list[dict[str, Any]] = []
    for edge_index in range(profile.foreign_keys):
        child = 1 + edge_index % profile.tables
        parent = _edge_target(edge_index, profile.tables, variant, rng)
        child_schema = schema_names[schema_for_table[child - 1]]
        child_table = table_names[child - 1]
        parent_schema = schema_names[schema_for_table[parent - 1]]
        parent_table = table_names[parent - 1]
        child_column = _column_name(child - 1, 0, variant)
        constraints.append(
            {
                "relation_oid": child,
                "schema_name": child_schema,
                "relation_name": child_table,
                "constraint_name": f"constraint_{edge_index:06d}_foreign_key",
                "constraint_type": "f",
                "constraint_def": (
                    f'FOREIGN KEY ("{child_column}") REFERENCES '
                    f'"{parent_schema}"."{parent_table}" '
                    f'("{_column_name(parent - 1, 0, variant)}")'
                ),
            }
        )

    indexes = [
        {
            "index_name": f"index_{index:06d}_btree",
            "table_schema_name": schema_names[schema_for_table[index % profile.tables]],
            "table_name": table_names[index % profile.tables],
            "index_def": "",
        }
        for index in range(profile.indexes)
    ]
    return {
        "source_dialect": "postgresql",
        "profile": profile_name,
        "variant": variant,
        "seed": seed,
        "profile_counts": asdict(profile),
        "relations": relations,
        "columns": columns,
        "constraints": constraints,
        "indexes": indexes,
    }


def main() -> None:
    """Write one deterministic profile as JSON to stdout or a file."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=sorted(PROFILES), default="small")
    parser.add_argument("--variant", choices=sorted(VARIANTS), default="baseline")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = json.dumps(
        generate_snapshot(args.profile, seed=args.seed, variant=args.variant),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    if args.output:
        args.output.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)


if __name__ == "__main__":
    main()
