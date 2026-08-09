"""Guard the canonical forward-engineering documentation contract."""

from __future__ import annotations

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
)

PLANNED_ROUTES = (
    "POST /api/migration-plans/{migration_plan_uuid}/dry-runs",
    "POST /api/migration-plans/{migration_plan_uuid}/apply-runs",
    "GET /api/migration-runs/{migration_run_uuid}",
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
    assert "## 8. Migration-plan retrieval and planned run API" in contract
    assert "Implemented" in contract
    assert "remaining run routes" in contract


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


def test_superseded_adr_is_not_restored() -> None:
    """Prevent a superseded ADR from reappearing beside canonical decisions."""

    superseded = REPOSITORY_ROOT / "docs/adr/0001-server-authoritative-migration-plans.md"

    assert not superseded.exists()


def test_readme_links_the_core_forward_engineering_documents() -> None:
    """Keep the repository entry point linked to canonical product memory."""

    readme = _read(Path("README.md"))
    missing_links = [target for target in README_CORE_LINKS if target not in readme]

    assert missing_links == []
