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
    "POST /api/migration-plans/{migration_plan_uuid}/apply-runs",
    "GET /api/migration-runs/{migration_run_uuid}",
)

PLANNED_ROUTES: tuple[str, ...] = ()

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


def test_published_apply_intent_route_is_not_classified_as_planned() -> None:
    """Keep the non-dispatched intent endpoint separate from planned execution."""

    route = "POST /api/migration-plans/{migration_plan_uuid}/apply-runs"

    assert route in CURRENT_ROUTES
    assert route not in PLANNED_ROUTES


def test_trd_tracks_current_apply_intent_and_migration_contract() -> None:
    """Keep the TRD aligned with the implemented non-dispatched intent slice."""

    trd = _read(Path("docs/TRD.md"))
    normalized = " ".join(trd.split())

    assert "apply creation Planned" not in normalized
    assert "future apply routes must reuse it" not in normalized
    assert "apply-intent creation HTTP" in normalized
    assert "the apply-intent route reuses it" in normalized
    for revision in (
        "0008_schema_model_revision",
        "0009_migration_plan",
        "0010_migration_run",
        "0011_migration_run_attempt",
        "0012_apply_intent_confirmation",
    ):
        assert revision in trd


def test_forward_browser_transport_is_partial_without_execution_authority() -> None:
    """Track typed browser transport without claiming the forward UI exists."""

    client = _read(Path("frontend/src/api.ts"))
    review_panel = _read(
        Path("frontend/src/components/forward/PlanReviewPanel.tsx")
    )
    review_surface = _read(
        Path("frontend/src/components/forward/PlanReviewSurface.tsx")
    )
    modal = _read(
        Path("frontend/src/components/forward/ForwardEngineeringModal.tsx")
    )
    run_panel = _read(
        Path("frontend/src/components/forward/RunStatusPanel.tsx")
    )
    run_surface = _read(
        Path("frontend/src/components/forward/RunStatusSurface.tsx")
    )
    dry_run_intent = _read(
        Path("frontend/src/components/forward/DryRunIntentPanel.tsx")
    )
    cancellation_control = _read(
        Path("frontend/src/components/forward/RunCancellationControl.tsx")
    )
    documents = (
        _read(Path("ARCHITECTURE.md")),
        _read(Path("docs/PRD.md")),
        _read(Path("docs/TRD.md")),
        _read(Path("docs/TEST_STRATEGY.md")),
    )

    for symbol in (
        "getMigrationPlan",
        "createDryRun",
        "createApplyRun",
        "getMigrationRun",
        "cancelMigrationRun",
    ):
        assert symbol in client
    for symbol in (
        "MigrationPlan",
        "plan.proposed_statements",
        "plan.blockers",
        "이 화면은 SQL 실행 권한을 갖지 않습니다",
    ):
        assert symbol in review_panel
    for symbol in (
        "getMigrationPlan",
        "계획을 불러오는 중입니다",
        "계획을 불러오지 못했습니다",
        "다시 시도",
        "active = false",
    ):
        assert symbol in review_surface
    for symbol in (
        "useDialogAccessibility",
        'role="dialog"',
        'aria-modal="true"',
        "PlanReviewSurface",
        "RunStatusSurface",
    ):
        assert symbol in modal
    for symbol in (
        "MigrationRun",
        'role="status"',
        "자동 재실행이 금지됩니다",
        "서버가 검증한 이벤트 메타데이터만 표시합니다",
    ):
        assert symbol in run_panel
    for symbol in (
        "getMigrationRun",
        "TERMINAL_RUN_STATES",
        "실행 상태를 불러오는 중입니다",
        "실행 상태를 불러오지 못했습니다",
        "active = false",
    ):
        assert symbol in run_surface
    for symbol in (
        "createDryRun",
        "plan.plan_digest",
        "plan.can_dry_run",
        "web-dry-run-",
        "globalThis.crypto.randomUUID",
        "inFlightRef",
        "같은 요청 다시 시도",
    ):
        assert symbol in dry_run_intent
    for symbol in (
        "cancelMigrationRun",
        "run.state_version",
        "isTerminalMigrationRunState",
        "inFlightRef",
        "요청을 자동으로 반복하지 말고",
        "실행 상태 새로고침",
    ):
        assert symbol in cancellation_control
    for document in documents:
        normalized = " ".join(document.lower().split())
        assert "typed browser transport is **partially implemented**" in normalized
        assert "plan review panel is **partially implemented**" in normalized
        assert "stale-response suppression is **partially implemented**" in normalized
        assert "forward engineering modal shell is **partially implemented**" in normalized
        assert "run status and audit panel is **partially implemented**" in normalized
        assert "terminal-aware polling is **partially implemented**" in normalized
        assert "dry-run intent control is **partially implemented**" in normalized
        assert "cancellation intent control is **partially implemented**" in normalized
        assert "forward ui remains **planned**" in normalized


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
    assert "public apply intent creation is **implemented**" in normalized_contract
    assert "for update" in normalized_contract
    assert "stale_revision" in normalized_contract
    assert (
        "post /api/migration-plans/{migration_plan_uuid}/dry-runs"
        in normalized_contract
    )
    assert (
        "post /api/migration-runs/{migration_run_uuid}/cancel"
        in normalized_contract
    )
    assert (
        "post /api/migration-plans/{migration_plan_uuid}/apply-runs"
        in normalized_contract
    )
    assert "creates no dispatch" in normalized_contract
    assert "0012_apply_intent_confirmation" in data_model
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
    assert "VALKEY_INTEGRATION_URL: redis://127.0.0.1:6379/0" in workflow
    assert "Verify PostgreSQL and Valkey dual-lease recovery" in workflow
    postgres_job = workflow.split("  postgres-integration:", 1)[1].split(
        "  valkey-integration:", 1
    )[0]
    assert "services:" in postgres_job
    assert "valkey/valkey@sha256:" in postgres_job
    integration_test = _read(
        Path("backend/tests/test_postgres_migration_run_integration.py")
    )
    assert (
        "test_real_postgres_and_valkey_recover_failure_and_crash"
        in integration_test
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
        "- **Planned — application startup wiring, worker execution, "
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
        assert "expired signal owner cannot renew" in document
        assert "automatic heartbeat is **implemented**" in document
        assert "execution-neutral consumer contract is **implemented**" in document
        assert "application startup wiring" in document
        assert "worker execution remain **planned**" in document

    assert "exact lease-token claim/renew/ack/release primitives" in trd

    consumer = _read(Path("backend/app/jobs/migration_run_consumer.py"))
    queue = _read(Path("backend/app/jobs/valkey_queue.py"))
    main = _read(Path("backend/app/main.py"))
    assert "process_one_migration_run_signal" in consumer
    assert "run_migration_run_consumer_forever" in consumer
    assert "renew_migration_run_signal" in queue
    assert "run_migration_run_consumer_forever" not in main


def test_durable_attempt_documentation_is_implemented_without_authority_claim() -> None:
    """Keep durable ownership distinct from consumer, credentials, and execution."""

    documents = {
        path: " ".join(_read(Path(path)).lower().split())
        for path in (
            "ARCHITECTURE.md",
            "docs/PRD.md",
            "docs/TRD.md",
            "docs/DATA_MODEL.md",
            "docs/DOCUMENTATION_AUDIT.md",
            "docs/adr/ADR-0004-durable-runs-and-recovery.md",
            "docs/contracts/forward-engineering-v1.md",
            "docs/security/forward-engineering-threat-model.md",
            "docs/runbooks/forward-engineering.md",
            "docs/TEST_STRATEGY.md",
        )
    }
    for document in documents.values():
        assert "attempt" in document
        assert "hash" in document
        assert "planned" in document

    assert "0011_migration_run_attempt" in documents["docs/DATA_MODEL.md"]
    assert "at most one" in documents["docs/DATA_MODEL.md"]
    contract = documents["docs/contracts/forward-engineering-v1.md"]
    assert "exact-token cas" in contract
    assert "complete an expired attempt" in contract
    assert "consumer-to-attempt binding" in documents["docs/DOCUMENTATION_AUDIT.md"]
    assert "application startup wiring" in documents["docs/DOCUMENTATION_AUDIT.md"]
    assert "partial foundation" in documents["docs/PRD.md"]


def test_consumer_attempt_binding_is_documented_without_startup_or_sql_authority() -> None:
    """Track the exact dual-lease adapter while keeping deployment Planned."""

    documents = [
        " ".join(_read(Path(path)).lower().split())
        for path in (
            "ARCHITECTURE.md",
            "docs/PRD.md",
            "docs/TRD.md",
            "docs/contracts/forward-engineering-v1.md",
            "docs/runbooks/forward-engineering.md",
            "docs/TEST_STRATEGY.md",
        )
    ]
    for document in documents:
        assert "consumer-to-attempt binding is **implemented**" in document
        assert "application startup wiring" in document
        assert "worker execution" in document
        assert "**planned**" in document

    consumer = _read(Path("backend/app/jobs/migration_run_consumer.py"))
    main = _read(Path("backend/app/main.py"))
    assert "make_attempt_bound_migration_run_handler" in consumer
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


def test_claude_guidance_tracks_partial_forward_engineering_authority() -> None:
    """Keep coding-agent guidance aligned without claiming live apply readiness."""

    guidance = _read(Path("CLAUDE.md"))
    normalized = " ".join(guidance.split())

    for route_group in (
        "schema_models",
        "migration_plans",
        "migration_runs",
    ):
        assert route_group in guidance
    assert "UUID-only migration dispatch relay" in normalized
    assert "provider-neutral dry-run/preflight orchestration" in normalized
    assert "concrete sandbox and target credential providers" in normalized
    assert "It is not a production apply executor" in normalized
    assert (
        "Never describe this partial control plane as production apply readiness"
        in normalized
    )
