"""Executable checks for deterministic benchmark workload generation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pytest

from capacity_profile import PROFILES, VARIANTS, generate_snapshot
from run_capacity_benchmark import _percentile, run


def test_profiles_have_issue_951_counts() -> None:
    assert PROFILES["small"].tables == 100
    assert PROFILES["medium"].columns == 25_000
    assert PROFILES["large"].foreign_keys == 30_000


def test_generation_is_deterministic_and_value_free() -> None:
    first = generate_snapshot("small", seed=7)
    second = generate_snapshot("small", seed=7)

    assert first == second
    assert "password" not in json.dumps(first).lower()
    assert len(first["relations"]) == 100
    assert len(first["columns"]) == 2_000
    assert len(first["constraints"]) == 200
    assert len(first["indexes"]) == 300


@pytest.mark.parametrize("variant", sorted(VARIANTS))
def test_variants_keep_cardinality_and_two_word_names(variant: str) -> None:
    snapshot = generate_snapshot("small", seed=11, variant=variant)

    assert len(snapshot["relations"]) == 100
    assert len(snapshot["columns"]) == 2_000
    assert all("_" in row["relation_name"] for row in snapshot["relations"])
    assert all("_" in row["column_name"] for row in snapshot["columns"])


def test_invalid_profile_and_variant_fail_closed() -> None:
    with pytest.raises(ValueError, match="unknown capacity profile"):
        generate_snapshot("unknown")
    with pytest.raises(ValueError, match="unknown capacity variant"):
        generate_snapshot("small", variant="unknown")


def test_percentile_uses_nearest_rank_for_the_median() -> None:
    assert _percentile([30.0, 10.0, 20.0], 50) == 20.0
    assert _percentile([30.0, 10.0, 20.0], 95) == 30.0


def test_benchmark_measures_the_reported_snowflake_path(monkeypatch: pytest.MonkeyPatch) -> None:
    dialects: list[str] = []

    def fake_export(snapshot: dict, target_dialect: str = "postgresql") -> str:
        del snapshot
        dialects.append(target_dialect)
        return ""

    monkeypatch.setattr("run_capacity_benchmark.snapshot_json_to_sql", fake_export)
    result = run("small", "baseline", seed=0, repetitions=1)

    assert dialects == ["snowflake"]
    assert "snowflake_ddl_export" in result["measurements"]
