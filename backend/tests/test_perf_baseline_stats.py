"""Tests for :mod:`app.perf.baseline_stats`.

The aggregator must run the baseline the requested number of times, reduce
each path to an ordered distribution summary, stay correct at the
degenerate ``repeat=1`` boundary, reject ``repeat < 1``, and carry no
invented performance threshold.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import pytest

from app.perf import baseline_stats
from app.perf.baseline_stats import SUMMARY_FIELDS, aggregate_baseline, main

_EXPECTED_PATHS = {
    "canonical_hash",
    "json_round_trip",
    "schema_self_diff",
    "ddl_export_postgresql",
    "ddl_export_snowflake",
    "data_dictionary_markdown",
}


def test_aggregate_reports_every_path_with_a_full_summary() -> None:
    report = aggregate_baseline("small", repeat=3)
    assert set(report["paths"]) == _EXPECTED_PATHS
    assert report["repeat"] == 3
    for row in report["paths"].values():
        assert set(row) == {"wall_seconds", "peak_bytes", "result_size_bytes"}
        for metric in ("wall_seconds", "peak_bytes"):
            summary = row[metric]
            assert set(summary) == set(SUMMARY_FIELDS)
            assert len(summary["samples"]) == 3
            assert summary["min"] <= summary["p50"] <= summary["p95"] <= summary["p99"]
            assert summary["p99"] <= summary["max"]
        assert row["result_size_bytes"] > 0


def test_metadata_carries_profile_repeat_seed_and_generated_at() -> None:
    report = aggregate_baseline("small", repeat=2, seed=99)
    assert report["profile"] == "small"
    assert report["repeat"] == 2
    assert report["seed"] == 99
    assert report["relation_count"] == 100
    assert report["column_count"] == 2_000
    assert datetime.fromisoformat(report["generated_at"]).tzinfo is not None


def test_repeat_one_is_degenerate_but_well_formed() -> None:
    report = aggregate_baseline("small", repeat=1)
    for row in report["paths"].values():
        summary = row["wall_seconds"]
        assert len(summary["samples"]) == 1
        assert (
            summary["min"]
            == summary["p50"]
            == summary["p95"]
            == summary["p99"]
            == summary["max"]
            == summary["mean"]
        )


def test_repeat_below_one_raises_value_error() -> None:
    with pytest.raises(ValueError):
        aggregate_baseline("small", repeat=0)


def test_unknown_profile_raises_key_error() -> None:
    with pytest.raises(KeyError):
        aggregate_baseline("enterprise", repeat=2)


def test_result_size_is_stable_across_runs_of_a_fixed_seed() -> None:
    a = aggregate_baseline("small", repeat=2, seed=5)
    b = aggregate_baseline("small", repeat=2, seed=5)
    sizes_a = {n: r["result_size_bytes"] for n, r in a["paths"].items()}
    sizes_b = {n: r["result_size_bytes"] for n, r in b["paths"].items()}
    assert sizes_a == sizes_b


def test_cli_json_emits_a_parseable_report(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--profile", "small", "--repeat", "2", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert set(report["paths"]) == _EXPECTED_PATHS
    assert report["repeat"] == 2


def test_cli_table_output_is_human_readable(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--profile", "small", "--repeat", "2"]) == 0
    out = capsys.readouterr().out
    assert "profile=small" in out
    assert "wall_p95_ms" in out


def test_module_states_targets_are_measured_and_invents_no_threshold() -> None:
    raw = Path("app/perf/baseline_stats.py").read_text(encoding="utf-8").lower()
    prose = re.sub(r"\s+", " ", raw)
    assert "set from measured baseline runs and never invented" in prose
    assert "makes no pass/fail judgement" in prose
    assert "no latency, throughput, or memory threshold" in prose
    assert re.search(r"\b\d+(\.\d+)?\s*(ms|milliseconds|seconds)\b", raw) is None
    assert re.search(r"p9[59]\s*[<>=:]", raw) is None
    assert re.search(r"\b\d+\s*(rps|qps|req/s)\b", raw) is None
