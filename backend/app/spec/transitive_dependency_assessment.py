"""Transitive-dependency (3NF) assessment from catalog plus declared FDs.

The sibling :mod:`app.spec.normalization_assessment` answers 1NF / 2NF / BCNF
questions from catalog evidence alone. It deliberately stops short of third
normal form: a genuine 3NF violation is a *transitive* functional dependency
(a non-prime attribute determined by another non-prime attribute), and the
catalog cannot see a functional dependency that was never declared as a key
or a constraint.

This module adds the 3NF layer without inventing dependencies from column
names. It works from two evidence sources:

* **Catalog** -- declared primary keys, NOT NULL ``UNIQUE`` constraints, and
  declared foreign keys in the snapshot. From these it can only flag a
  *structural precondition* for a transitive dependency, never confirm one.
* **Declared functional dependencies** -- an optional, caller-supplied list.
  Each entry is ``{"relation": "schema.table", "determinant": [col, ...],
  "dependent": [col, ...]}`` and states a functional dependency the caller
  knows to hold (from documentation, an ORM model, or profiling done
  elsewhere). Only when such a dependency is supplied can this module assert
  an actual 3NF violation.

Every finding carries an explicit evidence class (see ``EVIDENCE_CLASSES``,
re-exported from the sibling module) so a declared certainty is never shown
as an inferred guess. The analyzer is a pure, dialect-agnostic function over
the common snapshot JSON shape and emits no DDL.

What this increment does **not** do (tracked on issue #947): discover
functional dependencies from table data (that needs profiling, which belongs
in a separate service), persist signed waivers, or emit an HTTP endpoint.

References (APA 7th):

Codd, E. F. (1971). Normalized data base structure: A brief tutorial. In
*Proceedings of the 1971 ACM SIGFIDET workshop on data description, access
and control* (pp. 1-17). Association for Computing Machinery.
https://doi.org/10.1145/1734714.1734716

Codd, E. F. (1972). Further normalization of the data base relational model.
In R. Rustin (Ed.), *Data base systems* (pp. 33-64). Prentice-Hall.
"""

from __future__ import annotations

from typing import Any

from app.spec.normalization_assessment import (
    EVIDENCE_CLASSES,
    _apply_waivers,
    _finding_id,
    _relation_ref,
)

__all__ = [
    "ASSESSMENT_VERSION",
    "EVIDENCE_CLASSES",
    "FINDING_KINDS",
    "assess_transitive_dependencies",
]

#: Report contract version. Bump on any breaking change to the output shape.
ASSESSMENT_VERSION = "1"

#: The finding kinds this analyzer can emit.
FINDING_KINDS = (
    "transitive_dependency_via_declared_fd",
    "non_key_reference_cluster",
    "candidate_3nf_split",
)

#: Relation kinds worth assessing (ordinary + partitioned tables). Views derive
#: from base relations, so a finding there belongs on the source.
_ASSESSABLE_RELATION_KINDS = frozenset({"r", "p", ""})

_CONTYPE_UNIQUE = "u"


