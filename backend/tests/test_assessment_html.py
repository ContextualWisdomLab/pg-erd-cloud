"""Tests for :mod:`app.spec.assessment_html`."""

from __future__ import annotations

from typing import Any

from app.spec.assessment_html import render_assessment_html
from app.spec.hot_partition_report import build_hot_partition_report
from app.spec.normalization_report import build_normalization_report

_MALICIOUS_SNAPSHOT: dict[str, Any] = {
    "relations": [
        {
            "relation_oid": 1,
            "schema_name": "public",
            "relation_name": "<script>alert('x')</script>",
            "relation_kind": "r",
            "partition_key": None,
            "is_partition": False,
        }
    ],
    "columns": [
        {"relation_oid": 1, "column_position": 1, "column_name": "id", "data_type": "bigint", "is_not_null": True},
        {"relation_oid": 1, "column_position": 2, "column_name": "tags", "data_type": "text[]", "type_category": "A", "array_dimensions": 1},
    ],
    "pk_columns": [{"relation_oid": 1, "column_name": "id"}],
}


def test_every_value_is_html_escaped() -> None:
    report = build_normalization_report(_MALICIOUS_SNAPSHOT)
    out = render_assessment_html(report, title="Normalization assessment")
    assert "<script>alert('x')</script>" not in out
    assert "&lt;script&gt;alert(&#x27;x&#x27;)&lt;/script&gt;" in out
    # The wrapper and our own markup are still present.
    assert out.startswith("<div class='cwl-assessment'>")
    assert "<h1>Normalization assessment</h1>" in out


def test_state_is_shown_as_a_text_label_not_colour_only() -> None:
    report = build_normalization_report(_MALICIOUS_SNAPSHOT)
    out = render_assessment_html(report, title="t")
    # The malicious relation has a non_atomic_column finding (array column).
    assert "[observed]" in out
    assert "<caption>non_atomic_column (1)</caption>" in out


def test_hot_partition_report_renders_with_caveat_column() -> None:
    snap = {
        "relations": [
            {"relation_oid": 1, "schema_name": "public", "relation_name": "job_queue", "relation_kind": "r", "partition_key": None, "is_partition": False}
        ],
        "columns": [
            {"relation_oid": 1, "column_position": 1, "column_name": "job_id", "data_type": "bigint", "is_not_null": True, "has_default": True, "default_expr": "nextval('s'::regclass)"},
            {"relation_oid": 1, "column_position": 2, "column_name": "enqueued_at", "data_type": "timestamp with time zone", "is_not_null": True, "has_default": True, "default_expr": "now()"},
        ],
        "pk_columns": [{"relation_oid": 1, "column_name": "job_id"}],
    }
    out = render_assessment_html(build_hot_partition_report(snap), title="Hot-partition assessment")
    assert "<caption>append_heavy_table (1)</caption>" in out
    assert "job_queue" in out


def test_empty_report_renders_placeholders() -> None:
    out = render_assessment_html(build_normalization_report(None), title="t")
    assert "No findings." in out
    assert "No base relations were assessed." in out
    # None passes through as an empty report too.
    assert render_assessment_html(None, title="t").startswith("<div class='cwl-assessment'>")
