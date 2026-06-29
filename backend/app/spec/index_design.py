from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Literal

from app.jobs.valkey_queue import valkey_queue_config_summary


SpecMode = Literal["markdown", "llm-prompt"]
MAX_IDENTIFIER_LENGTH = 63


def _text(value: object, default: str = "") -> str:
    return value if isinstance(value, str) else default


def _rows(snapshot: dict, key: str) -> list[dict]:
    value = snapshot.get(key)
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


def _q(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _qname(schema: str, name: str) -> str:
    return f"{_q(schema)}.{_q(name)}"


def _identifier_part(value: str) -> str:
    chars = [ch.lower() if ch.isalnum() else "_" for ch in value]
    text = "".join(chars).strip("_")
    while "__" in text:
        text = text.replace("__", "_")
    return text or "col"


def _index_name(table_name: str, columns: list[str]) -> str:
    raw = f"idx_{_identifier_part(table_name)}_{'_'.join(_identifier_part(c) for c in columns)}"
    return raw[:MAX_IDENTIFIER_LENGTH]


def _escape_cell(value: object) -> str:
    text = "-" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def _relation_label(row: dict) -> str:
    schema = _text(row.get("schema_name"), "unknown")
    name = _text(row.get("relation_name"), "unknown")
    return f"{schema}.{name}"


def _relation_maps(snapshot: dict) -> tuple[dict[int, dict], dict[str, int]]:
    by_oid: dict[int, dict] = {}
    oid_by_label: dict[str, int] = {}
    for relation in _rows(snapshot, "relations"):
        oid = relation.get("relation_oid")
        if not isinstance(oid, int):
            continue
        by_oid[oid] = relation
        oid_by_label[_relation_label(relation)] = oid
    return by_oid, oid_by_label


def _columns_by_relation(snapshot: dict) -> dict[int, list[dict]]:
    grouped: dict[int, list[dict]] = defaultdict(list)
    for column in _rows(snapshot, "columns"):
        oid = column.get("relation_oid")
        if isinstance(oid, int):
            grouped[oid].append(column)
    return grouped


def _indexes_by_relation(snapshot: dict) -> dict[int, list[dict]]:
    grouped: dict[int, list[dict]] = defaultdict(list)
    for index in _rows(snapshot, "indexes"):
        oid = index.get("relation_oid") or index.get("table_oid")
        if isinstance(oid, int):
            grouped[oid].append(index)
    return grouped


def _citus_by_relation(snapshot: dict) -> dict[int, dict]:
    result: dict[int, dict] = {}
    for row in _rows(snapshot, "citus_distributed_tables"):
        oid = row.get("relation_oid")
        if isinstance(oid, int):
            result[oid] = row
    return result


def _fk_groups(snapshot: dict) -> list[dict]:
    groups: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for edge in _rows(snapshot, "fk_edges"):
        constraint = _text(edge.get("fk_constraint_name"), "fk")
        child_oid = edge.get("child_relation_oid")
        if isinstance(child_oid, int):
            groups[(constraint, child_oid)].append(edge)

    result = []
    for (constraint, child_oid), edges in groups.items():
        ordered = sorted(edges, key=lambda x: int(x.get("column_ordinal") or 0))
        columns = [
            _text(edge.get("child_column_name"))
            for edge in ordered
            if _text(edge.get("child_column_name"))
        ]
        if columns:
            result.append(
                {
                    "constraint": constraint,
                    "child_relation_oid": child_oid,
                    "columns": columns,
                }
            )
    return result


def _existing_index_column_text(index: dict) -> str:
    index_def = index.get("index_def")
    if not isinstance(index_def, str):
        return ""
    marker = " USING "
    if marker not in index_def:
        return index_def.lower()
    return index_def.split(marker, 1)[1].lower()


def _index_mentions_column(index_text: str, column: str) -> bool:
    quoted = _q(column).lower()
    if quoted in index_text:
        return True
    return re.search(rf"\b{re.escape(column.lower())}\b", index_text) is not None


def _has_covering_index(
    indexes: list[dict],
    columns: list[str],
) -> bool:
    for index in indexes:
        if index.get("is_primary") is True:
            continue
        column_text = _existing_index_column_text(index)
        if columns and all(
            _index_mentions_column(column_text, column) for column in columns
        ):
            return True
    return False


def _candidate_indexes(snapshot: dict) -> list[dict]:
    relations_by_oid, _ = _relation_maps(snapshot)
    indexes_by_oid = _indexes_by_relation(snapshot)
    candidates = []
    for group in _fk_groups(snapshot):
        child_oid = group["child_relation_oid"]
        relation = relations_by_oid.get(child_oid)
        if relation is None:
            continue
        columns = group["columns"]
        if _has_covering_index(indexes_by_oid.get(child_oid, []), columns):
            continue
        schema = _text(relation.get("schema_name"), "public")
        table = _text(relation.get("relation_name"), "unknown")
        index_name = _index_name(table, columns)
        columns_sql = ", ".join(_q(column) for column in columns)
        candidates.append(
            {
                "index_name": index_name,
                "schema_name": schema,
                "table_name": table,
                "columns": columns,
                "reason": (f"foreign-key lookup support for {group['constraint']}"),
                "ddl": (
                    f"CREATE INDEX CONCURRENTLY {_q(index_name)} "
                    f"ON {_qname(schema, table)} USING btree ({columns_sql});"
                ),
            }
        )
    return candidates


def _workload_observations(snapshot: dict) -> list[object]:
    observations = []
    for key in (
        "explain_analyze",
        "explain_results",
        "query_plans",
        "workload_observations",
    ):
        value = snapshot.get(key)
        if isinstance(value, list):
            observations.extend(value)
        elif isinstance(value, (str, dict)):
            observations.append(value)
    return observations


def _compact_index_design_summary(snapshot: dict) -> dict:
    relations_by_oid, _ = _relation_maps(snapshot)
    columns_by_oid = _columns_by_relation(snapshot)
    indexes_by_oid = _indexes_by_relation(snapshot)
    citus_by_oid = _citus_by_relation(snapshot)

    tables = []
    for oid, relation in sorted(
        relations_by_oid.items(), key=lambda item: _relation_label(item[1])
    ):
        if relation.get("relation_kind") not in ("r", "p"):
            continue
        tables.append(
            {
                "name": _relation_label(relation),
                "columns": [
                    {
                        "name": column.get("column_name"),
                        "type": column.get("data_type"),
                        "not_null": column.get("is_not_null") is True,
                    }
                    for column in columns_by_oid.get(oid, [])
                ],
                "indexes": [
                    {
                        "name": index.get("index_name"),
                        "method": index.get("access_method"),
                        "unique": index.get("is_unique") is True,
                        "primary": index.get("is_primary") is True,
                        "predicate": index.get("predicate_expr"),
                    }
                    for index in indexes_by_oid.get(oid, [])
                ],
                "citus": citus_by_oid.get(oid),
            }
        )

    return {
        "source_dialect": snapshot.get("source_dialect")
        or snapshot.get("database_dialect")
        or "postgresql",
        "server_version": snapshot.get("server_version"),
        "captured_at": snapshot.get("captured_at"),
        "tables": tables,
        "candidate_indexes": _candidate_indexes(snapshot),
        "workload_observations": _workload_observations(snapshot),
        "valkey_queue": valkey_queue_config_summary(),
    }


def generate_index_design_llm_prompt(snapshot: dict) -> str:
    """Build a prompt for LLM-assisted table and index design."""

    summary = _compact_index_design_summary(snapshot)
    payload = json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True)
    return "\n".join(
        [
            "# ERD Index Design Prompt",
            "",
            "You are a senior PostgreSQL data architect. Review the supplied",
            "ERD snapshot, current indexes, optional EXPLAIN ANALYZE evidence,",
            "Citus distribution metadata, and queue configuration. Propose table",
            "and index changes only when supported by the snapshot or workload",
            "evidence. Use CREATE INDEX CONCURRENTLY for PostgreSQL index DDL",
            "and call out when Valkey queueing should be used for asynchronous",
            "index work. Do not invent application behavior.",
            "",
            "Return Markdown with these sections:",
            "- Workload assumptions",
            "- Table design adjustments",
            "- Index recommendations",
            "- Citus placement considerations",
            "- Valkey queue execution plan",
            "- SQL migration draft",
            "",
            "Snapshot summary:",
            "```json",
            payload,
            "```",
            "",
        ]
    )


