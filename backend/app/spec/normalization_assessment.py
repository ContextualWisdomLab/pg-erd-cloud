"""Catalog-evidence normalization and functional-dependency assessment.

Enterprise buyers routinely ask an architect three questions a generic ERD
drawer cannot answer:

1. Which relations appear to violate normalization or mix independent facts?
2. Which of those findings are certain, inferred, or intentionally excepted?
3. What is the customer's next action for each finding?

This module answers the first two from **catalog evidence only** -- declared
primary keys, ``UNIQUE`` constraints, ``NOT NULL`` flags, column types, and
declared foreign keys captured in the schema snapshot. It never profiles table
data, never asserts a normalization theorem from column *names* alone, and
never emits or executes DDL. Every finding carries an explicit evidence class
so a certain observation is never presented as an inferred guess (or the
reverse).

The analyzer is a pure, dialect-agnostic function over the common snapshot
JSON shape produced by :mod:`app.pg_introspect.introspect` (and the MySQL and
Snowflake introspectors), matching the other :mod:`app.spec` analyzers.

Evidence classes (see ``EVIDENCE_CLASSES``):

``observed``
    Directly visible in the catalog with no inference (e.g. an array column).
``declared``
    Proven from a declared constraint (e.g. a ``UNIQUE`` on a nullable column
    is not a total key).
``inferred``
    A structural precondition is present but the catalog cannot confirm an
    actual dependency; profiling or a declared rule is required.
``proposed``
    Reserved for a future increment that emits a concrete remediation.
``waived``
    A caller-supplied waiver matched this finding; it is recorded, not hidden.

What this increment deliberately does **not** do yet (tracked on issue #947):
transitive-dependency (3NF) detection that needs data profiling or declared
functional dependencies, signed/persisted waiver records, the hot-partition
and growth assessment, and the versioned report envelope with an HTTP
endpoint. Those land as separate bounded changes so each is reviewable.

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

#: The evidence classes a finding may carry, from most to least certain.
EVIDENCE_CLASSES = ("observed", "declared", "inferred", "proposed", "waived")

#: Relation kinds worth assessing for normalization. Views and materialized
#: views derive from base relations, so a finding there belongs on the source.
_ASSESSABLE_RELATION_KINDS = frozenset({"r", "p", ""})

#: PostgreSQL ``pg_constraint.contype`` codes used here.
_CONTYPE_PRIMARY_KEY = "p"
_CONTYPE_UNIQUE = "u"


def _norm_type(data_type: object) -> str:
    """Normalize a SQL type name for comparison (drop length/precision)."""

    text = str(data_type or "").strip().lower()
    text = re.sub(r"\(.*?\)", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _is_non_atomic(column: dict[str, Any]) -> tuple[bool, str]:
    """Return ``(non_atomic, confidence)`` for a column from catalog evidence.

    An array column is a repeating group with high confidence. A ``json`` or
    ``jsonb`` column *may* be a deliberate document/evidence envelope, so it is
    flagged with medium confidence and a false-positive caveat downstream.
    """

    normalized = _norm_type(column.get("data_type"))
    category = str(column.get("type_category") or "")
    try:
        dimensions = int(column.get("array_dimensions") or 0)
    except (TypeError, ValueError):
        dimensions = 0
    if category == "A" or dimensions > 0 or normalized.endswith("[]"):
        return True, "high"
    if normalized in {"json", "jsonb"}:
        return True, "medium"
    return False, "high"


def _relation_ref(relation: dict[str, Any]) -> dict[str, Any]:
    """Build the stable ``{schema, name, oid}`` reference for a relation."""

    return {
        "schema": relation.get("schema_name"),
        "name": relation.get("relation_name"),
        "oid": relation.get("relation_oid"),
    }


def _finding_id(relation_oid: object, kind: str, source_names: Iterable[str]) -> str:
    """Derive a deterministic short id for a finding (stable across runs)."""

    payload = "|".join(
        [str(relation_oid), kind, ",".join(sorted(str(n) for n in source_names))]
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def _waiver_matches(waiver: dict[str, Any], relation: dict[str, Any], kind: str) -> bool:
    """Return ``True`` when every field a waiver's ``scope`` sets matches."""

    scope = waiver.get("scope") or {}
    if "kind" in scope and scope.get("kind") != kind:
        return False
    if "schema" in scope and scope.get("schema") != relation.get("schema_name"):
        return False
    if "relation" in scope and scope.get("relation") != relation.get("relation_name"):
        return False
    # An empty scope would match everything, which is never a deliberate waiver.
    return bool(scope)


