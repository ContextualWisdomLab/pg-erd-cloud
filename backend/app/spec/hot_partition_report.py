"""Versioned report envelope for the hot-partition & growth assessment.

Wraps :func:`app.spec.hot_partition_assessment.assess_hot_partitions` with the
same buyer-facing envelope shape as :mod:`app.spec.normalization_report`: a
stable schema fingerprint, a generation timestamp, and a plain-language
summary. The envelope is additive.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from app.spec.hot_partition_assessment import assess_hot_partitions
from app.spec.normalization_report import schema_fingerprint

#: Report envelope contract version.
REPORT_VERSION = "1"


def _summarize(assessment: dict[str, Any]) -> dict[str, Any]:
    """Build the plain-language summary block from an analyzer result."""

    relations_assessed = len(assessment.get("relation_assessments", []))
    relations_at_risk = sum(
        1
        for record in assessment.get("relation_assessments", [])
        if record.get("risk") == "review"
    )

    findings_by_kind: dict[str, int] = {}
    findings_by_evidence_class: dict[str, int] = {}
    for finding in assessment.get("findings", []):
        kind = str(finding.get("kind"))
        cls = str(finding.get("evidence_class"))
        findings_by_kind[kind] = findings_by_kind.get(kind, 0) + 1
        findings_by_evidence_class[cls] = findings_by_evidence_class.get(cls, 0) + 1

    if relations_assessed == 0:
        headline = "No base relations were available to assess."
    elif relations_at_risk == 0:
        headline = (
            f"None of the {relations_assessed} assessed relation(s) show a "
            "catalog-visible hot-partition or unbounded-growth signal."
        )
    else:
        headline = (
            f"{relations_at_risk} of {relations_assessed} assessed relation(s) "
            "have a hot-partition or growth signal to review; "
            f"{len(assessment.get('findings', []))} finding(s) total"
            + (
                " (capacity profile applied)."
                if assessment.get("capacity_profile_applied")
                else " (no capacity profile supplied — findings stay advisory)."
            )
        )

    return {
        "relations_assessed": relations_assessed,
        "relations_at_risk": relations_at_risk,
        "findings_by_kind": dict(sorted(findings_by_kind.items())),
        "findings_by_evidence_class": dict(sorted(findings_by_evidence_class.items())),
        "headline": headline,
    }


def build_hot_partition_report(
    snapshot: dict[str, Any] | None,
    *,
    capacity_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assess ``snapshot`` and return the versioned report envelope.

    Args:
        snapshot: A schema snapshot in the common introspection JSON shape.
        capacity_profile: Optional explicit workload expectations passed
            through to :func:`assess_hot_partitions`.

    Returns:
        The analyzer result plus ``report_version`` (:data:`REPORT_VERSION`),
        ``generated_at`` (UTC ISO-8601), ``schema_fingerprint`` (stable
        SHA-256 of the snapshot), and a ``summary`` block with counts and a
        one-line buyer-facing ``headline``. No I/O, no DDL.
    """

    assessment = assess_hot_partitions(snapshot, capacity_profile=capacity_profile)
    return {
        "report_version": REPORT_VERSION,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "schema_fingerprint": schema_fingerprint(snapshot),
        "summary": _summarize(assessment),
        **assessment,
    }
