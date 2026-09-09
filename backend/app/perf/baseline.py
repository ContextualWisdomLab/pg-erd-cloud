"""Measured baseline harness for the performance & capacity profile (issue #951).

This module times the *pure* snapshot-processing paths of pg-erd-cloud
against a deterministic, anonymized workload snapshot. All capacity
targets are set from measured baseline runs and never invented; this
harness produces the measurements those targets are set from.

Every number produced here is an observation of the machine and code that
ran it. The module deliberately carries no latency, throughput, or memory
threshold and makes no pass/fail judgement: it only records
``wall_seconds``, ``peak_bytes``, and ``result_size_bytes`` per path.
Downstream capacity work is expected to run this harness on agreed
reference hardware and set its targets from the results.

Run it directly for a quick look::

    python -m app.perf.baseline --profile small --json

The measured paths are all side-effect free (no database, no network, no
disk): a canonical snapshot hash, a JSON encode/decode round-trip, a
self-diff, PostgreSQL and Snowflake DDL export, and a Markdown data
dictionary render.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import tracemalloc
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from app.ddl.export import snapshot_json_to_sql
from app.diff.schema_diff import diff_snapshots
from app.perf.workload_profiles import generate_workload_snapshot, list_profiles
from app.spec.data_dictionary import snapshot_to_data_dictionary_md

#: Fields recorded for every measured path. Kept as a constant so tests and
#: callers can assert on the shape without hard-coding the strings twice.
MEASUREMENT_FIELDS: tuple[str, ...] = (
    "wall_seconds",
    "peak_bytes",
    "result_size_bytes",
)


def _canonical_json(value: object) -> str:
    """Return a deterministic JSON string for ``value`` (sorted keys, tight)."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _result_size_bytes(value: object) -> int:
    """Return the UTF-8 byte length of ``value`` rendered as text.

    Strings and bytes are measured directly; anything else is measured as
    its canonical JSON form. This is a size *observation* of each path's
    output, not a limit.
    """
    if isinstance(value, str):
        return len(value.encode("utf-8"))
    if isinstance(value, (bytes, bytearray)):
        return len(value)
    return len(_canonical_json(value).encode("utf-8"))


def _measured_paths(snapshot: dict[str, Any]) -> dict[str, Callable[[], object]]:
    """Build the name -> zero-argument callable map of pure paths to time.

    Each callable closes over ``snapshot`` and, when invoked, runs exactly
    one side-effect-free processing path and returns its result so the
    harness can size it.
    """
    encoded = json.dumps(snapshot)
    return {
        "canonical_hash": lambda: hashlib.sha256(
            _canonical_json(snapshot).encode("utf-8")
        ).hexdigest(),
        "json_round_trip": lambda: json.loads(encoded),
        "schema_self_diff": lambda: diff_snapshots(snapshot, snapshot),
        "ddl_export_postgresql": lambda: snapshot_json_to_sql(snapshot, "postgresql"),
        "ddl_export_snowflake": lambda: snapshot_json_to_sql(snapshot, "snowflake"),
        "data_dictionary_markdown": lambda: snapshot_to_data_dictionary_md(snapshot),
    }


def _measure_one(thunk: Callable[[], object]) -> dict[str, float | int]:
    """Time one path callable and report wall time, peak memory, output size.

    ``tracemalloc`` must already be started by the caller; this function
    resets the peak counter so the reading reflects only ``thunk``.
    """
    tracemalloc.reset_peak()
    start = time.perf_counter()
    result = thunk()
    wall_seconds = time.perf_counter() - start
    _current, peak_bytes = tracemalloc.get_traced_memory()
    return {
        "wall_seconds": wall_seconds,
        "peak_bytes": peak_bytes,
        "result_size_bytes": _result_size_bytes(result),
    }


def run_baseline(profile_name: str, *, seed: int | None = None) -> dict[str, Any]:
    """Generate a workload snapshot and time every pure processing path over it.

    Args:
        profile_name: One of :func:`app.perf.workload_profiles.list_profiles`
            (``small`` / ``medium`` / ``large``).
        seed: Optional PRNG seed forwarded to the workload generator. ``None``
            uses the profile's own default seed, so the run stays deterministic.

    Returns:
        A report dict with ``profile``, ``seed``, ``generated_at`` (UTC
        ISO-8601), ``relation_count``, ``column_count``, and ``paths`` -- a
        map from path name to a dict of :data:`MEASUREMENT_FIELDS`. The
        report contains only observations; it has no thresholds and no
        verdict.

    Raises:
        KeyError: If ``profile_name`` is not a known profile.
        KeyboardInterrupt: If the run is cancelled mid-measurement. The
            partially filled measurement map is never returned.
    """
    snapshot = generate_workload_snapshot(profile_name, seed=seed)
    resolved_seed = snapshot.get("workload_profile", {}).get("seed", seed)

    paths: dict[str, dict[str, float | int]] = {}
    tracemalloc.start()
    try:
        # ponytail: build the whole map or raise -- never hand back a
        # half-measured report if the loop is interrupted.
        for name, thunk in _measured_paths(snapshot).items():
            paths[name] = _measure_one(thunk)
    except KeyboardInterrupt:
        raise
    finally:
        tracemalloc.stop()

    return {
        "profile": profile_name,
        "seed": resolved_seed,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "relation_count": len(snapshot.get("relations") or []),
        "column_count": len(snapshot.get("columns") or []),
        "paths": paths,
    }


def _format_table(report: dict[str, Any]) -> str:
    """Render ``report`` as a short fixed-width table for terminal reading."""
    lines = [
        f"profile={report['profile']} seed={report['seed']} "
        f"relations={report['relation_count']} columns={report['column_count']}",
        f"{'path':<28} {'wall_ms':>12} {'peak_kib':>12} {'size_bytes':>12}",
    ]
    for name, row in report["paths"].items():
        lines.append(
            f"{name:<28} {row['wall_seconds'] * 1000:>12.3f} "
            f"{row['peak_bytes'] / 1024:>12.1f} {row['result_size_bytes']:>12d}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: run the baseline for one profile and print the result.

    Args:
        argv: Argument list (defaults to ``sys.argv[1:]``).

    Returns:
        Process exit code (``0`` on success).
    """
    parser = argparse.ArgumentParser(
        prog="python -m app.perf.baseline",
        description=(
            "Measure the pure snapshot-processing paths over a generated "
            "workload. Prints observations only -- no thresholds, no verdict."
        ),
    )
    parser.add_argument(
        "--profile",
        default="small",
        choices=list_profiles(),
        help="workload profile to generate (default: small)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="optional PRNG seed (default: the profile's own seed)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit the raw report as JSON instead of a table",
    )
    args = parser.parse_args(argv)

    report = run_baseline(args.profile, seed=args.seed)
    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print(_format_table(report))
    return 0


if __name__ == "__main__":  # pragma: no cover - thin CLI shim
    raise SystemExit(main())