def _relation_records(snapshot: dict[str, Any]) -> dict[Any, dict[str, Any]]:
    """Index a snapshot into per-relation catalog facts.

    Returns a mapping from ``relation_oid`` to a record with the relation
    row, its column names, NOT NULL flags, declared candidate keys (the PK
    plus every all-NOT-NULL ``UNIQUE``), the prime / non-prime column split,
    and the set of foreign-key child columns.
    """
    relations = list(snapshot.get("relations") or [])
    columns = list(snapshot.get("columns") or [])
    pk_columns = list(snapshot.get("pk_columns") or [])
    constraints = list(snapshot.get("constraints") or [])
    fk_edges = list(snapshot.get("fk_edges") or [])

    cols_by_oid: dict[Any, list[dict[str, Any]]] = {}
    pos_to_name: dict[Any, dict[int, str]] = {}
    for column in columns:
        oid = column.get("relation_oid")
        name = column.get("column_name")
        if name is None:
            continue
        cols_by_oid.setdefault(oid, []).append(column)
        position = column.get("column_position")
        if position is not None:
            try:
                pos_to_name.setdefault(oid, {})[int(position)] = str(name)
            except (TypeError, ValueError):
                pass

    pk_by_oid: dict[Any, list[str]] = {}
    for pk in pk_columns:
        name = pk.get("column_name")
        if name is not None:
            pk_by_oid.setdefault(pk.get("relation_oid"), []).append(str(name))

    uniques_by_oid: dict[Any, list[list[str]]] = {}
    for constraint in constraints:
        if str(constraint.get("constraint_type")) != _CONTYPE_UNIQUE:
            continue
        oid = constraint.get("relation_oid")
        pos_map = pos_to_name.get(oid, {})
        names: list[str] = []
        ok = True
        for attnum in constraint.get("constrained_attnums") or []:
            try:
                resolved = pos_map.get(int(attnum))
            except (TypeError, ValueError):
                resolved = None
            if resolved is None:
                ok = False
                break
            names.append(resolved)
        if ok and names:
            uniques_by_oid.setdefault(oid, []).append(names)

    fk_cols_by_oid: dict[Any, set[str]] = {}
    for edge in fk_edges:
        child = edge.get("child_column_name")
        if child is not None:
            fk_cols_by_oid.setdefault(edge.get("child_relation_oid"), set()).add(
                str(child)
            )

    records: dict[Any, dict[str, Any]] = {}
    for relation in relations:
        if str(relation.get("relation_kind") or "") not in _ASSESSABLE_RELATION_KINDS:
            continue
        oid = relation.get("relation_oid")
        relation_columns = cols_by_oid.get(oid, [])
        if not relation_columns:
            continue
        not_null = {
            str(c.get("column_name")): bool(c.get("is_not_null"))
            for c in relation_columns
            if c.get("column_name") is not None
        }
        all_names = list(not_null)

        candidate_keys: list[list[str]] = []
        pk_cols = pk_by_oid.get(oid, [])
        if pk_cols:
            candidate_keys.append(sorted(pk_cols))
        for unique_columns in uniques_by_oid.get(oid, []):
            if all(not_null.get(name, False) for name in unique_columns):
                key = sorted(unique_columns)
                if key not in candidate_keys:
                    candidate_keys.append(key)

        prime = sorted({c for key in candidate_keys for c in key})
        non_prime = sorted(set(all_names) - set(prime))
        records[oid] = {
            "relation": relation,
            "column_names": set(all_names),
            "candidate_keys": candidate_keys,
            "prime_columns": prime,
            "non_prime_columns": non_prime,
            "fk_columns": sorted(fk_cols_by_oid.get(oid, set())),
        }
    return records


def _is_superkey(column_set: set[str], candidate_keys: list[list[str]]) -> bool:
    """Return ``True`` when ``column_set`` contains a whole candidate key."""
    return any(set(key).issubset(column_set) for key in candidate_keys)


def _fqname(relation: dict[str, Any]) -> str:
    """Return ``"schema.name"`` for a relation row."""
    return f"{relation.get('schema_name')}.{relation.get('relation_name')}"


