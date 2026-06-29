import re

with open('backend/app/spec/index_design.py', 'r') as f:
    content = f.read()

# We need to replace the `generate_index_design_markdown` function with the refactored version.
# Let's extract the part before `generate_index_design_markdown` and after it.

pattern = r"(def generate_index_design_markdown\(snapshot: dict\) -> str:.*?)(?=\n\n\ndef generate_index_design_spec)"

refactored_code = """def _append_valkey_queue_section(lines: list[str], summary: dict) -> None:
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
    \"\"\"Generate deterministic index-design guidance from snapshot metadata.\"\"\"

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
    return "\\n".join(lines)"""

new_content = re.sub(pattern, refactored_code, content, flags=re.DOTALL)

with open('backend/app/spec/index_design.py', 'w') as f:
    f.write(new_content)
