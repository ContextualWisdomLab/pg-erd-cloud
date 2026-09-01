"""Repeat-run aggregation for the measured performance baseline (issue #951).

:mod:`app.perf.baseline` times each pure processing path once. A single
timing is noisy, so this module runs the baseline ``repeat`` times over the
*same* generated workload (the snapshot is fixed by the seed; only the
timing varies) and reduces the samples to a small distribution summary --
min, max, mean, and the 50th / 95th / 99th percentiles -- per path.

Like the harness it wraps, this module records observations only. It
carries **no latency, throughput, or memory threshold** and makes no
pass/fail judgement; the percentile targets a capacity profile eventually
publishes are set from measured baseline runs and never invented here.

Run it directly::

    python -m app.perf.baseline_stats --profile small --repeat 5 --json
"""

from __future__ import annotations

import argparse
import json
import statistics
from datetime import datetime, timezone
from typing import Any

from app.perf.baseline import run_baseline
from app.perf.workload_profiles import list_profiles

#: Distribution fields reported for ``wall_seconds`` and ``peak_bytes``.
SUMMARY_FIELDS: tuple[str, ...] = ("samples", "min", "max", "mean", "p50", "p95", "p99")


def _summarize(values: list[float]) -> dict[str, Any]:
    """Reduce a list of samples to a distribution summary.

    With fewer than two samples every percentile is just the single value
    (``statistics.quantiles`` needs at least two points). ``samples`` keeps
    the raw observations so a caller can re-aggregate or plot them.
    """
    ordered = sorted(values)
    if len(ordered) < 2:
        only = ordered[0]
        return {
            "samples": list(values),
            "min": only,
            "max": only,
            "mean": only,
            "p50": only,
            "p95": only,
            "p99": only,
        }
    cuts = statistics.quantiles(ordered, n=100, method="inclusive")
    return {
        "samples": list(values),
        "min": ordered[0],
        "max": ordered[-1],
        "mean": statistics.fmean(ordered),
        "p50": cuts[49],
        "p95": cuts[94],
        "p99": cuts[98],
    }


def aggregate_baseline(
    profile_name: str, *, repeat: int, seed: int | None = None
) -> dict[str, Any]:
    """Run :func:`app.perf.baseline.run_baseline` ``repeat`` times and summarize.

    Args:
        profile_name: One of :func:`app.perf.workload_profiles.list_profiles`.
        repeat: Number of baseline runs to collect (must be >= 1). Each run
            uses the same ``seed``, so the workload snapshot is identical and
            only the measured timing/allocation varies.
        seed: Optional PRNG seed forwarded to each run. ``None`` uses the
            profile's own default seed.

    Returns:
        A report dict with ``profile``, ``repeat``, ``seed``, ``generated_at``
        (UTC ISO-8601), ``relation_count``, ``column_count``, and ``paths`` --
        a map from path name to ``{wall_seconds: <summary>, peak_bytes:
        <summary>, result_size_bytes: <int>}`` where ``<summary>`` has the
        :data:`SUMMARY_FIELDS` keys. ``result_size_bytes`` is deterministic
        for a fixed snapshot, so it is reported once as a scalar.

    Raises:
        ValueError: If ``repeat`` is less than 1.
        KeyError: If ``profile_name`` is not a known profile.
        KeyboardInterrupt: If a run is cancelled. No partial aggregate is
            returned.
    """
    if repeat < 1:
        raise ValueError(f"repeat must be >= 1, got {repeat}")

    runs: list[dict[str, Any]] = []
    try:
        # ponytail: collect every run or raise -- a cancelled aggregation
        # never returns a half-filled distribution.
        for _ in range(repeat):
            runs.append(run_baseline(profile_name, seed=seed))
    except KeyboardInterrupt:
        raise

    first = runs[0]
    path_names = list(first["paths"])
    paths: dict[str, dict[str, Any]] = {}
    for name in path_names:
        wall = [run["paths"][name]["wall_seconds"] for run in runs]
        peak = [float(run["paths"][name]["peak_bytes"]) for run in runs]
        paths[name] = {
            "wall_seconds": _summarize(wall),
            "peak_bytes": _summarize(peak),
            "result_size_bytes": first["paths"][name]["result_size_bytes"],
        }

    return {
        "profile": profile_name,
        "repeat": repeat,
        "seed": first["seed"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "relation_count": first["relation_count"],
        "column_count": first["column_count"],
        "paths": paths,
    }


def _format_table(report: dict[str, Any]) -> str:
    """Render ``report`` as a short fixed-width table for terminal reading."""
    lines = [
        f"profile={report['profile']} repeat={report['repeat']} "
        f"seed={report['seed']} relations={report['relation_count']} "
        f"columns={report['column_count']}",
        f"{'path':<28} {'wall_p50_ms':>13} {'wall_p95_ms':>13} "
        f"{'wall_p99_ms':>13} {'peak_mean_kib':>15}",
    ]
    for name, row in report["paths"].items():
        wall = row["wall_seconds"]
        lines.append(
            f"{name:<28} {wall['p50'] * 1000:>13.3f} {wall['p95'] * 1000:>13.3f} "
            f"{wall['p99'] * 1000:>13.3f} {row['peak_bytes']['mean'] / 1024:>15.1f}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: aggregate the baseline for one profile and print it.

    Args:
        argv: Argument list (defaults to ``sys.argv[1:]``).

    Returns:
        Process exit code (``0`` on success).
    """
    parser = argparse.ArgumentParser(
        prog="python -m app.perf.baseline_stats",
        description=(
            "Run the measured baseline several times and reduce each path to "
            "a distribution summary. Observations only -- no thresholds, no "
            "verdict."
        ),
    )
    parser.add_argument(
        "--profile",
        default="small",
        choices=list_profiles(),
        help="workload profile to generate (default: small)",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=5,
        help="number of baseline runs to collect (default: 5)",
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

    report = aggregate_baseline(args.profile, repeat=args.repeat, seed=args.seed)
    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print(_format_table(report))
    return 0


if __name__ == "__main__":  # pragma: no cover - thin CLI shim
    raise SystemExit(main())