def assess_transitive_dependencies(
    snapshot: dict[str, Any] | None,
    *,
    declared_functional_dependencies: list[dict[str, Any]] | None = None,
    waivers: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Assess third normal form from catalog evidence and declared FDs.

    Args:
        snapshot: A schema snapshot in the common introspection JSON shape.
            ``None`` or missing keys are treated as an empty schema.
        declared_functional_dependencies: Optional list of caller-asserted
            functional dependencies, each
            ``{"relation": "schema.table", "determinant": [col, ...],
            "dependent": [col, ...]}``. Dependencies are never inferred from
            column names; only what the caller supplies here can raise a
            confirmed 3NF finding. Entries that name an unknown relation or
            unknown columns are reported under ``unresolved_declared_fds``.
        waivers: Optional list of waiver records with the same shape the
            sibling :func:`app.spec.normalization_assessment.assess_normalization`
            accepts (``{"scope": {"schema"?, "relation"?, "kind"?}, ...}``). A
            matched finding is recorded with evidence class ``waived`` and an
            attached ``waiver`` object rather than dropped.

    Returns:
        A dictionary with:

        ``version``
            :data:`ASSESSMENT_VERSION`.
        ``evidence_basis``
            Always ``"catalog_and_declared"``.
        ``relation_assessments``
            One record per assessed base relation: its relation reference,
            candidate keys, prime / non-prime split, foreign-key columns, and
            the count of declared FDs that resolved against it.
        ``findings``
            Zero or more finding records (see :data:`FINDING_KINDS`), each
            with a deterministic ``finding_id``, ``relation`` reference,
            ``kind``, ``normal_form_scope`` (``"3NF"``), ``evidence_class``,
            ``confidence``, ``rationale``, ``false_positive_caveat``,
            ``source_objects``, and ``next_action``. Sorted for stable output.
        ``unresolved_declared_fds``
            The declared-FD entries that could not be matched to a relation
            and its columns, each with a ``reason``.

        The analyzer performs no I/O and emits no DDL.
    """
    snapshot = snapshot or {}
    waivers = list(waivers or [])
    declared = list(declared_functional_dependencies or [])

    records = _relation_records(snapshot)
    by_fqname: dict[str, dict[str, Any]] = {
        _fqname(rec["relation"]): rec for rec in records.values()
    }

    findings: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    declared_fd_count: dict[Any, int] = {}

    for entry in declared:
        rel_name = str(entry.get("relation") or "")
        determinant = [str(c) for c in entry.get("determinant") or []]
        dependent = [str(c) for c in entry.get("dependent") or []]
        record = by_fqname.get(rel_name)
        if record is None:
            unresolved.append({"entry": entry, "reason": "relation_not_found"})
            continue
        if not determinant or not dependent:
            unresolved.append({"entry": entry, "reason": "empty_determinant_or_dependent"})
            continue
        known = record["column_names"]
        unknown = sorted((set(determinant) | set(dependent)) - known)
        if unknown:
            unresolved.append(
                {"entry": entry, "reason": f"unknown_columns:{','.join(unknown)}"}
            )
            continue

        oid = record["relation"].get("relation_oid")
        declared_fd_count[oid] = declared_fd_count.get(oid, 0) + 1

        det_set = set(determinant)
        candidate_keys = record["candidate_keys"]
        prime = set(record["prime_columns"])

        determinant_is_superkey = _is_superkey(det_set, candidate_keys)
        dependent_all_non_prime = all(col not in prime for col in dependent)
        determinant_all_non_prime = all(col not in prime for col in determinant)

        if determinant_is_superkey or not dependent_all_non_prime:
            # A dependency on a superkey is the definition of a key; a
            # dependency whose right side is a prime attribute is allowed in
            # 3NF. Neither is a violation.
            continue

        kind_key = "transitive_dependency_via_declared_fd"
        relation = record["relation"]
        finding = {
            "finding_id": _finding_id(oid, kind_key, sorted(det_set) + sorted(dependent)),
            "relation": _relation_ref(relation),
            "kind": kind_key,
            "normal_form_scope": "3NF",
            "evidence_class": "declared",
            "confidence": "high" if determinant_all_non_prime else "medium",
            "rationale": (
                f"Declared functional dependency {sorted(det_set)!r} -> "
                f"{sorted(dependent)!r}: the determinant is not a superkey and "
                "the dependent columns are non-prime, so the dependent columns "
                "transitively depend on a candidate key through the "
                "determinant. That is a third normal form violation."
            ),
            "false_positive_caveat": (
                "This finding is only as sound as the supplied functional "
                "dependency. If the dependency does not actually hold in the "
                "data, withdraw it from the declared list."
            ),
            "source_objects": (
                [{"type": "column", "name": c} for c in sorted(det_set)]
                + [{"type": "column", "name": c} for c in sorted(dependent)]
            ),
            "next_action": (
                "Move the determinant and its dependent columns into their own "
                "relation keyed by the determinant, and replace the dependent "
                "columns here with a foreign key to it -- or record a waiver "
                "explaining why the redundancy is accepted."
            ),
        }
        findings.append(_apply_waivers(finding, relation, kind_key, waivers))

        split_kind = "candidate_3nf_split"
        split = {
            "finding_id": _finding_id(oid, split_kind, sorted(det_set) + sorted(dependent)),
            "relation": _relation_ref(relation),
            "kind": split_kind,
            "normal_form_scope": "3NF",
            "evidence_class": "proposed",
            "confidence": "medium",
            "rationale": (
                "A 3NF-preserving decomposition exists for the declared "
                f"dependency {sorted(det_set)!r} -> {sorted(dependent)!r}."
            ),
            "false_positive_caveat": (
                "A proposal only. Splitting changes the physical model and "
                "every query and write path that touches these columns; it is "
                "never applied automatically."
            ),
            "source_objects": [
                {
                    "type": "proposed_relation",
                    "key": sorted(det_set),
                    "columns": sorted(det_set | set(dependent)),
                }
            ],
            "next_action": (
                "Review the proposed split with the owning team before any "
                "migration is drafted."
            ),
        }
        findings.append(_apply_waivers(split, relation, split_kind, waivers))

    # --- Catalog-only: non-key foreign-key clusters -----------------------
    for oid, record in records.items():
        fk_columns = record["fk_columns"]
        prime = set(record["prime_columns"])
        non_prime = set(record["non_prime_columns"])
        if len(fk_columns) <= 1:
            continue
        if _is_superkey(set(fk_columns), record["candidate_keys"]):
            continue
        descriptive = sorted((non_prime - set(fk_columns)))
        if not descriptive:
            continue

        kind_key = "non_key_reference_cluster"
        relation = record["relation"]
        finding = {
            "finding_id": _finding_id(oid, kind_key, fk_columns),
            "relation": _relation_ref(relation),
            "kind": kind_key,
            "normal_form_scope": "3NF",
            "evidence_class": "inferred",
            "confidence": "low",
            "rationale": (
                f"The relation carries multiple foreign-key columns "
                f"({fk_columns!r}) that are not a candidate key, alongside "
                f"non-prime descriptive columns ({descriptive!r}). Those "
                "descriptive columns may transitively depend on one of the "
                "referenced entities rather than on this relation's key."
            ),
            "false_positive_caveat": (
                "Row-level profiling or a declared functional dependency is "
                "needed to confirm a real transitive dependency. A junction "
                "table that legitimately carries edge attributes is a common "
                "and valid shape that looks the same to the catalog."
            ),
            "source_objects": (
                [{"type": "column", "name": c} for c in fk_columns]
                + [{"type": "column", "name": c} for c in descriptive]
            ),
            "next_action": (
                "Confirm (by profiling or documentation) whether each "
                "descriptive column depends on this relation's key or on a "
                "referenced entity; supply the functional dependency to this "
                "analyzer to get a confirmed finding."
            ),
        }
        findings.append(_apply_waivers(finding, relation, kind_key, waivers))

    findings.sort(
        key=lambda f: (
            str(f["relation"].get("schema") or ""),
            str(f["relation"].get("name") or ""),
            f["kind"],
            f["finding_id"],
        )
    )

    relation_assessments = [
        {
            "relation": _relation_ref(record["relation"]),
            "candidate_keys": record["candidate_keys"],
            "prime_columns": record["prime_columns"],
            "non_prime_columns": record["non_prime_columns"],
            "foreign_key_columns": record["fk_columns"],
            "declared_fd_count": declared_fd_count.get(
                record["relation"].get("relation_oid"), 0
            ),
            "evidence_class": "declared",
        }
        for record in records.values()
    ]
    relation_assessments.sort(
        key=lambda a: (
            str(a["relation"].get("schema") or ""),
            str(a["relation"].get("name") or ""),
        )
    )

    return {
        "version": ASSESSMENT_VERSION,
        "evidence_basis": "catalog_and_declared",
        "relation_assessments": relation_assessments,
        "findings": findings,
        "unresolved_declared_fds": unresolved,
    }
