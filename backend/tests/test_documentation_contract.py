"""Machine-check the repository's canonical documentation authority graph."""

from __future__ import annotations

import ast
import re
from pathlib import Path
from urllib.parse import unquote


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

CANONICAL_FILES = (
    "ARCHITECTURE.md",
    "docs/README.md",
    "docs/observability.md",
    "docs/ci-drift-check.md",
    "docs/PRD.md",
    "docs/TRD.md",
    "docs/API.md",
    "docs/UML.md",
    "docs/ERD.md",
    "docs/forward-engineering-support-matrix.md",
    "docs/threat-model.md",
    "docs/test-strategy.md",
    "docs/traceability-matrix.md",
    "docs/documentation-coverage-matrix.md",
    "docs/references.md",
    "docs/operations-runbook.md",
    "docs/release-plan.md",
    "docs/automation-contract.md",
    "docs/adr/README.md",
    "docs/ui-ux/figma-contract.md",
)

LIFECYCLE_LABELS = {
    "implemented_on_main",
    "active_pr",
    "planned",
    "research_only",
    "downstream",
    "deprecated",
    "out_of_scope",
}

LEGACY_SINGLE_WORD_COLUMNS = {
    "schema_snapshot.status",
    "job_queue.status",
    "diagram_view.name",
    "table_annotation.body",
}


