from __future__ import annotations

import json
from collections import defaultdict
from typing import Literal


SpecMode = Literal["markdown", "llm-prompt"]


def _text(value: object, default: str = "") -> str:
    return value if isinstance(value, str) else default


def _bool_text(value: object) -> str:
    return "yes" if value is True else "no"


def _escape_cell(value: object) -> str:
    text = _text(value, "-") or "-"
    return text.replace("|", "\\|").replace("\n", " ")


def _relation_label(row: dict) -> str:
    schema = _text(row.get("schema_name"), "unknown")
    name = _text(row.get("relation_name"), "unknown")
    return f"{schema}.{name}"


def _relation_kind_name(kind: object) -> str:
    if not isinstance(kind, str):
        return "relation"
    kind_names = {
        "r": "table",
        "p": "partitioned table",
        "v": "view",
        "m": "materialized view",
    }
    return kind_names.get(kind, "relation")


def _rows(snapshot: dict, key: str) -> list[dict]:
    value = snapshot.get(key)
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


def _compact_snapshot_summary(snapshot: dict) -> dict:
    relations = _rows(snapshot, "relations")
    columns = _rows(snapshot, "columns")
    constraints = _rows(snapshot, "constraints")
    indexes = _rows(snapshot, "indexes")
    fk_edges = _rows(snapshot, "fk_edges")

    columns_by_oid: dict[int, list[dict]] = defaultdict(list)
    for column in columns:
        oid = column.get("relation_oid")
        if isinstance(oid, int):
            columns_by_oid[oid].append(
                {
                    "name": column.get("column_name"),
                    "type": column.get("data_type"),
                    "not_null": column.get("is_not_null") is True,
                    "default": column.get("default_expr"),
                    "example": column.get("example_value"),
                    "comment": column.get("column_comment"),
                }
            )

    constraints_by_oid: dict[int, list[dict]] = defaultdict(list)
    for constraint in constraints:
        oid = constraint.get("relation_oid")
        if isinstance(oid, int):
            constraints_by_oid[oid].append(
                {
                    "name": constraint.get("constraint_name"),
                    "type": constraint.get("constraint_type"),
                    "definition": constraint.get("constraint_def"),
                }
            )

    indexes_by_oid: dict[int, list[dict]] = defaultdict(list)
    for index in indexes:
        oid = index.get("relation_oid")
        if isinstance(oid, int):
            indexes_by_oid[oid].append(
                {
                    "name": index.get("index_name"),
                    "unique": index.get("is_unique") is True,
                    "primary": index.get("is_primary") is True,
                    "method": index.get("access_method"),
                    "predicate": index.get("predicate_expr"),
                }
            )

    objects: list[dict] = []
    for relation in relations:
        oid = relation.get("relation_oid")
        if not isinstance(oid, int):
            continue
        objects.append(
            {
                "name": _relation_label(relation),
                "kind": _relation_kind_name(relation.get("relation_kind")),
                "comment": relation.get("relation_comment"),
                "columns": columns_by_oid.get(oid, []),
                "constraints": constraints_by_oid.get(oid, []),
                "indexes": indexes_by_oid.get(oid, []),
            }
        )

    relationships = [
        {
            "constraint": edge.get("fk_constraint_name"),
            "from": (
                f"{edge.get('child_schema_name')}.{edge.get('child_relation_name')}"
                f".{edge.get('child_column_name')}"
            ),
            "to": (
                f"{edge.get('parent_schema_name')}.{edge.get('parent_relation_name')}"
                f".{edge.get('parent_column_name')}"
            ),
        }
        for edge in fk_edges
    ]

    return {
        "source_dialect": snapshot.get("source_dialect")
        or snapshot.get("database_dialect")
        or "postgresql",
        "server_version": snapshot.get("server_version"),
        "captured_at": snapshot.get("captured_at"),
        "schema_filter": snapshot.get("schema_filter"),
        "objects": objects,
        "relationships": relationships,
    }


def generate_reversing_llm_prompt(snapshot: dict) -> str:
    """Build a provider-neutral prompt for LLM-assisted DB reversing specs."""

    summary = _compact_snapshot_summary(snapshot)
    payload = json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True)
    return "\n".join(
        [
            "# DB Reversing Specification Prompt",
            "",
            "You are a senior data architect. Generate a concise DB reversing",
            "specification from the supplied schema snapshot. Focus on business",
            "entities, relationships, key constraints, indexing intent, and",
            "open questions. Do not invent facts that are not supported by the",
            "snapshot. Mark uncertain business meanings as assumptions.",
            "",
            "Return Markdown with these sections:",
            "- Overview",
            "- Entity catalog",
            "- Relationship model",
            "- Constraint and index interpretation",
            "- Data quality and modeling questions",
            "",
            "Snapshot summary:",
            "```json",
            payload,
            "```",
            "",
        ]
    )


