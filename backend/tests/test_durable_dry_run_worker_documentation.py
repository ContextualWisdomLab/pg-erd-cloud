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
    normalized = " ".join(contract.split())
    required = (
        "make_durable_dry_run_attempt_handler",
        "MigrationRunAttemptClaim",
        "IsolatedSandboxRequest",
        "LivePreflightRequest",
        "guard_live_preflight_handoff",
        "load_guarded_live_preflight_target",
        "encrypted DSN ciphertext and nonce",
        "execute_isolated_dry_run",
        "execute_bound_live_preflight",
        "complete_isolated_dry_run",
        "complete_live_preflight",
        "exact expected run state version",
        "one fresh database statement",
        "PostgreSQL 14–18 matrix exercises",
        "does not eliminate the gap",
        "does not implement or prove",
        "decryption, target connection, provider composition and startup wiring remain Planned",
        "live apply",
        "production readiness",
    )

    assert [term for term in required if term not in normalized] == []


def test_worker_contract_names_are_present_in_production_source() -> None:
    """Bind published contract names to the implementation modules."""

    implementation = _read(Path("backend/app/jobs/migration_dry_run_worker.py"))
    authority = _read(
        Path("backend/app/jobs/migration_dry_run_worker_contract.py")
    )

    assert "make_durable_dry_run_attempt_handler" in implementation
    assert "guard_live_preflight_handoff" in implementation
    assert "load_guarded_live_preflight_target" in implementation
    assert "class GuardedLivePreflightTarget" in implementation
    assert "_refresh_live_stage" in implementation
    assert "class IsolatedSandboxRequest" in authority
    assert "class LivePreflightRequest" in authority


def test_uml_marks_durable_dry_run_sequence_partial_without_provider_claims() -> None:
    """Keep the sequence maturity aligned with orchestration and provider gaps."""

    uml = _read(Path("docs/UML.md"))
    dry_run_section = uml.split("## Target dry-run sequence", 1)[1].split(
        "## Target apply and verification sequence", 1
    )[0]
    normalized = " ".join(dry_run_section.split())

    assert "**Status: Partially implemented.**" in normalized
    assert "provider-neutral durable worker orchestration" in normalized
    assert "sandbox provisioning" in normalized
    assert "target credential binding" in normalized
    assert "application startup wiring" in normalized
    assert "**Planned**" in normalized


def test_worker_contract_bounds_whole_capability_stages() -> None:
    """Keep cancellation deadlines distinct from proven provider termination."""

    contract = " ".join(_read(WORKER_CONTRACT).split()).lower()
    assert "whole-stage sandbox and preflight cancellation deadlines" in contract
    assert "timeout cancellation and capability cleanup" in contract
    assert "cooperative cancellation" in contract
    assert "does not prove a hard wall-clock termination bound" in contract