def _read(relative_path: str) -> str:
    return (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")


def test_canonical_documentation_files_exist_and_are_substantive() -> None:
    """Every authority linked from the index must be present and nontrivial."""

    for relative_path in CANONICAL_FILES:
        path = REPOSITORY_ROOT / relative_path
        assert path.is_file(), f"missing canonical documentation: {relative_path}"
        assert len(path.read_text(encoding="utf-8").splitlines()) >= 10, (
            f"canonical documentation is unexpectedly short: {relative_path}"
        )


def test_canonical_authority_index_matches_contract_inventory() -> None:
    """Every authority row must participate in the machine-checked graph."""

    authority_section = _read("docs/README.md").split(
        "## Canonical authorities", 1
    )[1].split("## Related control and integration documents", 1)[0]
    indexed_files = {
        str(
            (REPOSITORY_ROOT / "docs" / target)
            .resolve()
            .relative_to(REPOSITORY_ROOT.resolve())
        )
        for target in re.findall(r"\[[^\]]+\]\(([^)#?]+)(?:[?#][^)]*)?\)", authority_section)
    }

    assert indexed_files == set(CANONICAL_FILES) - {"docs/README.md"}


def test_documentation_index_defines_every_lifecycle_label() -> None:
    """A shared lifecycle vocabulary prevents planned work looking shipped."""

    index = _read("docs/README.md")
    for label in LIFECYCLE_LABELS:
        assert f"`{label}`" in index


def test_canonical_internal_markdown_links_resolve() -> None:
    """Relative links in canonical authorities must resolve inside the repo."""

    link_pattern = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
    failures: list[str] = []

    for relative_path in CANONICAL_FILES:
        source_path = REPOSITORY_ROOT / relative_path
        for raw_target in link_pattern.findall(source_path.read_text(encoding="utf-8")):
            target = raw_target.strip().split(maxsplit=1)[0].strip("<>")
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target_path = unquote(target.split("#", 1)[0].split("?", 1)[0])
            if not target_path:
                continue
            resolved = (source_path.parent / target_path).resolve()
            if not resolved.is_relative_to(REPOSITORY_ROOT.resolve()):
                failures.append(f"{relative_path}: link escapes repository: {target}")
            elif not resolved.exists():
                failures.append(f"{relative_path}: missing link target: {target}")

    assert not failures, "\n".join(failures)


def test_adr_index_matches_files_and_required_sections() -> None:
    """The ADR index and durable decision files must not silently diverge."""

    adr_directory = REPOSITORY_ROOT / "docs/adr"
    index_content = _read("docs/adr/README.md")
    indexed = set(re.findall(r"\((000\d-[^)]+\.md)\)", index_content))
    actual = {path.name for path in adr_directory.glob("[0-9][0-9][0-9][0-9]-*.md")}
    assert indexed == actual

    required_sections = (
        "## Context",
        "## Decision",
        "## Alternatives considered",
        "## Consequences",
        "## Verification",
        "## References",
    )
    for filename in sorted(actual):
        content = _read(f"docs/adr/{filename}")
        status_match = re.search(r"^- Status: (\w+)$", content, flags=re.MULTILINE)
        assert status_match is not None
        index_status_match = re.search(
            rf"\({re.escape(filename)}\)\s*\|[^|\n]*\|\s*([^|\n]+?)\s*\|",
            index_content,
        )
        assert index_status_match is not None
        assert index_status_match.group(1) == status_match.group(1)
        assert "- Lifecycle:" in content
        for section in required_sections:
            assert section in content, f"{filename} is missing {section}"


def test_required_architecture_diagram_views_are_present() -> None:
    """Structure, interaction, state, deployment, class and data views exist."""

    content = "\n".join(
        _read(path) for path in ("ARCHITECTURE.md", "docs/UML.md", "docs/ERD.md")
    )
    minimum_counts = {
        "flowchart": 4,
        "sequenceDiagram": 3,
        "stateDiagram-v2": 2,
        "classDiagram": 1,
        "erDiagram": 2,
    }
    for diagram_kind, minimum in minimum_counts.items():
        assert content.count(f"```mermaid\n{diagram_kind}") >= minimum


def test_prd_requirements_are_present_in_traceability_matrix() -> None:
    """Every stable PRD requirement ID must appear in traceability."""

    requirement_pattern = re.compile(r"\b[A-Z][A-Z0-9]+-\d{3}\b")
    prd_ids = set(requirement_pattern.findall(_read("docs/PRD.md")))
    traced_ids = set(requirement_pattern.findall(_read("docs/traceability-matrix.md")))
    assert prd_ids
    assert prd_ids <= traced_ids, f"untraced requirements: {sorted(prd_ids - traced_ids)}"


def test_figma_contract_keeps_current_live_file_authority() -> None:
    """The contract records current live metadata and dated historical nodes."""

    contract = _read("docs/ui-ux/figma-contract.md")
    assert "csnpEEJfmqFWB0vNUoTkWA" in contract
    assert "`0:1`" in contract
    assert "`8:2`" in contract
    assert "Historical screen nodes (2026-08-09 audit)" in contract
    assert "`29:143` no longer exists" in contract


def test_current_model_naming_exceptions_are_exactly_inventoried() -> None:
    """New single-token persisted fields cannot bypass NAME-010 silently."""

    module = ast.parse(_read("backend/app/models.py"))
    violations: set[str] = set()
    table_names: list[str] = []

    for node in module.body:
        if not isinstance(node, ast.ClassDef):
            continue
        table_name: str | None = None
        column_names: list[str] = []
        for statement in node.body:
            if (
                isinstance(statement, ast.Assign)
                and any(
                    isinstance(target, ast.Name) and target.id == "__tablename__"
                    for target in statement.targets
                )
                and isinstance(statement.value, ast.Constant)
                and isinstance(statement.value.value, str)
            ):
                table_name = statement.value.value
            elif isinstance(statement, ast.AnnAssign) and isinstance(
                statement.target, ast.Name
            ):
                column_names.append(statement.target.id)

        if table_name is None:
            continue
        table_names.append(table_name)
        for column_name in column_names:
            if "_" not in column_name:
                violations.add(f"{table_name}.{column_name}")

    assert table_names
    assert all("_" in table_name for table_name in table_names)
    assert violations == LEGACY_SINGLE_WORD_COLUMNS

    erd = _read("docs/ERD.md")
    for violation in LEGACY_SINGLE_WORD_COLUMNS:
        assert f"`{violation}`" in erd


def test_planned_forward_engineering_entities_follow_naming_contract() -> None:
    """The planned persistent model uses descriptive multi-token names."""

    erd = _read("docs/ERD.md")
    for table_name in (
        "schema_model_revision",
        "migration_plan",
        "migration_statement",
        "migration_approval",
        "migration_execution_job",
        "migration_audit_event",
        "migration_audit_checkpoint",
    ):
        assert f"`{table_name}`" in erd or table_name.upper() in erd