def _append_valkey_queue_section(lines: list[str], summary: dict) -> None:
    valkey = summary.get("valkey_queue")
    if isinstance(valkey, dict):
        lines.extend(
            [
                f"- Enabled: {'yes' if valkey.get('enabled') is True else 'no'}",
                f"- Mode: {_escape_cell(valkey.get('mode'))}",
                f"- Queue key: {_escape_cell(valkey.get('queue_key'))}",
                f"- Sentinel master: {_escape_cell(valkey.get('sentinel_master'))}",
                f"- Sentinel count: {_escape_cell(valkey.get('sentinel_count'))}",
            ]
        )


def _append_index_recommendations_section(lines: list[str], summary: dict) -> None:
    candidates = [
        item for item in summary.get("candidate_indexes", []) if isinstance(item, dict)
    ]
    lines.extend(["", "## Index Recommendations"])
    if not candidates:
        lines.append("_No missing foreign-key helper indexes were detected._")
    for candidate in candidates:
        lines.extend(
            [
                "",
                f"### {_escape_cell(candidate.get('index_name'))}",
                f"- Table: {_escape_cell(candidate.get('schema_name'))}.{_escape_cell(candidate.get('table_name'))}",
                f"- Columns: {_escape_cell(', '.join(candidate.get('columns', [])))}",
                f"- Reason: {_escape_cell(candidate.get('reason'))}",
                "",
                "```sql",
                _text(candidate.get("ddl")),
                "```",
            ]
        )


