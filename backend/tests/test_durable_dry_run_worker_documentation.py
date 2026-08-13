"""Guard the partial durable dry-run worker documentation contract."""

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
WORKER_CONTRACT = Path("docs/contracts/durable-dry-run-worker-v1.md")
WORKER_ADR = Path("docs/adr/ADR-0002-isolated-dry-run-and-preflight.md")


def _read(path: Path) -> str:
    return (REPOSITORY_ROOT / path).read_text(encoding="utf-8")


def test_durable_dry_run_worker_contract_is_canonical_and_linked() -> None:
    """Keep the versioned worker contract reachable from its accepted ADR."""

    assert (REPOSITORY_ROOT / WORKER_CONTRACT).is_file()
    contract = _read(WORKER_CONTRACT)
    adr = _read(WORKER_ADR)

    assert "durable-dry-run-worker/v1" in contract
    assert "**Capability status:** Partial" in contract
    assert "../contracts/durable-dry-run-worker-v1.md" in adr


def test_worker_contract_preserves_authority_and_maturity_boundaries() -> None:
    """Prevent orchestration from being documented as provider or apply authority."""

    contract = _read(WORKER_CONTRACT)
    required = (
        "make_durable_dry_run_attempt_handler",
        "MigrationRunAttemptClaim",
        "IsolatedSandboxRequest",
        "LivePreflightRequest",
        "execute_isolated_dry_run",
        "execute_bound_live_preflight",
        "complete_isolated_dry_run",
        "complete_live_preflight",
        "cancellation or CAS loss",
        "does not implement or prove",
        "live apply",
        "production readiness",
    )

    assert [term for term in required if term not in contract] == []


def test_worker_contract_names_are_present_in_production_source() -> None:
    """Bind published contract names to the implementation modules."""

    implementation = _read(Path("backend/app/jobs/migration_dry_run_worker.py"))
    authority = _read(
        Path("backend/app/jobs/migration_dry_run_worker_contract.py")
    )

    assert "make_durable_dry_run_attempt_handler" in implementation
    assert "_refresh_live_stage" in implementation
    assert "class IsolatedSandboxRequest" in authority
    assert "class LivePreflightRequest" in authority
