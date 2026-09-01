"""Catalog-evidence normalization and functional-dependency assessment.

The analyzer is intentionally conservative. It reports catalog-visible
preconditions for normalization review, but it never certifies a relation as
BCNF merely because no warning is visible: undeclared functional dependencies
cannot be disproved from keys, nullability, and column types alone.

The function is pure and consumes the common introspection snapshot used by the
PostgreSQL, MySQL, and Snowflake adapters. Provider-specific representations
must be normalized at the adapter boundary rather than leaking into domain
interpretation where practical.

References (APA 7th):

Codd, E. F. (1972). Further normalization of the data base relational model.
In R. Rustin (Ed.), *Data base systems* (pp. 33-64). Prentice-Hall.

Date, C. J. (2019). *Database design and relational theory: Normal forms and
all that jazz* (2nd ed.). Apress. https://doi.org/10.1007/978-1-4842-5540-7
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable

#: Report contract version. Bump on any breaking change to the output shape.
ASSESSMENT_VERSION = "1"

#: The evidence classes a finding may carry.
EVIDENCE_CLASSES = ("observed", "declared", "inferred", "proposed", "waived")

#: Relation kinds worth assessing for normalization. Views are derived objects.
_ASSESSABLE_RELATION_KINDS = frozenset({"r", "p", ""})
_CONTYPE_UNIQUE = "u"
_WAIVER_SCOPE_KEYS = frozenset({"schema", "relation", "kind"})


def _norm_type(data_type: object) -> str:
    """Normalize a SQL type name for comparison (drop length/precision)."""

    text = str(data_type or "").strip().lower()
    text = re.sub(r"\(.*?\)", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _is_non_atomic(column: dict[str, Any]) -> tuple[bool, str]:
    """Return whether a catalog type is a nested/repeating value and confidence."""

    normalized = _norm_type(column.get("data_type"))
    category = str(column.get("type_category") or "")
    try:
        dimensions = int(column.get("array_dimensions") or 0)
    except (TypeError, ValueError):
        dimensions = 0
    if (
        category == "A"
        or dimensions > 0
        or normalized.endswith("[]")
        or normalized == "array"
    ):
        return True, "high"
    if normalized in {"json", "jsonb"}:
        return True, "medium"
    return False, "high"


def _relation_ref(relation: dict[str, Any]) -> dict[str, Any]:
    """Build the report reference for a relation."""

    return {
        "schema": relation.get("schema_name"),
        "name": relation.get("relation_name"),
        "oid": relation.get("relation_oid"),
    }


def _finding_id(
    relation: dict[str, Any], kind: str, source_names: Iterable[str]
) -> str:
    """Derive an id stable across relation OID churn for the same logical object."""

    payload = "|".join(
        [
            str(relation.get("schema_name") or ""),
            str(relation.get("relation_name") or ""),
            kind,
            ",".join(sorted(str(name) for name in source_names)),
        ]
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def _waiver_matches(
    waiver: dict[str, Any], relation: dict[str, Any], kind: str
) -> bool:
    """Match only a non-empty, explicitly supported waiver scope."""

    raw_scope = waiver.get("scope")
    if not isinstance(raw_scope, dict) or not raw_scope:
        return False
    if not set(raw_scope).issubset(_WAIVER_SCOPE_KEYS):
        return False
    if "kind" in raw_scope and raw_scope.get("kind") != kind:
        return False
    if "schema" in raw_scope and raw_scope.get("schema") != relation.get(
        "schema_name"
    ):
        return False
    if "relation" in raw_scope and raw_scope.get("relation") != relation.get(
        "relation_name"
    ):
        return False
    return True


def _apply_waivers(
    finding: dict[str, Any],
    relation: dict[str, Any],
    kind: str,
    waivers: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return a copy marked waived when a caller-supplied scope matches."""

    for waiver in waivers:
        if _waiver_matches(waiver, relation, kind):
            waived = dict(finding)
            waived["evidence_class"] = "waived"
            waived["waiver"] = {
                "owner": waiver.get("owner"),
                "reason": waiver.get("reason"),
                "review_date": waiver.get("review_date"),
                "expiry": waiver.get("expiry"),
            }
            return waived
    return finding


def _minimal_candidate_keys(keys: list[list[str]]) -> list[list[str]]:
    """Return deterministic minimal declared keys, excluding strict superkeys."""

    unique_keys: list[list[str]] = []
    for key in keys:
        normalized = sorted(dict.fromkeys(key))
        if normalized and normalized not in unique_keys:
            unique_keys.append(normalized)
    minimal = [
        key
        for key in unique_keys
        if not any(set(other) < set(key) for other in unique_keys)
    ]
    return sorted(minimal, key=lambda key: (len(key), key))


