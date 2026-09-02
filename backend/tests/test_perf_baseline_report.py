"""Tests for :mod:`app.perf.baseline_report`.

The envelope must wrap the raw statistics additively, fingerprint the exact
workload it measured, pick a real slowest path, stay deterministic under a
fixed seed, and carry no invented performance threshold.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pytest

from app.perf.baseline_report import REPORT_VERSION, build_baseline_report

_EXPECTED_PATHS = {
    "canonical_hash",
    "json_round_trip",
    "schema_self_diff",
    "ddl_export_postgresql",
    "ddl_export_snowflake",
    "data_dictionary_markdown",
}


def test_report_has_the_full_envelope_and_preserves_statistics() -> None:
    report = build_baseline_report("small", repeat=2)
    assert report["report_version"] == REPORT_VERSION
    assert set(report) == {
        "report_version",
        "generated_at",
        "schema_fingerprint",
        "summary",
        "statistics",
    }
    assert set(report["statistics"]["paths"]) == _EXPECTED_PATHS
    assert report["statistics"]["repeat"] == 2


def test_schema_fingerprint_is_sha256_prefixed_and_seed_stable() -> None:
    a = build_baseline_report("small", repeat=1, seed=11)
    b = build_baseline_report("small", repeat=1, seed=11)
    assert a["schema_fingerprint"].startswith("sha256:")
    assert a["schema_fingerprint"] == b["schema_fingerprint"]


def test_different_seeds_fingerprint_differently() -> None:
    a = build_baseline_report("small", repeat=1, seed=1)
    b = build_baseline_report("small", repeat=1, seed=2)
    assert a["schema_fingerprint"] != b["schema_fingerprint"]


def test_summary_names_a_real_slowest_path() -> None:
    report = build_baseline_report("small", repeat=2)
    summary = report["summary"]
    assert summary["path_count"] == 6
    assert summary["slowest_path_by_wall_p95"] in _EXPECTED_PATHS
    assert "small" in summary["headline"]


def test_generated_at_is_timezone_aware() -> None:
    report = build_baseline_report("small", repeat=1)
    assert datetime.fromisoformat(report["generated_at"]).tzinfo is not None


def test_repeat_below_one_propagates_value_error() -> None:
    with pytest.raises(ValueError):
        build_baseline_report("small", repeat=0)


def test_unknown_profile_raises_key_error() -> None:
    with pytest.raises(KeyError):
        build_baseline_report("enterprise", repeat=1)


def test_module_states_targets_are_measured_and_invents_no_threshold() -> None:
    raw = Path("app/perf/baseline_report.py").read_text(encoding="utf-8").lower()
    prose = re.sub(r"\s+", " ", raw)
    assert "measured baseline runs and never invented" in prose
    assert "no latency, throughput, or memory threshold" in prose
    assert "makes no pass/fail judgement" in prose
    assert re.search(r"\b\d+(\.\d+)?\s*(ms|milliseconds|seconds)\b", raw) is None
    assert re.search(r"p9[59]\s*[<>=:]", raw) is None
    assert re.search(r"\b\d+\s*(rps|qps|req/s)\b", raw) is None
