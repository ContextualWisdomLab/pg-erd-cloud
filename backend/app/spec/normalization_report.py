"""Versioned report envelope for the normalization assessment.

:mod:`app.spec.normalization_assessment` produces the catalog-evidence
findings. This module wraps them in the buyer-facing report envelope required
by issue #947: a stable schema fingerprint, a generation timestamp, and a
plain-language summary an architect can read without opening the JSON.

The envelope is additive -- every key from :func:`assess_normalization` is
preserved -- so downstream consumers can ignore the envelope and read
``findings`` / ``relation_assessments`` directly.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from typing import Any

from app.spec.normalization_assessment import assess_normalization

#: Report envelope contract version. Distinct from the analyzer's own
#: ``version``; bump when the envelope shape changes.
REPORT_VERSION = "1"


def schema_fingerprint(snapshot: dict[str, Any] | None) -> str:
    """Return a stable SHA-256 fingerprint of a schema snapshot.

    The snapshot is serialized with sorted keys and a string fallback for
    non-JSON values so the same schema always yields the same fingerprint
    regardless of dict ordering.
    """

    canonical = json.dumps(snapshot or {}, sort_keys=True, default=str, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _summarize(assessment: dict[str, Any]) -> dict[str, Any]:
    """Build the plain-language summary block from an analyzer result."""

    by_normal_form: dict[str, int] = {}
    for record in assessment.get("relation_assessments", []):
        label = str(record.get("normal_form"))
        by_normal_form[label] = by_normal_form.get(label, 0) + 1

    by_evidence_class: dict[str, int] = {}
    for finding in assessment.get("findings", []):
        cls = str(finding.get("evidence_class"))
        by_evidence_class[cls] = by_evidence_class.get(cls, 0) + 1

    relations_assessed = len(assessment.get("relation_assessments", []))
    needs_review = sum(
        count
        for label, count in by_normal_form.items()
        if label not in {"bcnf"}
    )
    waived = by_evidence_class.get("waived", 0)

    if relations_assessed == 0:
        headline = "No base relations were available to assess."
    elif needs_review == 0:
        headline = (
            f"All {relations_assessed} assessed relation(s) are in BCNF by "
            "declared-key evidence"
            + (f" ({waived} finding(s) waived)" if waived else "")
            + ". Undeclared dependencies are not visible to this catalog-only "
            "check."
        )
    else:
        headline = (
            f"{needs_review} of {relations_assessed} assessed relation(s) need "
            "a normalization review; "
            f"{len(assessment.get('findings', []))} finding(s) total"
            + (f", {waived} waived." if waived else ".")
        )

    return {
        "relations_assessed": relations_assessed,
        "relations_needing_review": needs_review,
        "relations_by_normal_form": dict(sorted(by_normal_form.items())),
        "findings_by_evidence_class": dict(sorted(by_evidence_class.items())),
        "headline": headline,
    }


def build_normalization_report(
    snapshot: dict[str, Any] | None,
    *,
    waivers: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Assess ``snapshot`` and return the versioned report envelope.

    Args:
        snapshot: A schema snapshot in the common introspection JSON shape.
        waivers: Optional waiver records passed through to
            :func:`assess_normalization`.

    Returns:
        The analyzer result (``version``, ``evidence_basis``,
        ``relation_assessments``, ``findings``) plus:

        ``report_version``
            :data:`REPORT_VERSION`.
        ``generated_at``
            UTC ISO-8601 timestamp of this report.
        ``schema_fingerprint``
            Stable SHA-256 fingerprint of the snapshot.
        ``summary``
            A plain-language block: counts by normal form and evidence class
            plus a one-line ``headline`` for a buyer-facing view.

        The function performs no I/O and emits no DDL.
    """

    assessment = assess_normalization(snapshot, waivers=waivers)
    return {
        "report_version": REPORT_VERSION,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "schema_fingerprint": schema_fingerprint(snapshot),
        "summary": _summarize(assessment),
        **assessment,
    }
