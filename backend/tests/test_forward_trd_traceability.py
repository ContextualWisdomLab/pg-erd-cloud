"""Guard forward-engineering requirement-to-evidence traceability."""

from __future__ import annotations

import re
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _traceability_row(requirement: str) -> str:
    """Return one normalized TRD traceability row by requirement identity."""

    trd = (REPOSITORY_ROOT / "docs/TRD.md").read_text(encoding="utf-8")
    prefix = f"| {requirement} |"
    matches = [line for line in trd.splitlines() if line.startswith(prefix)]

    assert len(matches) == 1
    return " ".join(matches[0].split()).casefold()


def test_trd_traceability_records_current_forward_foundations() -> None:
    """Keep implemented foundations distinct from remaining deployment gates."""

    dry_run = _traceability_row("FE-TRD-006\u2013008")
    durable_runs = _traceability_row("FE-TRD-009\u2013012")

    assert "metadata only" not in dry_run
    assert "isolated dry-run execution/convergence core" in dry_run
    assert "bound read-only live preflight" in dry_run
    assert "test_forward_isolated_dry_run.py" in dry_run
    assert "test_forward_live_preflight" in dry_run
    assert "sandbox provisioning/materialization/isolation/cleanup" in dry_run
    assert "credential-bound worker execution" in dry_run
    assert "live apply" in dry_run

    assert "design/adr/contract only" not in durable_runs
    assert "durable run/event/outbox/attempt persistence" in durable_runs
    assert "uuid-only dispatch" in durable_runs
    assert "exact signal/attempt leases" in durable_runs
    assert "dry-run/apply-intent/cancellation apis" in durable_runs
    assert "test_migration_run_consumer.py" in durable_runs
    assert "test_postgres_migration_run_integration.py" in durable_runs
    assert "application startup/credentials/deployed worker" in durable_runs
    assert "crash recovery/no-replay reconciliation" in durable_runs
    assert "live apply/convergence" in durable_runs


def test_trd_traceability_names_existing_test_files() -> None:
    """Reject stale exact test filenames in the evidence matrix."""

    trd = (REPOSITORY_ROOT / "docs/TRD.md").read_text(encoding="utf-8")
    traceability = trd.split("## Requirement-to-evidence traceability", 1)[1]
    test_filenames = set(re.findall(r"`(test_[^`*]+\.py)`", traceability))

    missing = sorted(
        filename
        for filename in test_filenames
        if not (REPOSITORY_ROOT / "backend/tests" / filename).is_file()
    )
    assert missing == []
