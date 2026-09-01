"""Accessible exact-value HTML rendering for the schema-quality assessments.

Both the normalization report (:mod:`app.spec.normalization_report`) and the
hot-partition report (:mod:`app.spec.hot_partition_report`) share the same
envelope shape (``summary`` + ``relation_assessments`` + ``findings``), so one
renderer serves both.

Design constraints (issue #947):

* **Exact values** -- every cell is the literal value from the report, HTML
  escaped with :func:`html.escape` (``quote=True``); nothing is rounded or
  abbreviated.
* **Not colour-only** -- evidence class and risk are shown as text labels
  (``[declared]``, ``risk: review``), never as colour alone.
* **Self-contained** -- one fragment with a scoped inline ``<style>``; no
  external CSS/JS, no scripts, safe to embed.
* **Semantic** -- ``<table>`` with ``<caption>`` and ``<th scope>`` per
  section so screen readers can navigate it.
"""

from __future__ import annotations

import html
from typing import Any

_STYLE = (
    ".cwl-assessment{font:14px/1.5 system-ui,sans-serif;color:#1a1a1a;max-width:70rem}"
    ".cwl-assessment table{border-collapse:collapse;width:100%;margin:0 0 1.5rem}"
    ".cwl-assessment caption{text-align:left;font-weight:600;margin:1rem 0 .35rem}"
    ".cwl-assessment th,.cwl-assessment td{border:1px solid #c9c9c9;padding:.35rem .5rem;"
    "text-align:left;vertical-align:top}"
    ".cwl-assessment th[scope=row]{font-weight:600;white-space:nowrap}"
    ".cwl-assessment .cwl-tag{font-weight:600}"
)


def _esc(value: object) -> str:
    """HTML-escape any value (``None`` -> empty string), quotes included."""

    return "" if value is None else html.escape(str(value), quote=True)


def _summary_section(summary: dict[str, Any]) -> str:
    """Render the buyer-facing summary block."""

    rows = "".join(
        f"<tr><th scope='row'>{_esc(key)}</th><td>{_esc(value)}</td></tr>"
        for key, value in summary.items()
        if not isinstance(value, dict)
    )
    breakdowns = ""
    for key, value in summary.items():
        if isinstance(value, dict):
            inner = "".join(
                f"<tr><th scope='row'>{_esc(k)}</th><td>{_esc(v)}</td></tr>"
                for k, v in value.items()
            ) or "<tr><td colspan='2'>(none)</td></tr>"
            breakdowns += (
                f"<table><caption>{_esc(key)}</caption>"
                f"<thead><tr><th scope='col'>key</th><th scope='col'>count</th></tr></thead>"
                f"<tbody>{inner}</tbody></table>"
            )
    return (
        f"<table><caption>Summary</caption><tbody>{rows}</tbody></table>{breakdowns}"
    )


def _relation_section(relation_assessments: list[dict[str, Any]]) -> str:
    """Render the per-relation assessment table."""

    if not relation_assessments:
        return "<p>No base relations were assessed.</p>"
    body = ""
    for record in relation_assessments:
        relation = record.get("relation") or {}
        extra_cells = "".join(
            f"<td>{_esc(', '.join(map(str, v)) if isinstance(v, list) else v)}</td>"
            for k, v in record.items()
            if k != "relation"
        )
        headers = [k for k in record if k != "relation"]
        if not body:
            head = "".join(
                f"<th scope='col'>{_esc(h)}</th>" for h in ["schema", "relation", *headers]
            )
        body += (
            "<tr>"
            f"<th scope='row'>{_esc(relation.get('schema'))}</th>"
            f"<td>{_esc(relation.get('name'))}</td>"
            f"{extra_cells}</tr>"
        )
    return (
        "<table><caption>Relations</caption>"
        f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"
    )


def _findings_section(findings: list[dict[str, Any]]) -> str:
    """Render one table per finding kind, ordered by kind."""

    if not findings:
        return "<p>No findings.</p>"
    by_kind: dict[str, list[dict[str, Any]]] = {}
    for finding in findings:
        by_kind.setdefault(str(finding.get("kind")), []).append(finding)

    sections = ""
    for kind in sorted(by_kind):
        rows = ""
        for finding in by_kind[kind]:
            relation = finding.get("relation") or {}
            sources = ", ".join(
                str(o.get("name"))
                for o in (finding.get("source_objects") or [])
                if o.get("name") is not None
            )
            rows += (
                "<tr>"
                f"<th scope='row'>{_esc(relation.get('schema'))}.{_esc(relation.get('name'))}</th>"
                f"<td><span class='cwl-tag'>[{_esc(finding.get('evidence_class'))}]</span> "
                f"{_esc(finding.get('confidence'))}</td>"
                f"<td>{_esc(finding.get('normal_form_scope') or finding.get('scope') or '')}</td>"
                f"<td>{_esc(finding.get('rationale'))}</td>"
                f"<td>{_esc(sources)}</td>"
                f"<td>{_esc(finding.get('next_action'))}</td>"
                f"<td>{_esc(finding.get('false_positive_caveat') or finding.get('caveat'))}</td>"
                "</tr>"
            )
        sections += (
            f"<table><caption>{_esc(kind)} ({len(by_kind[kind])})</caption>"
            "<thead><tr>"
            "<th scope='col'>relation</th><th scope='col'>evidence / confidence</th>"
            "<th scope='col'>scope</th><th scope='col'>rationale</th>"
            "<th scope='col'>source objects</th><th scope='col'>next action</th>"
            "<th scope='col'>caveat</th>"
            "</tr></thead>"
            f"<tbody>{rows}</tbody></table>"
        )
    return sections


def render_assessment_html(report: dict[str, Any] | None, *, title: str) -> str:
    """Render a schema-quality assessment report as an accessible HTML fragment.

    Args:
        report: A report envelope from ``build_normalization_report`` or
            ``build_hot_partition_report`` (``summary`` + ``relation_assessments``
            + ``findings`` plus envelope metadata). ``None`` renders an empty
            report.
        title: Heading text for the fragment (already trusted; still escaped).

    Returns:
        A single ``<div class="cwl-assessment">`` fragment with a scoped inline
        ``<style>``. Every data value is HTML-escaped. No scripts, no external
        resources.
    """

    report = report or {}
    meta_rows = "".join(
        f"<tr><th scope='row'>{_esc(k)}</th><td>{_esc(v)}</td></tr>"
        for k, v in report.items()
        if k not in {"summary", "relation_assessments", "findings"}
        and not isinstance(v, (dict, list))
    )
    return (
        f"<div class='cwl-assessment'><style>{_STYLE}</style>"
        f"<h1>{_esc(title)}</h1>"
        f"<table><caption>Report</caption><tbody>{meta_rows}</tbody></table>"
        f"{_summary_section(report.get('summary') or {})}"
        f"{_relation_section(list(report.get('relation_assessments') or []))}"
        f"<h2>Findings</h2>{_findings_section(list(report.get('findings') or []))}"
        "</div>"
    )