def _generate_markdown_header(summary: dict) -> list[str]:
    objects = summary.get("objects", [])
    relationships = summary.get("relationships", [])
    return [
        "# DB Reversing Specification",
        "",
        "## Snapshot",
        f"- Source dialect: {_text(summary.get('source_dialect'), 'postgresql')}",
        f"- Server version: {_text(summary.get('server_version'), '-') or '-'}",
        f"- Captured at: {_text(summary.get('captured_at'), '-') or '-'}",
        f"- Schema filter: {_text(summary.get('schema_filter'), '-') or '-'}",
        "",
        "## Object Inventory",
        f"- Relations: {len(objects)}",
        f"- Relationships: {len(relationships)}",
        "",
        "## Entity Catalog",
    ]


def _generate_markdown_entity(obj: dict) -> list[str]:
    lines = [
        "",
        f"### {_text(obj.get('name'), 'unknown')}",
        f"- Kind: {_text(obj.get('kind'), 'relation')}",
    ]
    comment = obj.get("comment")
    if isinstance(comment, str) and comment:
        lines.append(f"- Comment: {comment}")

    lines.extend(
        [
            "",
            "| Column | Type | Required | Default | Example | Comment |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for column in obj.get("columns", []):
        if not isinstance(column, dict):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_cell(column.get("name")),
                    _escape_cell(column.get("type")),
                    _bool_text(column.get("not_null")),
                    _escape_cell(column.get("default")),
                    _escape_cell(column.get("example")),
                    _escape_cell(column.get("comment")),
                ]
            )
            + " |"
        )

    constraints = [
        item for item in obj.get("constraints", []) if isinstance(item, dict)
    ]
    if constraints:
        lines.extend(["", "Constraints:"])
        for constraint in constraints:
            lines.append(
                "- "
                f"{_escape_cell(constraint.get('name'))} "
                f"({_escape_cell(constraint.get('type'))}): "
                f"{_escape_cell(constraint.get('definition'))}"
            )

    indexes = [item for item in obj.get("indexes", []) if isinstance(item, dict)]
    if indexes:
        lines.extend(["", "Indexes:"])
        for index in indexes:
            intent = []
            if index.get("primary") is True:
                intent.append("primary")
            if index.get("unique") is True:
                intent.append("unique")
            if index.get("method"):
                intent.append(f"method={index.get('method')}")
            if index.get("predicate"):
                intent.append("partial")
            suffix = f" [{', '.join(intent)}]" if intent else ""
            lines.append(f"- {_escape_cell(index.get('name'))}{suffix}")

    return lines


def _generate_markdown_entity_catalog(objects: list[dict]) -> list[str]:
    if not objects:
        return ["", "_No relations were captured in this snapshot._"]
    lines = []
    for obj in objects:
        lines.extend(_generate_markdown_entity(obj))
    return lines


def _generate_markdown_relationship_model(relationships: list[dict]) -> list[str]:
    lines = ["", "## Relationship Model"]
    if not relationships:
        lines.append("_No foreign-key relationships were captured._")
    for relationship in relationships:
        lines.append(
            "- "
            f"{_escape_cell(relationship.get('from'))} -> "
            f"{_escape_cell(relationship.get('to'))} "
            f"({_escape_cell(relationship.get('constraint'))})"
        )
    return lines


def _generate_markdown_footer() -> list[str]:
    return [
        "",
        "## LLM Review Prompt",
        "Use `/reversing-spec.md?mode=llm-prompt` to generate a compact prompt",
        "for an approved LLM provider. The prompt includes only schema metadata",
        "from this snapshot and asks the model to mark unsupported business",
        "meaning as assumptions.",
        "When a provider is configured, `/reversing-spec.md?mode=llm-draft`",
        "asks the provider to generate a Markdown draft directly.",
        "",
    ]


def generate_reversing_markdown(snapshot: dict) -> str:
    """Generate a deterministic DB reversing specification draft."""

    summary = _compact_snapshot_summary(snapshot)
    lines: list[str] = []
    lines.extend(_generate_markdown_header(summary))
    lines.extend(_generate_markdown_entity_catalog(summary["objects"]))
    lines.extend(_generate_markdown_relationship_model(summary["relationships"]))
    lines.extend(_generate_markdown_footer())
    return "\n".join(lines)


def generate_reversing_spec(snapshot: dict, mode: str = "markdown") -> str:
    """Generate a reverse-engineering document or LLM prompt from a snapshot."""
    if mode == "llm-prompt":
        return generate_reversing_llm_prompt(snapshot)
    if mode == "markdown":
        return generate_reversing_markdown(snapshot)
    raise ValueError(f"unsupported reversing spec mode: {mode}")
