"""Measure deterministic snapshot serialization and DDL export paths."""

from __future__ import annotations

import argparse
import json
import platform
import resource
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.ddl.export import snapshot_json_to_sql  # noqa: E402
from capacity_profile import PROFILES, VARIANTS, generate_snapshot  # noqa: E402


def _git_commit() -> str:
    """Return the measured source commit, or ``unknown`` outside Git."""

    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return result.stdout.strip() or "unknown"


def _percentile(samples: list[float], percentile: float) -> float:
    """Return a nearest-rank percentile from non-empty samples."""

    if not samples:
        raise ValueError("at least one benchmark sample is required")
    ordered = sorted(samples)
    index = min(len(ordered) - 1, round((percentile / 100) * len(ordered)))
    return ordered[index]


def _peak_rss_kib() -> int:
    """Return peak resident memory in KiB on macOS and Linux."""

    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value / 1024) if sys.platform == "darwin" else int(value)


def _measure(operation: Callable[[], Any], repetitions: int) -> dict[str, Any]:
    """Measure wall-clock milliseconds and peak resident memory."""

    if repetitions < 1:
        raise ValueError("repetitions must be positive")
    samples: list[float] = []
    for _ in range(repetitions):
        started = time.perf_counter()
        operation()
        samples.append((time.perf_counter() - started) * 1000)
    return {
        "samples_ms": [round(sample, 3) for sample in samples],
        "p50_ms": round(_percentile(samples, 50), 3),
        "p95_ms": round(_percentile(samples, 95), 3),
        "peak_rss_kib": _peak_rss_kib(),
    }


def run(profile_name: str, variant: str, seed: int, repetitions: int) -> dict[str, Any]:
    """Generate and measure one profile without contacting a customer system."""

    snapshot = generate_snapshot(profile_name, seed=seed, variant=variant)
    encoded = json.dumps(snapshot, ensure_ascii=False, sort_keys=True)
    export = _measure(lambda: snapshot_json_to_sql(snapshot), repetitions)
    encoding = _measure(lambda: json.dumps(snapshot, ensure_ascii=False), repetitions)
    return {
        "profile": profile_name,
        "variant": variant,
        "seed": seed,
        "counts": {
            "relations": len(snapshot["relations"]),
            "columns": len(snapshot["columns"]),
            "constraints": len(snapshot["constraints"]),
            "indexes": len(snapshot["indexes"]),
            "snapshot_bytes": len(encoded.encode("utf-8")),
        },
        "measurements": {"json_encode": encoding, "snowflake_ddl_export": export},
    }


def main() -> None:
    """Run one profile and emit a reproducibility manifest as JSON."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=sorted(PROFILES), default="small")
    parser.add_argument("--variant", choices=sorted(VARIANTS), default="baseline")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--repetitions", type=int, default=3)
    args = parser.parse_args()
    result = run(args.profile, args.variant, args.seed, args.repetitions)
    result["environment"] = {
        "commit": _git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
