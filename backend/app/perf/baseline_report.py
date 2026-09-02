"""Versioned report envelope for the measured baseline (issue #951).

:mod:`app.perf.baseline_stats` produces the per-path distribution summary
from repeated baseline runs. This module wraps that raw statistics block in
a buyer-facing envelope: a stable schema fingerprint of the workload it
measured, a generation timestamp, a contract version, and a plain-language
summary an engineer can read without opening the JSON.

The envelope is additive -- the full :func:`aggregate_baseline` output is
preserved verbatim under ``statistics`` -- so a downstream consumer can
ignore the envelope entirely.

Like everything under :mod:`app.perf`, this records observations only. It
carries **no latency, throughput, or memory threshold** and makes no
pass/fail judgement; capacity targets are set from measured baseline runs
and never invented here.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from app.perf.baseline_stats import aggregate_baseline
from app.perf.workload_profiles import generate_workload_snapshot

#: Report envelope contract version. Distinct from the statistics block's own
#: fields; bump when the envelope shape changes.
REPORT_VERSION = "1"


def _schema_fingerprint(snapshot: dict[str, Any] | None) -> str:
    """Return a stable ``"sha256:"``-prefixed fingerprint of a snapshot.

    The snapshot is serialized with sorted keys and a string fallback for
    non-JSON values, so the same schema always yields the same fingerprint
    regardless of dict ordering. This matches
    ``app.spec.normalization_report.schema_fingerprint``; the two should be
    unified into one shared helper once both land on ``main``.
    """
    canonical = json.dumps(
        snapshot or {}, sort_keys=True, default=str, separators=(",", ":")
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _summarize(statistics: dict[str, Any]) -> dict[str, Any]:
    """Build the plain-language summary block from an ``aggregate_baseline`` result.

    Picks the path with the largest 95th-percentile wall time as the one an
    engineer should look at first. Reports names and counts only -- never a
    duration value, so the summary carries no implied threshold.
    """
    paths: dict[str, Any] = statistics.get("paths", {})
    path_names = sorted(paths)
    if path_names:
        slowest = max(
            path_names, key=lambda name: paths[name]["wall_seconds"]["p95"]
        )
    else:
        slowest = ""

    profile = statistics.get("profile", "?")
    repeat = statistics.get("repeat", 0)
    if not path_names:
        headline = f"{profile} profile: no measured paths."
    else:
        headline = (
            f"{profile} profile, {len(path_names)} measured paths over "
            f"{repeat} run(s); slowest by wall-time 95th percentile is "
            f"{slowest}."
        )
    return {
        "headline": headline,
        "path_count": len(path_names),
        "slowest_path_by_wall_p95": slowest,
    }


def build_baseline_report(
    profile_name: str, *, repeat: int, seed: int | None = None
) -> dict[str, Any]:
    """Run the repeat-baseline aggregation and wrap it in a versioned envelope.

    Args:
        profile_name: One of
            :func:`app.perf.workload_profiles.list_profiles`.
        repeat: Number of baseline runs to aggregate (forwarded to
            :func:`app.perf.baseline_stats.aggregate_baseline`; must be >= 1).
        seed: Optional PRNG seed forwarded to both the aggregation and the
            fingerprinted workload snapshot, so the fingerprint identifies
            exactly the schema that was measured.

    Returns:
        A dict with:

        ``report_version``
            :data:`REPORT_VERSION`.
        ``generated_at``
            UTC ISO-8601 timestamp of this envelope.
        ``schema_fingerprint``
            ``"sha256:"``-prefixed fingerprint of the generated workload
            snapshot that was measured.
        ``summary``
            ``{headline, path_count, slowest_path_by_wall_p95}`` -- names and
            counts only, no duration values.
        ``statistics``
            The full :func:`aggregate_baseline` output, unmodified.

        The report contains only observations; it has no thresholds and no
        verdict.

    Raises:
        ValueError: Propagated from :func:`aggregate_baseline` if ``repeat``
            is less than 1.
        KeyError: If ``profile_name`` is not a known profile.
    """
    statistics = aggregate_baseline(profile_name, repeat=repeat, seed=seed)
    snapshot = generate_workload_snapshot(profile_name, seed=seed)
    return {
        "report_version": REPORT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "schema_fingerprint": _schema_fingerprint(snapshot),
        "summary": _summarize(statistics),
        "statistics": statistics,
    }
