"""Guard the canonical forward-engineering documentation contract."""

from __future__ import annotations

import re
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

CANONICAL_DOCUMENTS = (
    Path("ARCHITECTURE.md"),
    Path("docs/PRD.md"),
    Path("docs/TRD.md"),
    Path("docs/UML.md"),
    Path("docs/DATA_MODEL.md"),
    Path("docs/DOCUMENTATION_AUDIT.md"),
    Path("docs/TEST_STRATEGY.md"),
    Path("docs/STANDARDS.md"),
    Path("docs/security/forward-engineering-threat-model.md"),
    Path("docs/runbooks/forward-engineering.md"),
    Path("docs/contracts/forward-engineering-v1.md"),
    Path("docs/adr/README.md"),
    Path("docs/adr/ADR-0001-server-authoritative-planning.md"),
    Path("docs/adr/ADR-0002-isolated-dry-run-and-preflight.md"),
    Path("docs/adr/ADR-0003-plan-execution-segmentation.md"),
    Path("docs/adr/ADR-0004-durable-runs-and-recovery.md"),
    Path("docs/adr/ADR-0005-authority-approvals-and-convergence.md"),
)

MERMAID_DOCUMENTS = (
    Path("ARCHITECTURE.md"),
    Path("docs/UML.md"),
    Path("docs/DATA_MODEL.md"),
)

CURRENT_ROUTES = (
    "POST /api/schema-models/by-project/{project_space_uuid}",
    "GET /api/schema-models/{schema_model_uuid}",
    "PUT /api/schema-models/{schema_model_uuid}",
    "POST /api/schema-model-revisions/{schema_model_revision_uuid}/migration-plans",
    "GET /api/migration-plans/{migration_plan_uuid}",
    "POST /api/migration-plans/{migration_plan_uuid}/dry-runs",
    "GET /api/migration-runs/{migration_run_uuid}",
)

PLANNED_ROUTES = (
    "POST /api/migration-plans/{migration_plan_uuid}/apply-runs",
)

README_CORE_LINKS = (
    "ARCHITECTURE.md",
    "docs/PRD.md",
    "docs/TRD.md",
    "docs/adr/README.md",
    "docs/contracts/forward-engineering-v1.md",
    "docs/UML.md",
    "docs/DATA_MODEL.md",
    "docs/security/forward-engineering-threat-model.md",
    "docs/runbooks/forward-engineering.md",
    "docs/DOCUMENTATION_AUDIT.md",
)