def _apply_waivers(
    finding: dict[str, Any],
    relation: dict[str, Any],
    kind: str,
    waivers: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return ``finding`` with evidence class flipped to ``waived`` if matched."""

    for waiver in waivers:
        if _waiver_matches(waiver, relation, kind):
            finding = dict(finding)
            finding["evidence_class"] = "waived"
            finding["waiver"] = {
                "owner": waiver.get("owner"),
                "reason": waiver.get("reason"),
                "review_date": waiver.get("review_date"),
                "expiry": waiver.get("expiry"),
            }
            return finding
    return finding


def assess_normalization(
    snapshot: dict[str, Any] | None,
    *,
    waivers: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Assess normalization for every base relation from catalog evidence.

    Args:
        snapshot: A schema snapshot in the common introspection JSON shape.
            ``None`` or missing keys are treated as an empty schema.
        waivers: Optional list of waiver records. Each is
            ``{"scope": {"schema"?, "relation"?, "kind"?}, "owner", "reason",
            "review_date", "expiry"}``. A finding whose relation and kind match
            every field the ``scope`` sets is recorded with evidence class
            ``waived`` and an attached ``waiver`` object rather than dropped.

    Returns:
        A dictionary with:

        ``version``
            :data:`ASSESSMENT_VERSION`.
        ``evidence_basis``
            Always ``"catalog_only"`` for this analyzer.
        ``relation_assessments``
            One record per assessed base relation with its catalog-derived
            candidate keys, prime/non-prime column split, a coarse
            ``normal_form`` label, and the evidence class of that label.
        ``findings``
            Zero or more finding records, each with a deterministic
            ``finding_id``, ``relation`` reference, ``kind``,
            ``normal_form_scope``, ``evidence_class``, ``confidence``,
            ``rationale``, ``false_positive_caveat``, ``source_objects``, and
            ``next_action``. Findings are sorted for stable output.

        The analyzer performs no I/O and emits no DDL.
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

    # Declared UNIQUE constraints, mapped from attnums to column names.
    unique_by_oid: dict[Any, list[dict[str, Any]]] = {}
    for constraint in constraints:
        if str(constraint.get("constraint_type")) != _CONTYPE_UNIQUE:
            continue
        oid = constraint.get("relation_oid")
        attnums = constraint.get("constrained_attnums") or []
        pos_map = attname_by_oid_pos.get(oid, {})
        names: list[str] = []
        resolved = True
        for attnum in attnums:
            try:
                resolved_name = pos_map.get(int(attnum))
            except (TypeError, ValueError):
                resolved_name = None
            if resolved_name is None:
                resolved = False
                break
            names.append(resolved_name)
        if resolved and names:
            unique_by_oid.setdefault(oid, []).append(
                {"name": constraint.get("constraint_name"), "columns": names}
            )

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
        kind = str(relation.get("relation_kind") or "")
        if kind not in _ASSESSABLE_RELATION_KINDS:
            continue
        oid = relation.get("relation_oid")
        relation_columns = cols_by_oid.get(oid, [])
        if not relation_columns:
            continue

        not_null: dict[str, bool] = {
            str(c.get("column_name")): bool(c.get("is_not_null"))
            for c in relation_columns
            if c.get("column_name") is not None
        }
        all_column_names = list(not_null.keys())

        # Candidate keys from declared evidence: the PK, plus every UNIQUE whose
        # columns are all NOT NULL (a UNIQUE with a nullable column is not a
        # total key in PostgreSQL, where NULLs are distinct).
        candidate_keys: list[list[str]] = []
        pk_cols = pk_by_oid.get(oid, [])
        if pk_cols:
            candidate_keys.append(sorted(pk_cols))
        nullable_unique_determinants: list[dict[str, Any]] = []
        for unique in unique_by_oid.get(oid, []):
            unique_columns = unique["columns"]
            if all(not_null.get(name, False) for name in unique_columns):
                key = sorted(unique_columns)
                if key not in candidate_keys:
                    candidate_keys.append(key)
            else:
                nullable_unique_determinants.append(unique)

        prime_columns = sorted({c for key in candidate_keys for c in key})
        non_prime_columns = sorted(set(all_column_names) - set(prime_columns))

        relation_findings: list[dict[str, Any]] = []

        # --- 1NF: non-atomic columns -------------------------------------
        for column in relation_columns:
            name = column.get("column_name")
            if name is None:
                continue
            non_atomic, confidence = _is_non_atomic(column)
            if not non_atomic:
                continue
            kind_key = "non_atomic_column"
            finding = {
                "finding_id": _finding_id(oid, kind_key, [str(name)]),
                "relation": _relation_ref(relation),
                "kind": kind_key,
                "normal_form_scope": "1NF",
                "evidence_class": "observed",
                "confidence": confidence,
                "rationale": (
                    f"Column {name!r} has type "
                    f"{_norm_type(column.get('data_type'))!r}, which stores a "
                    "repeating group or a nested document in a single cell."
                ),
                "false_positive_caveat": (
                    "Array and JSON columns are frequently a deliberate, valid "
                    "design (an evidence envelope, an audit payload, a document "
                    "store). Confirm intent before treating this as a defect."
                ),
                "source_objects": [{"type": "column", "name": name}],
                "next_action": (
                    "Confirm whether this column holds a repeating group that "
                    "belongs in a child table, or record a waiver explaining "
                    "why the nested value is intentional."
                ),
            }
            relation_findings.append(
                _apply_waivers(finding, relation, kind_key, waivers)
            )

        # --- Key evidence: no declared candidate key --------------------
        if not candidate_keys:
            kind_key = "missing_candidate_key"
            finding = {
                "finding_id": _finding_id(oid, kind_key, all_column_names),
                "relation": _relation_ref(relation),
                "kind": kind_key,
                "normal_form_scope": "BCNF",
                "evidence_class": "inferred",
                "confidence": "high",
                "rationale": (
                    "The relation declares no primary key and no NOT NULL "
                    "UNIQUE constraint, so no candidate key is visible to the "
                    "catalog and normalization cannot be assessed."
                ),
                "false_positive_caveat": (
                    "The table may still have a natural key that was simply "
                    "never declared to the database."
                ),
                "source_objects": [{"type": "relation", "name": relation.get("relation_name")}],
                "next_action": (
                    "Declare a primary key or a NOT NULL UNIQUE constraint so "
                    "the relation's normal form can be evaluated."
                ),
            }
            relation_findings.append(
                _apply_waivers(finding, relation, kind_key, waivers)
            )

        # --- BCNF: UNIQUE on a nullable column --------------------------
        for unique in nullable_unique_determinants:
            kind_key = "nullable_unique_determinant"
            unique_columns = unique["columns"]
            finding = {
                "finding_id": _finding_id(oid, kind_key, unique_columns),
                "relation": _relation_ref(relation),
                "kind": kind_key,
                "normal_form_scope": "BCNF",
                "evidence_class": "declared",
                "confidence": "medium",
                "rationale": (
                    f"UNIQUE constraint {unique.get('name')!r} covers column(s) "
                    f"{', '.join(unique_columns)}, at least one of which is "
                    "nullable. PostgreSQL treats NULLs as distinct, so this "
                    "determinant does not guarantee a total key."
                ),
                "false_positive_caveat": (
                    "Partial uniqueness is sometimes intentional (for example a "
                    "single active row per group with the rest NULL)."
                ),
                "source_objects": [
                    {"type": "constraint", "name": unique.get("name")},
                    *[{"type": "column", "name": c} for c in unique_columns],
                ],
                "next_action": (
                    "If this should be a key, add NOT NULL to its columns; "
                    "otherwise document why partial uniqueness is acceptable."
                ),
            }
            relation_findings.append(
                _apply_waivers(finding, relation, kind_key, waivers)
            )

        # --- 2NF: composite-key partial-dependency precondition ---------
        has_single_column_key = any(len(key) == 1 for key in candidate_keys)
        has_composite_key = any(len(key) >= 2 for key in candidate_keys)
        if has_composite_key and not has_single_column_key and non_prime_columns:
            kind_key = "partial_dependency_precondition"
            finding = {
                "finding_id": _finding_id(oid, kind_key, non_prime_columns),
                "relation": _relation_ref(relation),
                "kind": kind_key,
                "normal_form_scope": "2NF",
                "evidence_class": "inferred",
                "confidence": "low",
                "rationale": (
                    "The only candidate key is composite and the relation has "
                    f"non-key column(s) ({', '.join(non_prime_columns)}). That "
                    "is the structural precondition for a 2NF partial "
                    "dependency; the catalog cannot confirm an actual one."
                ),
                "false_positive_caveat": (
                    "This is not a violation on its own. Many relations with a "
                    "composite key are fully normalized."
                ),
                "source_objects": [
                    {"type": "column", "name": c} for c in non_prime_columns
                ],
                "next_action": (
                    "Profile whether any non-key column depends on only part "
                    "of the composite key, or declare the functional "
                    "dependencies so this can be decided from evidence."
                ),
            }
            relation_findings.append(
                _apply_waivers(finding, relation, kind_key, waivers)
            )

        # --- Coarse normal-form label for the relation -----------------
        active_kinds = {
            f["kind"] for f in relation_findings if f["evidence_class"] != "waived"
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
            normal_form = "bcnf"
            nf_evidence = "declared"

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
                    "Label derived only from declared keys, NOT NULL flags, and "
                    "column types. Undeclared functional dependencies are not "
                    "visible to this analyzer."
                ),
            }
        )
        findings.extend(relation_findings)

    findings.sort(
        key=lambda f: (
            str(f["relation"].get("schema") or ""),
            str(f["relation"].get("name") or ""),
            f["normal_form_scope"],
            f["kind"],
            f["finding_id"],
        )
    )
    relation_assessments.sort(
        key=lambda a: (
            str(a["relation"].get("schema") or ""),
            str(a["relation"].get("name") or ""),
        )
    )

    return {
        "version": ASSESSMENT_VERSION,
        "evidence_basis": "catalog_only",
        "relation_assessments": relation_assessments,
        "findings": findings,
    }