def _declared_uniques(
    constraints: list[dict[str, Any]],
    attname_by_oid_pos: dict[Any, dict[int, str]],
) -> dict[Any, list[dict[str, Any]]]:
    """Resolve common-snapshot UNIQUE constraint attnums to column names."""

    unique_by_oid: dict[Any, list[dict[str, Any]]] = {}
    for constraint in constraints:
        if str(constraint.get("constraint_type")) != _CONTYPE_UNIQUE:
            continue
        oid = constraint.get("relation_oid")
        pos_map = attname_by_oid_pos.get(oid, {})
        names: list[str] = []
        for attnum in constraint.get("constrained_attnums") or []:
            try:
                resolved_name = pos_map.get(int(attnum))
            except (TypeError, ValueError):
                resolved_name = None
            if resolved_name is None:
                names = []
                break
            names.append(resolved_name)
        if names:
            unique_by_oid.setdefault(oid, []).append(
                {"name": constraint.get("constraint_name"), "columns": names}
            )
    return unique_by_oid


def assess_normalization(
    snapshot: dict[str, Any] | None,
    *,
    waivers: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Assess catalog-visible normalization evidence for every base relation.

    The result distinguishes observations and declared constraints from inferred
    review preconditions. A relation with no active finding is labelled
    ``catalog_reviewed`` rather than a normal-form certification because
    undeclared functional dependencies remain outside the evidence boundary.
    """

    snapshot = snapshot or {}
    waivers = list(waivers or [])
    relations: list[dict[str, Any]] = list(snapshot.get("relations") or [])
    columns: list[dict[str, Any]] = list(snapshot.get("columns") or [])
    pk_columns: list[dict[str, Any]] = list(snapshot.get("pk_columns") or [])
    constraints: list[dict[str, Any]] = list(snapshot.get("constraints") or [])
    fk_edges: list[dict[str, Any]] = list(snapshot.get("fk_edges") or [])

    cols_by_oid: dict[Any, list[dict[str, Any]]] = {}
    attname_by_oid_pos: dict[Any, dict[int, str]] = {}
    for column in columns:
        oid = column.get("relation_oid")
        name = column.get("column_name")
        if name is None:
            continue
        cols_by_oid.setdefault(oid, []).append(column)
        position = column.get("column_position")
        if position is not None:
            try:
                attname_by_oid_pos.setdefault(oid, {})[int(position)] = str(name)
            except (TypeError, ValueError):
                pass

    pk_by_oid: dict[Any, list[str]] = {}
    for pk in pk_columns:
        name = pk.get("column_name")
        if name is not None:
            pk_by_oid.setdefault(pk.get("relation_oid"), []).append(str(name))

    unique_by_oid = _declared_uniques(constraints, attname_by_oid_pos)

    fk_child_cols_by_oid: dict[Any, set[str]] = {}
    for edge in fk_edges:
        child = edge.get("child_column_name")
        if child is not None:
            fk_child_cols_by_oid.setdefault(edge.get("child_relation_oid"), set()).add(
                str(child)
            )

    relation_assessments: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []

    for relation in relations:
        relation_kind = str(relation.get("relation_kind") or "")
        if relation_kind not in _ASSESSABLE_RELATION_KINDS:
            continue
        oid = relation.get("relation_oid")
        relation_columns = cols_by_oid.get(oid, [])
        if not relation_columns:
            continue

        not_null = {
            str(column.get("column_name")): bool(column.get("is_not_null"))
            for column in relation_columns
            if column.get("column_name") is not None
        }
        all_column_names = list(not_null)

        declared_keys: list[list[str]] = []
        pk_cols = pk_by_oid.get(oid, [])
        if pk_cols:
            declared_keys.append(pk_cols)
        nullable_unique_determinants: list[dict[str, Any]] = []
        for unique in unique_by_oid.get(oid, []):
            unique_columns = list(unique["columns"])
            if all(not_null.get(name, False) for name in unique_columns):
                declared_keys.append(unique_columns)
            else:
                nullable_unique_determinants.append(unique)

        candidate_keys = _minimal_candidate_keys(declared_keys)
        prime_columns = sorted({column for key in candidate_keys for column in key})
        non_prime_columns = sorted(set(all_column_names) - set(prime_columns))
        relation_findings: list[dict[str, Any]] = []

        for column in relation_columns:
            name = column.get("column_name")
            if name is None:
                continue
            non_atomic, confidence = _is_non_atomic(column)
            if not non_atomic:
                continue
            finding_kind = "non_atomic_column"
            finding = {
                "finding_id": _finding_id(relation, finding_kind, [str(name)]),
                "relation": _relation_ref(relation),
                "kind": finding_kind,
                "normal_form_scope": "1NF",
                "evidence_class": "observed",
                "confidence": confidence,
                "rationale": (
                    f"Column {name!r} has type {_norm_type(column.get('data_type'))!r}, "
                    "which stores a repeating group or nested document in one cell."
                ),
                "false_positive_caveat": (
                    "Array and JSON columns can be deliberate evidence envelopes, "
                    "audit payloads, or document values; confirm domain intent first."
                ),
                "source_objects": [{"type": "column", "name": name}],
                "next_action": (
                    "Confirm whether the value is a repeating group that belongs in "
                    "a child relation, or record a scoped waiver for the deliberate "
                    "nested value."
                ),
            }
            relation_findings.append(
                _apply_waivers(finding, relation, finding_kind, waivers)
            )

        if not candidate_keys:
            finding_kind = "missing_candidate_key"
            finding = {
                "finding_id": _finding_id(
                    relation, finding_kind, all_column_names
                ),
                "relation": _relation_ref(relation),
                "kind": finding_kind,
                "normal_form_scope": "BCNF",
                "evidence_class": "inferred",
                "confidence": "high",
                "rationale": (
                    "No primary key or total declared UNIQUE key is visible, so "
                    "normal-form assessment lacks a catalog-visible candidate key."
                ),
                "false_positive_caveat": (
                    "A natural key may exist in the domain but remain undeclared."
                ),
                "source_objects": [
                    {"type": "relation", "name": relation.get("relation_name")}
                ],
                "next_action": (
                    "Declare the candidate key, or supply evidence of the domain key "
                    "before drawing normalization conclusions."
                ),
            }
            relation_findings.append(
                _apply_waivers(finding, relation, finding_kind, waivers)
            )

        for unique in nullable_unique_determinants:
            finding_kind = "nullable_unique_determinant"
            unique_columns = list(unique["columns"])
            finding = {
                "finding_id": _finding_id(
                    relation, finding_kind, unique_columns
                ),
                "relation": _relation_ref(relation),
                "kind": finding_kind,
                "normal_form_scope": "BCNF",
                "evidence_class": "declared",
                "confidence": "medium",
                "rationale": (
                    f"UNIQUE constraint {unique.get('name')!r} covers "
                    f"{', '.join(unique_columns)}, with at least one nullable "
                    "column, so it is not treated as a total candidate key."
                ),
                "false_positive_caveat": (
                    "Nullable uniqueness can be intentional and SQL dialects differ "
                    "in null-distinctness details."
                ),
                "source_objects": [
                    {"type": "constraint", "name": unique.get("name")},
                    *[
                        {"type": "column", "name": column}
                        for column in unique_columns
                    ],
                ],
                "next_action": (
                    "If the determinant is intended as a total key, make its columns "
                    "non-null and verify dialect semantics; otherwise document intent."
                ),
            }
            relation_findings.append(
                _apply_waivers(finding, relation, finding_kind, waivers)
            )

        has_composite_key = any(len(key) >= 2 for key in candidate_keys)
        if has_composite_key and non_prime_columns:
            finding_kind = "partial_dependency_precondition"
            finding = {
                "finding_id": _finding_id(
                    relation, finding_kind, non_prime_columns
                ),
                "relation": _relation_ref(relation),
                "kind": finding_kind,
                "normal_form_scope": "2NF",
                "evidence_class": "inferred",
                "confidence": "low",
                "rationale": (
                    "At least one candidate key is composite and the relation has "
                    f"non-prime column(s) ({', '.join(non_prime_columns)}). This is "
                    "a structural precondition for a partial dependency, not proof "
                    "that one exists."
                ),
                "false_positive_caveat": (
                    "Many relations with composite candidate keys are fully normalized."
                ),
                "source_objects": [
                    {"type": "column", "name": column}
                    for column in non_prime_columns
                ],
                "next_action": (
                    "Profile or declare functional dependencies to determine whether "
                    "a non-prime attribute depends on a proper subset of a composite key."
                ),
            }
            relation_findings.append(
                _apply_waivers(finding, relation, finding_kind, waivers)
            )

        active_kinds = {
            finding["kind"]
            for finding in relation_findings
            if finding["evidence_class"] != "waived"
        }
        if "missing_candidate_key" in active_kinds:
            normal_form = "insufficient_evidence"
            nf_evidence = "inferred"
        elif "non_atomic_column" in active_kinds:
            normal_form = "1nf_review"
            nf_evidence = "observed"
        elif "partial_dependency_precondition" in active_kinds:
            normal_form = "2nf_review"
            nf_evidence = "inferred"
        elif "nullable_unique_determinant" in active_kinds:
            normal_form = "bcnf_review"
            nf_evidence = "declared"
        else:
            normal_form = "catalog_reviewed"
            nf_evidence = "inferred"

        relation_assessments.append(
            {
                "relation": _relation_ref(relation),
                "candidate_keys": candidate_keys,
                "prime_columns": prime_columns,
                "non_prime_columns": non_prime_columns,
                "foreign_key_columns": sorted(fk_child_cols_by_oid.get(oid, set())),
                "normal_form": normal_form,
                "evidence_class": nf_evidence,
                "rationale": (
                    "Label is derived only from catalog-visible keys, nullability, "
                    "and column types; absence of a finding does not prove BCNF "
                    "because undeclared functional dependencies remain unknown."
                ),
            }
        )
        findings.extend(relation_findings)

    findings.sort(
        key=lambda finding: (
            str(finding["relation"].get("schema") or ""),
            str(finding["relation"].get("name") or ""),
            finding["normal_form_scope"],
            finding["kind"],
            finding["finding_id"],
        )
    )
    relation_assessments.sort(
        key=lambda assessment: (
            str(assessment["relation"].get("schema") or ""),
            str(assessment["relation"].get("name") or ""),
        )
    )

    return {
        "version": ASSESSMENT_VERSION,
        "evidence_basis": "catalog_only",
        "relation_assessments": relation_assessments,
        "findings": findings,
    }