def _append_citus_placement_section(lines: list[str], snapshot: dict) -> None:
    lines.extend(["", "## Citus Placement"])
    citus_rows = _rows(snapshot, "citus_distributed_tables")
    if not citus_rows:
        lines.append("_No Citus distributed table metadata was captured._")
    else:
        lines.extend(
            [
                "| Table | Method | Key | Colocation | Shards | Replicas |",
                "| --- | --- | --- | --- | --- | --- |",
            ]
        )
        for row in citus_rows:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _escape_cell(_relation_label(row)),
                        _escape_cell(row.get("distribution_method")),
                        _escape_cell(row.get("distribution_key")),
                        _escape_cell(row.get("colocation_id")),
                        _escape_cell(row.get("shard_count")),
                        _escape_cell(row.get("replication_factor")),
                    ]
                )
                + " |"
            )


def _append_explain_analyze_evidence_section(lines: list[str], summary: dict) -> None:
    observations = summary.get("workload_observations", [])
    lines.extend(["", "## EXPLAIN ANALYZE Evidence"])
    if not observations:
        lines.append(
            "_No EXPLAIN ANALYZE or workload observations were embedded in this snapshot._"
        )
    else:
        lines.append("```json")
        lines.append(json.dumps(observations, ensure_ascii=False, indent=2))
        lines.append("```")


def generate_index_design_markdown(snapshot: dict) -> str:
    """Generate deterministic index-design guidance from snapshot metadata."""

    summary = _compact_index_design_summary(snapshot)
    lines: list[str] = [
        "# ERD Index Design",
        "",
        "## Snapshot",
        f"- Source dialect: {_text(summary.get('source_dialect'), 'postgresql')}",
        f"- Server version: {_text(summary.get('server_version'), '-') or '-'}",
        f"- Captured at: {_text(summary.get('captured_at'), '-') or '-'}",
        "",
        "## Valkey Queue",
    ]

    _append_valkey_queue_section(lines, summary)
    _append_index_recommendations_section(lines, summary)
    _append_citus_placement_section(lines, snapshot)
    _append_explain_analyze_evidence_section(lines, summary)

    lines.extend(
        [
            "",
            "## LLM Review Prompt",
            "Use `/index-design.md?mode=llm-prompt` to generate a compact prompt",
            "for an approved LLM provider. When a provider is configured,",
            "`/index-design.md?mode=llm-draft` asks the provider to generate",
            "a Markdown table/index design directly.",
            "",
        ]
    )
    return "\n".join(lines)


def generate_index_design_spec(snapshot: dict, mode: str = "markdown") -> str:
    """Generate an index-design document or LLM prompt from a snapshot."""
    if mode == "llm-prompt":
        return generate_index_design_llm_prompt(snapshot)
    if mode == "markdown":
        return generate_index_design_markdown(snapshot)
    raise ValueError(f"unsupported index design spec mode: {mode}")