def _read(relative_path: Path) -> str:
    return (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")


def test_canonical_forward_engineering_documents_exist_and_are_nonempty() -> None:
    """Require every canonical forward-engineering document to contain text."""

    missing = [
        path.as_posix()
        for path in CANONICAL_DOCUMENTS
        if not (REPOSITORY_ROOT / path).is_file()
    ]
    empty = [
        path.as_posix()
        for path in CANONICAL_DOCUMENTS
        if (REPOSITORY_ROOT / path).is_file() and not _read(path).strip()
    ]

    assert missing == []
    assert empty == []


def test_architecture_views_remain_renderable_mermaid_documents() -> None:
    """Keep every required architecture view renderable as Mermaid source."""

    without_mermaid = [
        path.as_posix() for path in MERMAID_DOCUMENTS if "```mermaid" not in _read(path)
    ]

    assert without_mermaid == []


def test_v1_contract_separates_current_routes_from_remaining_run_routes() -> None:
    """Keep retrieval implemented without presenting execution routes as live."""

    contract = _read(Path("docs/contracts/forward-engineering-v1.md"))

    missing_current = [route for route in CURRENT_ROUTES if route not in contract]
    missing_planned = [route for route in PLANNED_ROUTES if route not in contract]

    assert missing_current == []
    assert missing_planned == []
    assert "## 5. Current HTTP API contract" in contract
    assert "## 8. Migration-plan retrieval and bounded run API" in contract
    assert "Implemented" in contract
    assert "each route is classified below" in " ".join(contract.split())


def test_v1_contract_does_not_classify_plan_retrieval_as_planned() -> None:
    """Keep the implemented immutable-plan read surface out of planned scope."""

    contract = _read(Path("docs/contracts/forward-engineering-v1.md"))
    normalized_contract = " ".join(contract.split())

    assert "**Planned:** plan retrieval" not in normalized_contract
    assert (
        "| `GET /api/migration-plans/{migration_plan_uuid}` | none | "
        "current `MigrationPlanOut`, `200` | member | Implemented |"
        in normalized_contract
    )


def test_v1_contract_keeps_blocked_statements_as_review_only_proposals() -> None:
    """Keep blocked SQL visible for review but unavailable for execution."""

    contract = _read(Path("docs/contracts/forward-engineering-v1.md"))
    normalized_contract = " ".join(contract.split())

    assert "proposed_statements" in contract
    assert (
        "When `blockers` is non-empty, `statements` is empty" in normalized_contract
    )
    assert "`proposed_statements` solely for complete review" in normalized_contract


def test_v1_contract_keeps_current_concurrency_and_identifier_authority_explicit() -> None:
    """Retain concurrency, snapshot, and identifier authority in the contract."""

    contract = _read(Path("docs/contracts/forward-engineering-v1.md"))

    for required_term in (
        "strong `ETag`",
        "revision UUID",
        "snapshot_contract_version",
        "read-only repeatable-read transaction",
        "`object_ref` and `dependency_refs` are authoritative",
        "display-only",
        "recomputes the canonical plan digest",
    ):
        assert required_term in contract

    normalized_contract = " ".join(contract.split())
    assert (
        "The immutable preview exposes project, model-revision, connection, "
        "base-snapshot, snapshot-contract, PostgreSQL-major, creator, and creation-time "
        "bindings" in normalized_contract
    )


def test_docs_track_the_persisted_migration_run_foundation_without_overclaim() -> None:
    """Track the consumer contract without claiming startup or execution."""

    contract = _read(Path("docs/contracts/forward-engineering-v1.md"))
    trd = _read(Path("docs/TRD.md"))
    data_model = _read(Path("docs/DATA_MODEL.md"))
    adr = _read(Path("docs/adr/ADR-0004-durable-runs-and-recovery.md"))

    assert "These symbols and tables do not exist" not in contract
    assert "**Partially implemented:** durable run/event persistence" in contract
    assert "### Partially implemented foundation" in trd
    assert "## Physical run foundation — Implemented" in data_model
    assert "**Implementation status:** Partially implemented" in adr
    normalized_contract = " ".join(contract.lower().split())
    assert "public apply creation remains **planned**" in normalized_contract
    assert (
        "post /api/migration-plans/{migration_plan_uuid}/dry-runs"
        in normalized_contract
    )
    assert (
        "post /api/migration-runs/{migration_run_uuid}/cancel"
        in normalized_contract
    )
    assert "stable sanitized run-action error envelope" in normalized_contract
    assert "migration_run_dispatch" in normalized_contract
    assert "identifier-only transactional outbox" in normalized_contract
    assert "migration_run_dispatch" in trd
    assert "migration_run_dispatch" in data_model
    assert "identifier-only transactional outbox" in adr.lower()
    assert "lock-scoped due-order outbox claiming" in normalized_contract
    assert "bounded one-attempt publisher is **implemented**" in normalized_contract
    assert "every persisted plan precondition" in normalized_contract
    assert "missing, extra, duplicate, or kind-mismatched checks" in normalized_contract
    assert "scheduled relay lifecycle is **implemented**" in normalized_contract
    assert "dedicated valkey sorted-set key" in normalized_contract
    assert (
        "execution-neutral consumer contract is **implemented**"
        in normalized_contract
    )
    assert (
        "application startup wiring and worker execution remain **planned**"
        in normalized_contract
    )
    assert "Startup fails closed when Valkey is unavailable" not in adr
    assert "Startup rejects an unconfigured Valkey backend" in adr


def test_dispatch_relay_has_explicit_deployment_and_lifecycle_contract() -> None:
    """Keep the opt-in relay wired without implying execution authority."""

    environment = _read(Path(".env.example"))
    main = _read(Path("backend/app/main.py"))
    runbook = _read(Path("docs/runbooks/forward-engineering.md"))

    assert "MIGRATION_DISPATCH_RELAY_ENABLED=false" in environment
    assert "MIGRATION_DISPATCH_RELAY_POLL_INTERVAL_SECONDS=1.0" in environment
    assert "run_migration_dispatch_relay_forever" in main
    assert "migration-dispatch-relay" in main
    assert "MIGRATION_DISPATCH_RELAY_ENABLED" in runbook
    assert "does not start a queue consumer" in " ".join(runbook.split())


def test_ci_runs_real_supported_postgresql_migration_acceptance() -> None:
    """Keep PostgreSQL 14-18 acceptance explicit and image-digest pinned."""

    workflow = _read(Path(".github/workflows/ci.yml"))
    strategy = _read(Path("docs/TEST_STRATEGY.md"))

    for major in range(14, 19):
        assert f'major: "{major}"' in workflow
    assert workflow.count("postgres@sha256:") == 5
    assert "test_postgres_migration_run_integration.py" in workflow
    assert "CREATE DATABASE pg_erd_cloud_sandbox" in workflow
    assert "POSTGRES_SANDBOX_INTEGRATION_URL" in workflow
    assert "CREATE DATABASE pg_erd_cloud_target" in workflow
    assert "POSTGRES_TARGET_INTEGRATION_URL" in workflow
    assert "CREATE ROLE cwl_erd_preflight" in workflow
    assert "CREATE ROLE pg_" not in workflow
    assert "POSTGRES_PREFLIGHT_INTEGRATION_URL" in workflow
    integration_test = _read(
        Path("backend/tests/test_postgres_migration_run_integration.py")
    )
    assert 'os.getenv("POSTGRES_SANDBOX_INTEGRATION_URL")' in integration_test
    assert 'os.getenv("POSTGRES_TARGET_INTEGRATION_URL")' in integration_test
    assert (
        'os.getenv("POSTGRES_PREFLIGHT_INTEGRATION_URL")' in integration_test
    )
    assert "_sandbox_asyncpg_url()" in integration_test
    assert "_target_asyncpg_url()" in integration_test
    assert "_preflight_asyncpg_url()" in integration_test
    assert "PostgreSQL 14\u201318" in strategy
    assert "migration-run/outbox" in strategy


def test_bound_live_preflight_maturity_is_canonical() -> None:
    """Keep same-snapshot capture binding distinct from worker authority."""

    implementation = _read(Path("backend/app/forward/live_preflight.py"))
    durable_implementation = _read(Path("backend/app/forward/migration_run.py"))
    required_documents = (
        Path("ARCHITECTURE.md"),
        Path("CHANGELOG.md"),
        Path("docs/TRD.md"),
        Path("docs/DATA_MODEL.md"),
        Path("docs/DOCUMENTATION_AUDIT.md"),
        Path("docs/UML.md"),
        Path("docs/contracts/forward-engineering-v1.md"),
        Path("docs/adr/ADR-0002-isolated-dry-run-and-preflight.md"),
        Path("docs/TEST_STRATEGY.md"),
        Path("docs/runbooks/forward-engineering.md"),
    )

    assert "execute_bound_live_preflight" in implementation
    assert "complete_isolated_dry_run" in durable_implementation
    assert "complete_live_preflight" in durable_implementation
    integration_test = _read(
        Path("backend/tests/test_postgres_migration_run_integration.py")
    )
    strategy = _read(Path("docs/TEST_STRATEGY.md"))
    changelog = _read(Path("CHANGELOG.md"))
    contract = _read(Path("docs/contracts/forward-engineering-v1.md"))
    standards = _read(Path("docs/STANDARDS.md"))
    assert "LOCK TABLE {qualified} IN ACCESS EXCLUSIVE MODE" in integration_test
    assert "connection.is_in_transaction() is False" in integration_test
    assert "denied_table_name" in integration_test
    assert "pg_catalog.pg_stat_activity" in integration_test
    assert "wait_event_type = 'Lock'" in integration_test
    assert "pg_catalog.pg_terminate_backend" in integration_test
    assert "connection.is_closed() is True" in integration_test
    assert "real relation-lock wait" in strategy
    assert "ungranted-table SELECT failure" in strategy
    assert "terminates the backend" in strategy
    assert "ACCESS EXCLUSIVE" in changelog
    assert "pg_terminate_backend" in changelog
    assert "relation-lock wait" in contract
    assert "SELECT denial" in contract
    assert "terminates the restricted backend" in contract
    assert (
        "`table_is_empty` precondition primitive and completion CAS are "
        "Implemented" in contract
    )
    assert (
        "`no_null_values` precondition primitive and completion CAS are "
        "Implemented" in contract
    )
    assert (
        "`castable_values` precondition primitive and completion CAS are "
        "Implemented" in contract
    )
    assert (
        "bounded live-preflight execution and completion CAS are Implemented"
        in standards
    )
    assert (
        "bounded all-transactional isolated executor core is Implemented"
        in standards
    )
    for path in required_documents:
        document = _read(path)
        assert "complete_isolated_dry_run" in document
        assert "execute_bound_live_preflight" in document
        assert "complete_live_preflight" in document
        assert "caller-owned" in document


def test_ci_generates_ephemeral_integration_credentials() -> None:
    """Keep test credentials ephemeral and checkout credentials unavailable."""

    workflow = _read(Path(".github/workflows/ci.yml"))

    assert "POSTGRES_PASSWORD: postgres" not in workflow
    assert "postgres:postgres" not in workflow
    assert "integration-only-app-secret" not in workflow
    assert "openssl rand -hex" in workflow
    step_blocks = re.findall(
        r"(?ms)^      - (?P<step>.*?)(?=^      - |\Z)", workflow
    )
    checkout_steps = [
        step for step in step_blocks if "uses: actions/checkout@" in step
    ]
    assert checkout_steps
    assert all("persist-credentials: false" in step for step in checkout_steps)


def test_dispatch_relay_documentation_separates_implemented_and_planned_scope() -> None:
    """Keep scheduler maturity distinct from consumer/worker maturity."""

    data_model = _read(Path("docs/DATA_MODEL.md"))
    audit = _read(Path("docs/DOCUMENTATION_AUDIT.md"))

    assert "Additional **Implemented and Planned** invariants:" in data_model
    assert "- **Implemented — scheduled relay lifecycle:**" in data_model
    assert (
        "- **Implemented — execution-neutral queue consumer contract:**"
        in data_model
    )
    assert (
        "- **Implemented — scheduled relay lifecycle and UUID-only publication:**"
        in audit
    )
    assert "- **Implemented — execution-neutral queue consumer contract:**" in audit
    assert (
        "- **Planned — application consumer wiring, worker execution, "
        "failover, and retention:**" in audit
    )
    assert "Relay loop/queue delivery" not in audit


def test_signal_lease_documentation_keeps_execution_boundary_explicit() -> None:
    """Track exact lease ownership without claiming a worker exists."""

    contract = " ".join(
        _read(Path("docs/contracts/forward-engineering-v1.md")).lower().split()
    )
    trd = " ".join(_read(Path("docs/TRD.md")).lower().split())
    runbook = " ".join(
        _read(Path("docs/runbooks/forward-engineering.md")).lower().split()
    )

    for document in (contract, trd, runbook):
        assert "exact lease-token" in document
        assert "exact signal claim" in document
        assert "exact lease renewal" in document
        assert "execution-neutral consumer contract is **implemented**" in document
        assert (
            "application startup wiring and worker execution remain **planned**"
            in document
        )

    consumer = _read(Path("backend/app/jobs/migration_run_consumer.py"))
    queue = _read(Path("backend/app/jobs/valkey_queue.py"))
    main = _read(Path("backend/app/main.py"))
    assert "process_one_migration_run_signal" in consumer
    assert "run_migration_run_consumer_forever" in consumer
    assert "renew_migration_run_signal" in queue
    assert "run_migration_run_consumer_forever" not in main


def test_ci_runs_real_valkey_signal_acceptance() -> None:
    """Keep UUID-only queue separation tested against a pinned real service."""

    workflow = _read(Path(".github/workflows/ci.yml"))
    strategy = _read(Path("docs/TEST_STRATEGY.md"))

    assert "valkey-integration:" in workflow
    assert "valkey/valkey@sha256:" in workflow
    assert "test_valkey_queue_integration.py" in workflow
    assert "VALKEY_INTEGRATION_URL" in workflow
    assert "real Valkey" in strategy


def test_superseded_adr_is_not_restored() -> None:
    """Prevent a superseded ADR from reappearing beside canonical decisions."""

    superseded = REPOSITORY_ROOT / "docs/adr/0001-server-authoritative-migration-plans.md"

    assert not superseded.exists()


def test_readme_links_the_core_forward_engineering_documents() -> None:
    """Keep the repository entry point linked to canonical product memory."""

    readme = _read(Path("README.md"))
    missing_links = [target for target in README_CORE_LINKS if target not in readme]

    assert missing_links == []
