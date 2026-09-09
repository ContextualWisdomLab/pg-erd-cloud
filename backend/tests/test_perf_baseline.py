"""Tests for :mod:`app.perf.baseline`.

The harness must time every pure processing path over a generated workload,
report observations only (wall time, peak memory, output size), stay
deterministic under a fixed seed, never leave ``tracemalloc`` running after a
cancelled run, and carry no invented performance threshold.
"""

from __future__ import annotations

import json
import re
import tracemalloc
from datetime import datetime
from pathlib import Path

import pytest

from app.perf import baseline
from app.perf.baseline import MEASUREMENT_FIELDS, main, run_baseline

_EXPECTED_PATHS = {
    "canonical_hash",
    "json_round_trip",
    "schema_self_diff",
    "ddl_export_postgresql",
    "ddl_export_snowflake",
    "data_dictionary_markdown",
}


def test_run_baseline_small_reports_every_measured_path() -> None:
    report = run_baseline("small")
    assert set(report["paths"]) == _EXPECTED_PATHS
    for row in report["paths"].values():
        assert set(row) == set(MEASUREMENT_FIELDS)
        assert row["wall_seconds"] > 0.0
        assert row["peak_bytes"] >= 0
        assert row["result_size_bytes"] > 0


def test_report_carries_profile_seed_and_generated_at() -> None:
    report = run_baseline("small")
    assert report["profile"] == "small"
    assert isinstance(report["seed"], int)
    assert report["relation_count"] == 100
    assert report["column_count"] == 2_000
    stamp = datetime.fromisoformat(report["generated_at"])
    assert stamp.tzinfo is not None


def test_seed_override_is_forwarded_into_the_report() -> None:
    assert run_baseline("small", seed=12_345)["seed"] == 12_345


def test_two_runs_with_the_same_seed_size_paths_identically() -> None:
    a = run_baseline("small", seed=7)
    b = run_baseline("small", seed=7)
    sizes_a = {name: row["result_size_bytes"] for name, row in a["paths"].items()}
    sizes_b = {name: row["result_size_bytes"] for name, row in b["paths"].items()}
    assert sizes_a == sizes_b


def test_unknown_profile_raises_key_error() -> None:
    with pytest.raises(KeyError):
        run_baseline("enterprise")


def test_run_baseline_is_cancellation_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}
    real = baseline._measure_one

    def flaky(thunk: object) -> object:
        calls["n"] += 1
        if calls["n"] == 2:
            raise KeyboardInterrupt
        return real(thunk)  # type: ignore[arg-type]

    monkeypatch.setattr(baseline, "_measure_one", flaky)
    with pytest.raises(KeyboardInterrupt):
        run_baseline("small")
    # The finally-block must have torn tracemalloc down; no partial report leaks.
    assert tracemalloc.is_tracing() is False


def test_cli_json_emits_a_parseable_report(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--profile", "small", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert set(report["paths"]) == _EXPECTED_PATHS


def test_cli_table_output_is_human_readable(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--profile", "small"]) == 0
    out = capsys.readouterr().out
    assert "profile=small" in out
    assert "wall_ms" in out


def test_module_states_targets_are_measured_and_invents_no_threshold() -> None:
    raw = Path("app/perf/baseline.py").read_text(encoding="utf-8").lower()
    prose = re.sub(r"\s+", " ", raw)
    assert "set from measured baseline runs and never invented" in prose
    assert "no latency, throughput, or memory threshold" in prose
    assert "makes no pass/fail judgement" in prose
    assert re.search(r"\b\d+(\.\d+)?\s*(ms|milliseconds|seconds)\b", raw) is None
    assert re.search(r"p9[59]\s*[<>=:]", raw) is None
    assert re.search(r"\b\d+\s*(rps|qps|req/s|requests per second)\b", raw) is None
