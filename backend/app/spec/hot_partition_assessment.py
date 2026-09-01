"""Catalog-evidence hot-partition and growth assessment.

Enterprise buyers ask which metadata, queue, audit, snapshot, or target-schema
objects are likely to become **hot partitions** -- write/read concentration
points -- or to grow without bound under the expected workload.

This module answers from **catalog evidence** (declared keys, column types and
defaults, and PostgreSQL partitioning metadata) plus an **optional explicit
capacity profile**. It never assumes a live workload, never samples data, and
never emits DDL. Every finding carries an evidence class:

``observed``
    Directly visible in the catalog (e.g. a partitioned table whose unique
    keys already contain the partition key).
``declared``
    Provable from a declared object (e.g. a monotonic serial primary key, or a
    partitioned table whose unique key omits the partition key).
``inferred``
    A structural / naming signal is present but confirmation needs workload
    evidence.
``proposed``
    A concrete remediation, emitted only when a ``capacity_profile`` supplies
    the missing quantities, or the signal is catalog-declared.

Deferred to a later increment (see the doctoring doc): generated
``EXPLAIN`` / ``EXPLAIN ANALYZE`` partition-pruning fixtures against a real
PostgreSQL, and persisted capacity-profile records.

References (APA 7th):

The PostgreSQL Global Development Group. (2025). *PostgreSQL 17 documentation:
Chapter 5.12, Table partitioning*. https://www.postgresql.org/docs/17/ddl-partitioning.html

Nemeth, E., Snyder, G., Hein, T. R., Whaley, B., & Mackin, D. (2017). *UNIX
and Linux system administration handbook* (5th ed.). Addison-Wesley.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable

#: Report contract version. Bump on any breaking change to the output shape.
ASSESSMENT_VERSION = "1"

#: Evidence classes a finding may carry, most to least certain.
EVIDENCE_CLASSES = ("observed", "declared", "inferred", "proposed")

#: Relation kinds worth assessing (ordinary + partitioned tables).
_ASSESSABLE_RELATION_KINDS = frozenset({"r", "p", ""})

#: Table-name tokens that signal an append-heavy / event-stream write pattern.
_APPEND_HEAVY_TOKENS = frozenset(
    {
        "job",
        "jobs",
        "queue",
        "outbox",
        "inbox",
        "audit",
        "event",
        "events",
        "log",
        "logs",
        "history",
        "activity",
        "session",
        "sessions",
        "access",
        "webhook",
        "webhooks",
        "notification",
        "notifications",
        "message",
        "messages",
    }
)

#: Substrings that signal an explicit retention / expiry mechanism on a column.
_RETENTION_SUBSTRINGS = (
    "deleted_at",
    "expires_at",
    "expire_at",
    "expiry",
    "purge_after",
    "archived_at",
    "retain_until",
    "ttl",
)

#: Single tokens that, as a whole word in a column name, signal a write/read
#: concentration axis (matched exactly, as a ``_``-suffix, or as a ``_``-prefix
#: so ``tenant_id`` / ``org_id`` / ``project_space_uuid`` all count).
_SKEW_AXIS_TOKENS = (
    "status",
    "state",
    "tenant",
    "org",
    "organization",
    "account",
    "project",
    "kind",
    "type",
    "category",
)


def _has_retention_signal(column_name: str) -> bool:
    """Return ``True`` when a column name denotes a retention / expiry field."""

    lowered = column_name.lower()
    return any(sub in lowered for sub in _RETENTION_SUBSTRINGS)


def _is_skew_axis(column_name: str) -> bool:
    """Return ``True`` when a column name reads as a concentration axis."""

    lowered = column_name.lower()
    return any(
        lowered == token
        or lowered.startswith(token + "_")
        or lowered.endswith("_" + token)
        for token in _SKEW_AXIS_TOKENS
    )

_TIME_TYPES = frozenset(
    {
        "timestamp",
        "timestamp with time zone",
        "timestamp without time zone",
        "timestamptz",
        "date",
    }
)


def _norm_type(data_type: object) -> str:
    """Normalize a SQL type name for comparison (drop length/precision)."""

    text = str(data_type or "").strip().lower()
    text = re.sub(r"\(.*?\)", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _tokens(name: object) -> set[str]:
    """Split an identifier into lower-case ``_``/``-`` separated tokens."""

    return {t for t in re.split(r"[^a-z0-9]+", str(name or "").lower()) if t}


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


def _is_serial_default(column: dict[str, Any]) -> bool:
    """Return ``True`` when a column's default makes it strictly increasing."""

    if not column.get("has_default"):
        # ``serial`` pseudo-types still carry a nextval default; also accept the
        # rare snapshot that records the type text directly.
        return "serial" in _norm_type(column.get("data_type"))
    expr = str(column.get("default_expr") or "").lower()
    return "nextval(" in expr or "identity" in expr


def _is_time_column(column: dict[str, Any]) -> bool:
    """Return ``True`` for a timestamp/date column."""

    return _norm_type(column.get("data_type")) in _TIME_TYPES


def _partition_key_columns(relation: dict[str, Any]) -> list[str]:
    """Best-effort column names from a ``pg_get_partkeydef`` string.

    ``partition_key`` looks like ``RANGE (created_at)`` or ``LIST (tenant_id,
    status)``. Expression keys (``RANGE (date_trunc('day', ts))``) yield no
    plain column names and are returned empty.
    """

    text = str(relation.get("partition_key") or "")
    match = re.search(r"\((.*)\)\s*$", text)
    if not match:
        return []
    inside = match.group(1)
    if "(" in inside or "'" in inside:
        return []
    return [c.strip().strip('"') for c in inside.split(",") if c.strip()]


def _profile_for(
    capacity_profile: dict[str, Any] | None, section: str, relation_name: object
) -> Any:
    """Return ``capacity_profile[section][relation_name]`` or ``None``."""

    if not capacity_profile:
        return None
    return (capacity_profile.get(section) or {}).get(str(relation_name))


def assess_hot_partitions(
    snapshot: dict[str, Any] | None,
    *,
    capacity_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assess hot-partition and unbounded-growth risk for every base relation.

    Args:
        snapshot: A schema snapshot in the common introspection JSON shape.
        capacity_profile: Optional explicit workload expectations. Recognized
            sections are ``expected_rows`` (``{relation_name: int}``),
            ``retention_days`` (``{relation_name: int}``), and
            ``write_concentration_keys`` (``{relation_name: [column, ...]}``).
            When a relevant section names a relation, that relation's findings
            are promoted from ``inferred`` to ``proposed`` and given a concrete
            recommendation. No section is required.

    Returns:
        A dict with ``version`` (:data:`ASSESSMENT_VERSION`),
        ``evidence_basis``, ``capacity_profile_applied`` (bool),
        ``relation_assessments`` (one per assessed relation: partition state,
        detected signals, coarse ``risk``), and ``findings`` (each with
        ``finding_id``, ``relation``, ``kind``, ``evidence_class``,
        ``confidence``, ``rationale``, ``caveat``, ``source_objects``,
        ``next_action``). Sorted for stable output. No I/O, no DDL.
    """

    snapshot = snapshot or {}
    relations: list[dict[str, Any]] = list(snapshot.get("relations") or [])
    columns: list[dict[str, Any]] = list(snapshot.get("columns") or [])
    pk_columns: list[dict[str, Any]] = list(snapshot.get("pk_columns") or [])
    constraints: list[dict[str, Any]] = list(snapshot.get("constraints") or [])

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

    unique_col_sets_by_oid: dict[Any, list[list[str]]] = {}
    for constraint in constraints:
        if str(constraint.get("constraint_type")) not in {"u", "p"}:
            continue
        oid = constraint.get("relation_oid")
        pos_map = attname_by_oid_pos.get(oid, {})
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
            unique_col_sets_by_oid.setdefault(oid, []).append(names)

    findings: list[dict[str, Any]] = []
    relation_assessments: list[dict[str, Any]] = []
    profile_applied = False

    for relation in relations:
        if str(relation.get("relation_kind") or "") not in _ASSESSABLE_RELATION_KINDS:
            continue
        oid = relation.get("relation_oid")
        relation_columns = cols_by_oid.get(oid, [])
        if not relation_columns:
            continue
        name = relation.get("relation_name")
        name_tokens = _tokens(name)
        column_names = {str(c.get("column_name")) for c in relation_columns}

        is_partitioned_parent = bool(relation.get("partition_key"))
        is_partition_child = bool(relation.get("is_partition"))
        partition_state = (
            "partitioned"
            if is_partitioned_parent
            else "partition_child"
            if is_partition_child
            else "unpartitioned"
        )

        append_heavy = bool(name_tokens & _APPEND_HEAVY_TOKENS)
        time_columns = [
            str(c.get("column_name")) for c in relation_columns if _is_time_column(c)
        ]
        serial_pk_cols = [
            str(c.get("column_name"))
            for c in relation_columns
            if str(c.get("column_name")) in pk_by_oid.get(oid, [])
            and _is_serial_default(c)
        ]
        retention_columns = sorted(
            cn for cn in column_names if _has_retention_signal(cn)
        )
        skew_columns = sorted(cn for cn in column_names if _is_skew_axis(cn))
        growing = bool(serial_pk_cols or time_columns)

        relation_findings: list[dict[str, Any]] = []
        signals: list[str] = []

        # --- append-heavy write pattern --------------------------------
        if append_heavy and growing:
            signals.append("append_heavy")
            profiled_rows = _profile_for(capacity_profile, "expected_rows", name)
            if profiled_rows is not None:
                profile_applied = True
            relation_findings.append(
                {
                    "kind": "append_heavy_table",
                    "evidence_class": "proposed" if profiled_rows is not None else "inferred",
                    "confidence": "medium",
                    "rationale": (
                        f"Relation name {name!r} matches an append/event-stream "
                        "vocabulary and it has "
                        + (
                            f"a monotonic key ({', '.join(serial_pk_cols)}) "
                            if serial_pk_cols
                            else ""
                        )
                        + (
                            f"time column(s) {', '.join(time_columns)}"
                            if time_columns
                            else ""
                        ).strip()
                        + ". Inserts concentrate on the newest rows/pages."
                        + (
                            f" Capacity profile expects ~{profiled_rows} rows."
                            if profiled_rows is not None
                            else ""
                        )
                    ),
                    "caveat": (
                        "This is a naming + structure signal, not a measured "
                        "write rate. A small or bounded table needs no action."
                    ),
                    "source_objects": [
                        {"type": "relation", "name": name},
                        *[{"type": "column", "name": c} for c in time_columns[:1]],
                    ],
                    "next_action": (
                        "Measure insert rate and row growth. If growth is "
                        "unbounded, RANGE-partition by "
                        + (time_columns[0] if time_columns else "the insert-time column")
                        + " so old data can be detached and archived cheaply."
                    ),
                }
            )

            # --- unbounded retention ---------------------------------
            profiled_retention = _profile_for(capacity_profile, "retention_days", name)
            if profiled_retention is not None:
                profile_applied = True
            if not retention_columns:
                signals.append("no_retention_signal")
                relation_findings.append(
                    {
                        "kind": "unbounded_retention",
                        "evidence_class": "proposed" if profiled_retention is not None else "inferred",
                        "confidence": "medium",
                        "rationale": (
                            "An append-heavy relation with no retention column "
                            "(deleted_at / expires_at / archived_at / purge_after) "
                            "grows without a catalog-visible bound, inflating "
                            "storage, VACUUM cost, and index size."
                            + (
                                f" Capacity profile sets retention to {profiled_retention} day(s)."
                                if profiled_retention is not None
                                else ""
                            )
                        ),
                        "caveat": (
                            "Retention may be handled outside the schema (an "
                            "external job, a partition-drop cron)."
                        ),
                        "source_objects": [{"type": "relation", "name": name}],
                        "next_action": (
                            "Define an explicit retention policy (archive or "
                            "delete after "
                            + (f"{profiled_retention} days" if profiled_retention is not None else "a documented window")
                            + "), or record why unbounded retention is required."
                        ),
                    }
                )

        # --- monotonic key insert hot-page ---------------------------
        if serial_pk_cols and len(pk_by_oid.get(oid, [])) == 1:
            signals.append("monotonic_key")
            relation_findings.append(
                {
                    "kind": "monotonic_key_hot_page",
                    "evidence_class": "declared",
                    "confidence": "medium",
                    "rationale": (
                        f"The single-column primary key {serial_pk_cols[0]!r} is "
                        "strictly increasing (nextval/identity). Under high "
                        "insert concurrency the right-most B-tree leaf is a "
                        "contention hot-spot, and the key gives no useful "
                        "range-partition pruning."
                    ),
                    "caveat": (
                        "Perfectly fine at low-to-moderate insert rates; only a "
                        "concern under sustained high-concurrency inserts."
                    ),
                    "source_objects": [{"type": "column", "name": serial_pk_cols[0]}],
                    "next_action": (
                        "If insert throughput becomes a bottleneck, use a "
                        "time-ordered non-monotonic key (UUIDv7 / ULID) or hash "
                        "partitioning to spread inserts."
                    ),
                }
            )

        # --- partition semantics -----------------------------------
        if is_partitioned_parent:
            pkey_cols = _partition_key_columns(relation)
            key_sets = unique_col_sets_by_oid.get(oid, [])
            bad_key_sets = [
                ks
                for ks in key_sets
                if pkey_cols and not set(pkey_cols).issubset(set(ks))
            ]
            if bad_key_sets:
                signals.append("partition_key_not_in_unique")
                relation_findings.append(
                    {
                        "kind": "partition_semantics_review",
                        "evidence_class": "declared",
                        "confidence": "high",
                        "rationale": (
                            f"Partitioned by ({', '.join(pkey_cols)}), but a "
                            "declared PRIMARY KEY / UNIQUE constraint "
                            f"({', '.join(bad_key_sets[0])}) does not contain "
                            "the partition key. PostgreSQL only enforces such a "
                            "constraint per partition, so global uniqueness is "
                            "not guaranteed."
                        ),
                        "caveat": (
                            "Acceptable if per-partition uniqueness is genuinely "
                            "all that is required."
                        ),
                        "source_objects": [
                            {"type": "column", "name": c} for c in bad_key_sets[0]
                        ],
                        "next_action": (
                            "Add the partition key column(s) to the unique "
                            "constraint, or move global-uniqueness enforcement "
                            "to the application / a lookup table."
                        ),
                    }
                )
            elif pkey_cols:
                signals.append("partition_semantics_ok")
            # An unpartitioned append-heavy/growing table is the candidate to
            # *become* partitioned; the append_heavy_table finding already
            # covers that recommendation.

        # --- write/read skew axis --------------------------------
        if skew_columns and growing and not is_partitioned_parent:
            profiled_keys = _profile_for(
                capacity_profile, "write_concentration_keys", name
            )
            if profiled_keys is not None:
                profile_applied = True
            signals.append("skew_axis")
            relation_findings.append(
                {
                    "kind": "skew_candidate",
                    "evidence_class": "proposed" if profiled_keys else "inferred",
                    "confidence": "low",
                    "rationale": (
                        f"Growing relation has low-cardinality axis column(s) "
                        f"{', '.join(skew_columns)}. One value (a busy tenant, a "
                        "dominant status) can concentrate writes/reads and "
                        "starve other work sharing the table."
                        + (
                            f" Capacity profile names {', '.join(profiled_keys)} as the concentration key."
                            if profiled_keys
                            else ""
                        )
                    ),
                    "caveat": (
                        "Needs per-value row and write distribution evidence; "
                        "many such columns are evenly distributed."
                    ),
                    "source_objects": [
                        {"type": "column", "name": c}
                        for c in (list(profiled_keys) if profiled_keys else skew_columns)
                    ],
                    "next_action": (
                        "Measure per-value distribution. If skewed, use "
                        "LIST/HASH partitioning on the hot axis or a dedicated "
                        "processing lane per hot key so one value cannot starve "
                        "the rest."
                    ),
                }
            )

        for finding in relation_findings:
            finding["relation"] = _relation_ref(relation)
            finding["finding_id"] = _finding_id(
                oid, finding["kind"], [o["name"] for o in finding["source_objects"]]
            )
            findings.append(finding)

        relation_assessments.append(
            {
                "relation": _relation_ref(relation),
                "partition_state": partition_state,
                "signals": sorted(set(signals)),
                "risk": "review" if relation_findings else "ok",
            }
        )

    findings.sort(
        key=lambda f: (
            str(f["relation"].get("schema") or ""),
            str(f["relation"].get("name") or ""),
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
        "evidence_basis": "catalog_and_optional_capacity_profile",
        "capacity_profile_applied": profile_applied,
        "relation_assessments": relation_assessments,
        "findings": findings,
    }
